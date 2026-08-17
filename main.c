#include "proto/virtual-keyboard-unstable-v1-client-protocol.h"
#include "proto/wlr-layer-shell-unstable-v1-client-protocol.h"
#include "proto/xdg-shell-client-protocol.h"
#include "proto/fractional-scale-v1-client-protocol.h"
#include "proto/viewporter-client-protocol.h"
#include "proto/input-method-unstable-v2-protocol.h"
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <linux/input-event-codes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/signalfd.h>
#include <sys/timerfd.h>
#include <poll.h>
#include <unistd.h>
#include <wayland-client-protocol.h>
#include <wayland-client.h>
#include <wchar.h>

#include "keyboard.h"
#include "config.h"
#include "visibility_policy.h"

/* lazy die macro */
#define die(...)                                                               \
    fprintf(stderr, __VA_ARGS__);                                              \
    exit(1)

/* array size */
#define countof(x) (sizeof(x) / sizeof(*x))

/* client state */
static const char *namespace = "wvkbd";
static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_seat *seat;
static struct wl_pointer *pointer;
static struct wl_touch *touch;
static struct wl_region *empty_region;
static struct zwlr_layer_shell_v1 *layer_shell;
static struct zwlr_layer_surface_v1 *layer_surface;
static struct xdg_wm_base *wm_base;
static struct xdg_surface *popup_xdg_surface;
static struct xdg_popup *popup_xdg_popup;
static struct xdg_positioner *popup_xdg_positioner;
static struct zwp_virtual_keyboard_manager_v1 *vkbd_mgr;
static struct wp_fractional_scale_v1 *wfs_draw_surf;
static struct wp_fractional_scale_manager_v1 *wfs_mgr;
static struct wp_viewport *draw_surf_viewport, *popup_draw_surf_viewport;
static struct wp_viewporter *viewporter;
static struct zwp_input_method_manager_v2 *im_mgr;
static struct zwp_input_method_v2 *input_method;
static uint32_t input_method_serial = 0;
static bool popup_xdg_surface_configured;
static bool layer_surface_configured;

static uint32_t available_width, available_height = 0;
static void refresh_available_dimension();

/* drawing */
static struct drw draw_ctx;
static struct drwbuf draw_surf_back_buffer, draw_surf_display_buffer, popup_draw_surf_back_buffer, popup_draw_surf_display_buffer;
static struct drwsurf draw_surf, popup_draw_surf;

/* layer surface parameters */
static uint32_t layer = ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY;
static uint32_t anchor = ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM |
                         ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT |
                         ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT;

/* application state */
static bool run_display = true;
static int cur_x = -1, cur_y = -1;
static bool cur_press = false;
static struct kbd keyboard;
static uint32_t height, normal_height, landscape_height;
static int rounding = DEFAULT_ROUNDING;
static bool hidden = false;
static bool im_auto = false;
/* Distinguish an explicit Hide-key request from automatic focus-loss hiding.
 * Some clients answer a second tap in an already-focused field with only an
 * input-method `done` batch, so the next batch may reopen a manually hidden
 * keyboard.  Automatic hiding must stay hidden until a fresh activation. */
static struct z13_visibility_policy visibility_policy = {0};
static double forced_scale = 0;
static struct key *touch_space_key = NULL;
static uint32_t touch_space_started = 0;
static int touch_space_x = 0, touch_space_y = 0;
static bool touch_space_trackpad = false;
static struct key *touch_flick_key = NULL;
static int32_t touch_flick_id = -1;
static int touch_flick_x = 0, touch_flick_y = 0;
static bool touch_flicked = false;
static int repeat_fd = -1;
static struct key *repeat_key = NULL;
static int hide_delay_fd = -1;
static int touch_reopen_fd = -1;
static int touch_device_fd = -1;

static void cancel_delayed_hide(void)
{
    if (hide_delay_fd >= 0) {
        struct itimerspec timer = {0};
        timerfd_settime(hide_delay_fd, 0, &timer, NULL);
    }
}

static void schedule_delayed_hide(void)
{
    if (hide_delay_fd < 0)
        return;
    struct itimerspec timer = {
        .it_value = { .tv_sec = 0, .tv_nsec = 500000000 },
    };
    timerfd_settime(hide_delay_fd, 0, &timer, NULL);
}

static void cancel_touch_reopen(void)
{
    z13_visibility_cancel_touch_reopen(&visibility_policy);
    if (touch_reopen_fd >= 0) {
        struct itimerspec timer = {0};
        timerfd_settime(touch_reopen_fd, 0, &timer, NULL);
    }
}

static void schedule_touch_reopen(void)
{
    if (touch_reopen_fd < 0)
        return;
    struct itimerspec timer = {
        .it_value = { .tv_sec = 0, .tv_nsec = 140000000 },
    };
    timerfd_settime(touch_reopen_fd, 0, &timer, NULL);
}

static int
encode_utf8(uint32_t codepoint, char output[5])
{
    if (codepoint <= 0x7f) {
        output[0] = codepoint;
        output[1] = '\0';
        return 1;
    }
    if (codepoint <= 0x7ff) {
        output[0] = 0xc0 | (codepoint >> 6);
        output[1] = 0x80 | (codepoint & 0x3f);
        output[2] = '\0';
        return 2;
    }
    if (codepoint >= 0xd800 && codepoint <= 0xdfff)
        return 0;
    if (codepoint <= 0xffff) {
        output[0] = 0xe0 | (codepoint >> 12);
        output[1] = 0x80 | ((codepoint >> 6) & 0x3f);
        output[2] = 0x80 | (codepoint & 0x3f);
        output[3] = '\0';
        return 3;
    }
    if (codepoint <= 0x10ffff) {
        output[0] = 0xf0 | (codepoint >> 18);
        output[1] = 0x80 | ((codepoint >> 12) & 0x3f);
        output[2] = 0x80 | ((codepoint >> 6) & 0x3f);
        output[3] = 0x80 | (codepoint & 0x3f);
        output[4] = '\0';
        return 4;
    }
    return 0;
}

static bool
im_commit_codepoint(uint32_t codepoint)
{
    char text[5];
    if (!input_method || !visibility_policy.input_method_active ||
        !encode_utf8(codepoint, text))
        return false;

    zwp_input_method_v2_commit_string(input_method, text);
    zwp_input_method_v2_commit(input_method, input_method_serial);
    fprintf(stderr, "Committed flick/copy text U+%04X through input method\n",
            codepoint);
    return true;
}

static void stop_key_repeat(void)
{
    if (repeat_fd >= 0) {
        struct itimerspec timer = {0};
        timerfd_settime(repeat_fd, 0, &timer, NULL);
    }
    repeat_key = NULL;
}

static void start_key_repeat(struct key *key)
{
    if (!key || key->type != Code ||
        (key->code != KEY_BACKSPACE && key->code != KEY_DELETE))
        return;

    struct itimerspec timer = {
        .it_value = { .tv_sec = 0, .tv_nsec = 420000000 },
        .it_interval = { .tv_sec = 0, .tv_nsec = 55000000 },
    };
    repeat_key = key;
    timerfd_settime(repeat_fd, 0, &timer, NULL);
}

/* event handler prototypes */
static void wl_pointer_enter(void *data, struct wl_pointer *wl_pointer,
                             uint32_t serial, struct wl_surface *surface,
                             wl_fixed_t surface_x, wl_fixed_t surface_y);
static void wl_pointer_leave(void *data, struct wl_pointer *wl_pointer,
                             uint32_t serial, struct wl_surface *surface);
static void wl_pointer_motion(void *data, struct wl_pointer *wl_pointer,
                              uint32_t time, wl_fixed_t surface_x,
                              wl_fixed_t surface_y);
static void wl_pointer_button(void *data, struct wl_pointer *wl_pointer,
                              uint32_t serial, uint32_t time, uint32_t button,
                              uint32_t state);
static void wl_pointer_axis(void *data, struct wl_pointer *wl_pointer,
                            uint32_t time, uint32_t axis, wl_fixed_t value);

static void wl_touch_down(void *data, struct wl_touch *wl_touch,
                          uint32_t serial, uint32_t time,
                          struct wl_surface *surface, int32_t id, wl_fixed_t x,
                          wl_fixed_t y);
static void wl_touch_up(void *data, struct wl_touch *wl_touch, uint32_t serial,
                        uint32_t time, int32_t id);
static void wl_touch_motion(void *data, struct wl_touch *wl_touch,
                            uint32_t time, int32_t id, wl_fixed_t x,
                            wl_fixed_t y);
static void wl_touch_frame(void *data, struct wl_touch *wl_touch);
static void wl_touch_cancel(void *data, struct wl_touch *wl_touch);
static void wl_touch_shape(void *data, struct wl_touch *wl_touch, int32_t id,
                           wl_fixed_t major, wl_fixed_t minor);
static void wl_touch_orientation(void *data, struct wl_touch *wl_touch,
                                 int32_t id, wl_fixed_t orientation);

static void seat_handle_capabilities(void *data, struct wl_seat *wl_seat,
                                     enum wl_seat_capability caps);
static void seat_handle_name(void *data, struct wl_seat *wl_seat,
                             const char *name);

static void handle_global(void *data, struct wl_registry *registry,
                          uint32_t name, const char *interface,
                          uint32_t version);
static void handle_global_remove(void *data, struct wl_registry *registry,
                                 uint32_t name);

static void layer_surface_configure(void *data,
                                    struct zwlr_layer_surface_v1 *surface,
                                    uint32_t serial, uint32_t w, uint32_t h);
static void layer_surface_closed(void *data,
                                 struct zwlr_layer_surface_v1 *surface);
static void im_activate(void *data, struct zwp_input_method_v2 *zwp_input_method_v2);
static void im_deactivate(void *data, struct zwp_input_method_v2 *zwp_input_method_v2);
static void im_surrounding_text(void *data, struct zwp_input_method_v2 *zwp_input_method_v2,
                                const char *text, uint32_t cursor, uint32_t anchor);
static void im_text_change_cause(void *data, struct zwp_input_method_v2 *zwp_input_method_v2,
                                 uint32_t cause);
static void im_content_type(void *data, struct zwp_input_method_v2 *zwp_input_method_v2,
                            uint32_t hint, uint32_t purpose);
static void im_done(void *data, struct zwp_input_method_v2 *zwp_input_method_v2);
static void im_unavailable(void *data, struct zwp_input_method_v2 *zwp_input_method_v2);
static void redimension_keyboard();
static void show();
static void hide();

/* event handlers */
static const struct zwp_input_method_v2_listener input_method_listener = {
    .activate = im_activate,
    .deactivate = im_deactivate,
    .surrounding_text = im_surrounding_text,
    .text_change_cause = im_text_change_cause,
    .content_type = im_content_type,
    .done = im_done,
    .unavailable = im_unavailable,
};

static const struct wl_pointer_listener pointer_listener = {
    .enter = wl_pointer_enter,
    .leave = wl_pointer_leave,
    .motion = wl_pointer_motion,
    .button = wl_pointer_button,
    .axis = wl_pointer_axis,
};

static const struct wl_touch_listener touch_listener = {
    .down = wl_touch_down,
    .up = wl_touch_up,
    .motion = wl_touch_motion,
    .frame = wl_touch_frame,
    .cancel = wl_touch_cancel,
    .shape = wl_touch_shape,
    .orientation = wl_touch_orientation,
};

static const struct wl_seat_listener seat_listener = {
    .capabilities = seat_handle_capabilities,
    .name = seat_handle_name,
};

void
wl_surface_enter(void *data, struct wl_surface *wl_surface,
                 struct wl_output *wl_output)
{
}

void
wl_surface_leave(void *data, struct wl_surface *wl_surface,
                 struct wl_output *wl_output) {
}

void
wl_preferred_buffer_scale(void *data, struct wl_surface *wl_surface,
                          int scale) {
    keyboard.preferred_scale = scale;
}

void
wl_preferred_buffer_transform(void *data, struct wl_surface *wl_surface,
                              uint32_t transform) {
}

static const struct wl_surface_listener surface_listener = {
    .enter = wl_surface_enter,
    .leave = wl_surface_leave,
    .preferred_buffer_scale = wl_preferred_buffer_scale,
    .preferred_buffer_transform = wl_preferred_buffer_transform,
};

static const struct wl_registry_listener registry_listener = {
    .global = handle_global,
    .global_remove = handle_global_remove,
};

void
initiate_configure(void *data, struct zwlr_layer_surface_v1 *surface,
                   uint32_t serial, uint32_t w, uint32_t h)
{
    available_width = w;
    available_height = h;
    zwlr_layer_surface_v1_ack_configure(surface, serial);
}

void
initiate_closed(void *data, struct zwlr_layer_surface_v1 *surface)
{
}

static const struct zwlr_layer_surface_v1_listener initiate_listener = {
    .configure = initiate_configure,
    .closed = initiate_closed,
};

static const struct zwlr_layer_surface_v1_listener layer_surface_listener = {
    .configure = layer_surface_configure,
    .closed = layer_surface_closed,
};

/* configuration, allows nested code to access above variables */

char *
estrdup(const char *s)
{
    char *p;

    if (!(p = strdup(s))) {
        fprintf(stderr, "strdup:");
        exit(6);
    }

    return p;
}

void
wl_touch_down(void *data, struct wl_touch *wl_touch, uint32_t serial,
              uint32_t time, struct wl_surface *surface, int32_t id,
              wl_fixed_t x, wl_fixed_t y)
{
    if(!layer_surface_configured || !popup_xdg_surface_configured) {
        return;
    }

    struct key *next_key;
    uint32_t touch_x, touch_y;

    touch_x = wl_fixed_to_int(x);
    touch_y = wl_fixed_to_int(y);

    stop_key_repeat();
    kbd_unpress_key(&keyboard, time);

    next_key = kbd_get_key(&keyboard, touch_x, touch_y);
    if (next_key) {
        if (next_key->type == Code && next_key->code == KEY_SPACE) {
            touch_space_key = next_key;
            touch_space_started = time;
            touch_space_x = touch_x;
            touch_space_y = touch_y;
            touch_space_trackpad = false;
            kbd_draw_key(&keyboard, next_key, Press);
        } else if (next_key->flick_label && next_key->flick_label[0]) {
            touch_flick_key = next_key;
            touch_flick_id = id;
            touch_flick_x = touch_x;
            touch_flick_y = touch_y;
            touch_flicked = false;
            kbd_draw_key(&keyboard, next_key, Press);
        } else {
            kbd_press_key(&keyboard, next_key, time);
            start_key_repeat(next_key);
            /* Keys that can move focus or replace the current surface must
             * release before the compositor deactivates the input method. */
            if (next_key->type == Code &&
                (next_key->code == KEY_TAB || next_key->code == KEY_ENTER ||
                 next_key->code == KEY_SYSRQ || next_key->code == KEY_ESC))
                kbd_release_key(&keyboard, time);
        }
    } else if (keyboard.compose) {
        keyboard.compose = 0;
        kbd_switch_layout(&keyboard, keyboard.prevlayout,
                          keyboard.last_abc_index);
    }
}

void
wl_touch_up(void *data, struct wl_touch *wl_touch, uint32_t serial,
            uint32_t time, int32_t id)
{
    if(!layer_surface_configured || !popup_xdg_surface_configured) {
        return;
    }

    stop_key_repeat();
    if (touch_flick_key && touch_flick_id == id) {
        struct key *key = touch_flick_key;
        bool flicked = touch_flicked;
        touch_flick_key = NULL;
        touch_flick_id = -1;
        touch_flicked = false;
        kbd_draw_key(&keyboard, key, Unpress);
        if (flicked)
            kbd_emit_flick(&keyboard, key, time);
        else {
            kbd_press_key(&keyboard, key, time);
            kbd_release_key(&keyboard, time);
        }
        return;
    }
    if (touch_space_key) {
        if (!touch_space_trackpad) {
            kbd_press_key(&keyboard, touch_space_key, time);
            kbd_release_key(&keyboard, time);
        } else {
            kbd_draw_key(&keyboard, touch_space_key, Unpress);
        }
        touch_space_key = NULL;
        touch_space_trackpad = false;
        return;
    }

    kbd_release_key(&keyboard, time);
}

void
wl_touch_motion(void *data, struct wl_touch *wl_touch, uint32_t time,
                int32_t id, wl_fixed_t x, wl_fixed_t y)
{
    if(!layer_surface_configured || !popup_xdg_surface_configured) {
        return;
    }

    uint32_t touch_x, touch_y;

    touch_x = wl_fixed_to_int(x);
    touch_y = wl_fixed_to_int(y);

    if (touch_flick_key && touch_flick_id == id) {
        int dx = (int)touch_x - touch_flick_x;
        int dy = (int)touch_y - touch_flick_y;
        /* Alternate labels live at the top of the key, so the physical
         * gesture follows the label: drag upward to select it. */
        if (!touch_flicked && dy <= -18 && abs(dy) > abs(dx)) {
            touch_flicked = true;
            kbd_draw_key(&keyboard, touch_flick_key, Swipe);
        }
        return;
    }

    if (touch_space_key) {
        int dx = (int)touch_x - touch_space_x;
        int dy = (int)touch_y - touch_space_y;
        if (time - touch_space_started >= 280 &&
            (abs(dx) >= 18 || abs(dy) >= 18)) {
            uint32_t code;
            if (abs(dx) >= abs(dy))
                code = dx < 0 ? KEY_LEFT : KEY_RIGHT;
            else
                code = dy < 0 ? KEY_UP : KEY_DOWN;
            zwp_virtual_keyboard_v1_key(keyboard.vkbd, time, code,
                                        WL_KEYBOARD_KEY_STATE_PRESSED);
            zwp_virtual_keyboard_v1_key(keyboard.vkbd, time, code,
                                        WL_KEYBOARD_KEY_STATE_RELEASED);
            touch_space_x = touch_x;
            touch_space_y = touch_y;
            touch_space_trackpad = true;
        }
        return;
    }

    kbd_motion_key(&keyboard, time, touch_x, touch_y);
}

void
wl_touch_frame(void *data, struct wl_touch *wl_touch)
{
}

void
wl_touch_cancel(void *data, struct wl_touch *wl_touch)
{
    stop_key_repeat();
    if (touch_flick_key)
        kbd_draw_key(&keyboard, touch_flick_key, Unpress);
    touch_flick_key = NULL;
    touch_flick_id = -1;
    touch_flicked = false;
    touch_space_key = NULL;
    touch_space_trackpad = false;
    kbd_release_key(&keyboard, 0);
}

void
wl_touch_shape(void *data, struct wl_touch *wl_touch, int32_t id,
               wl_fixed_t major, wl_fixed_t minor)
{
}

void
wl_touch_orientation(void *data, struct wl_touch *wl_touch, int32_t id,
                     wl_fixed_t orientation)
{
}

void
wl_pointer_enter(void *data, struct wl_pointer *wl_pointer, uint32_t serial,
                 struct wl_surface *surface, wl_fixed_t surface_x,
                 wl_fixed_t surface_y)
{
}

void
wl_pointer_leave(void *data, struct wl_pointer *wl_pointer, uint32_t serial,
                 struct wl_surface *surface)
{
    cur_x = cur_y = -1;
}

void
wl_pointer_motion(void *data, struct wl_pointer *wl_pointer, uint32_t time,
                  wl_fixed_t surface_x, wl_fixed_t surface_y)
{
    if(!layer_surface_configured || !popup_xdg_surface_configured) {
        return;
    }

    cur_x = wl_fixed_to_int(surface_x);
    cur_y = wl_fixed_to_int(surface_y);

    if (cur_press) {
        kbd_motion_key(&keyboard, time, cur_x, cur_y);
    }
}

void
wl_pointer_button(void *data, struct wl_pointer *wl_pointer, uint32_t serial,
                  uint32_t time, uint32_t button, uint32_t state)
{
    if(!layer_surface_configured || !popup_xdg_surface_configured) {
        return;
    }

    struct key *next_key;
    cur_press = state == WL_POINTER_BUTTON_STATE_PRESSED;

    if (cur_press) {
        kbd_unpress_key(&keyboard, time);
    } else {
        kbd_release_key(&keyboard, time);
    }

    if (cur_press && cur_x >= 0 && cur_y >= 0) {
        next_key = kbd_get_key(&keyboard, cur_x, cur_y);
        if (next_key) {
            kbd_press_key(&keyboard, next_key, time);
        } else if (keyboard.compose) {
            keyboard.compose = 0;
            kbd_switch_layout(&keyboard, keyboard.prevlayout,
                              keyboard.last_abc_index);
        }
    }
}

void
wl_pointer_axis(void *data, struct wl_pointer *wl_pointer, uint32_t time,
                uint32_t axis, wl_fixed_t value)
{
    if(!layer_surface_configured || !popup_xdg_surface_configured) {
        return;
    }

    kbd_next_layer(&keyboard, NULL, (value >= 0));
}

void
seat_handle_capabilities(void *data, struct wl_seat *wl_seat,
                         enum wl_seat_capability caps)
{
    if ((caps & WL_SEAT_CAPABILITY_POINTER)) {
        if (pointer == NULL) {
            pointer = wl_seat_get_pointer(wl_seat);
            wl_pointer_add_listener(pointer, &pointer_listener, NULL);
        }
    } else {
        if (pointer != NULL) {
            wl_pointer_destroy(pointer);
            pointer = NULL;
        }
    }
    if ((caps & WL_SEAT_CAPABILITY_TOUCH)) {
        if (touch == NULL) {
            touch = wl_seat_get_touch(wl_seat);
            wl_touch_add_listener(touch, &touch_listener, NULL);
        }
    } else {
        if (touch != NULL) {
            wl_touch_destroy(touch);
            touch = NULL;
        }
    }
}

void
seat_handle_name(void *data, struct wl_seat *wl_seat, const char *name)
{
}

static void
xdg_wm_base_ping(void *data, struct xdg_wm_base *xdg_wm_base, uint32_t serial)
{
    xdg_wm_base_pong(xdg_wm_base, serial);
}

static const struct xdg_wm_base_listener xdg_wm_base_listener = {
    .ping = xdg_wm_base_ping,
};

void
handle_global(void *data, struct wl_registry *registry, uint32_t name,
              const char *interface, uint32_t version)
{
    if (strcmp(interface, wl_compositor_interface.name) == 0) {
        compositor =
            wl_registry_bind(registry, name, &wl_compositor_interface, 6);
    } else if (strcmp(interface, wl_shm_interface.name) == 0) {
        draw_ctx.shm = wl_registry_bind(registry, name, &wl_shm_interface, 1);
    } else if (strcmp(interface, wl_seat_interface.name) == 0) {
        seat = wl_registry_bind(registry, name, &wl_seat_interface, 1);
        wl_seat_add_listener(seat, &seat_listener, NULL);
    } else if (strcmp(interface, zwlr_layer_shell_v1_interface.name) == 0) {
        layer_shell =
            wl_registry_bind(registry, name, &zwlr_layer_shell_v1_interface, 1);
    } else if (strcmp(interface, xdg_wm_base_interface.name) == 0) {
        wm_base = wl_registry_bind(registry, name, &xdg_wm_base_interface, 1);
        xdg_wm_base_add_listener(wm_base, &xdg_wm_base_listener, NULL);
    } else if (strcmp(interface,
                      wp_fractional_scale_manager_v1_interface.name) == 0) {
        wfs_mgr = wl_registry_bind(
            registry, name, &wp_fractional_scale_manager_v1_interface, 1);
    } else if (strcmp(interface, wp_viewporter_interface.name) == 0) {
        viewporter =
            wl_registry_bind(registry, name, &wp_viewporter_interface, 1);
    } else if (strcmp(interface,
                      zwp_virtual_keyboard_manager_v1_interface.name) == 0) {
        vkbd_mgr = wl_registry_bind(
            registry, name, &zwp_virtual_keyboard_manager_v1_interface, 1);
    } else if (im_auto && strcmp(interface, zwp_input_method_manager_v2_interface.name) == 0) {
        im_mgr = wl_registry_bind(registry, name, &zwp_input_method_manager_v2_interface, 1);
    }
}

void
handle_global_remove(void *data, struct wl_registry *registry, uint32_t name)
{
}

static void
xdg_popup_surface_configure(void *data, struct xdg_surface *xdg_surface,
                            uint32_t serial)
{
    xdg_surface_ack_configure(xdg_surface, serial);
    popup_xdg_surface_configured = true;
    drwsurf_attach(&popup_draw_surf);
}

static const struct xdg_surface_listener xdg_popup_surface_listener = {
    .configure = xdg_popup_surface_configure,
};

static void
xdg_popup_configure(void *data, struct xdg_popup *xdg_popup, int32_t x,
                    int32_t y, int32_t width, int32_t height)
{
}

static void
xdg_popup_done(void *data, struct xdg_popup *xdg_popup)
{
}

static const struct xdg_popup_listener xdg_popup_listener = {
    .configure = xdg_popup_configure,
    .popup_done = xdg_popup_done,
};

static void
wp_fractional_scale_preferred_scale(
    void *data, struct wp_fractional_scale_v1 *wp_fractional_scale_v1,
    uint32_t scale)
{
    keyboard.preferred_fractional_scale = (double)scale / 120;
}

static const struct wp_fractional_scale_v1_listener
    wp_fractional_scale_listener = {
        .preferred_scale = wp_fractional_scale_preferred_scale,
};

void
im_activate(void *data, struct zwp_input_method_v2 *zwp_input_method_v2)
{
    fprintf(stderr, "Input method activated\n");
    z13_visibility_activate(&visibility_policy);
    cancel_delayed_hide();
    cancel_touch_reopen();
    show();
}

void
im_deactivate(void *data, struct zwp_input_method_v2 *zwp_input_method_v2)
{
    fprintf(stderr, "Input method deactivated\n");
    z13_visibility_deactivate(&visibility_policy);
    cancel_touch_reopen();
    schedule_delayed_hide();
}

void
im_surrounding_text(void *data, struct zwp_input_method_v2 *zwp_input_method_v2,
                    const char *text, uint32_t cursor, uint32_t anchor)
{
}

void im_text_change_cause(void *data, struct zwp_input_method_v2 *zwp_input_method_v2,
                          uint32_t cause)
{
}

void im_content_type(void *data, struct zwp_input_method_v2 *zwp_input_method_v2,
                     uint32_t hint, uint32_t purpose)
{
}

void
im_done(void *data, struct zwp_input_method_v2 *zwp_input_method_v2)
{
    input_method_serial++;
}

void
im_unavailable(void *data, struct zwp_input_method_v2 *zwp_input_method_v2)
{
}

void
redimension_keyboard()
{
    keyboard.landscape = available_width > available_height;

    enum layout_id layer;
    if (keyboard.landscape) {
        layer = keyboard.landscape_layers[0];
        height = landscape_height;
    } else {
        layer = keyboard.layers[0];
        height = normal_height;
    }

    // Keep the Z13 keyboard centered and comfortably reachable in tablet mode.
    keyboard.w = available_width;
    keyboard.h = height;
    keyboard.layout = &keyboard.layouts[layer];
    keyboard.layer_index = 0;
    keyboard.prevlayout = keyboard.layout;
    keyboard.last_abc_layout = keyboard.layout;
    keyboard.last_abc_index = 0;
}

void
layer_surface_configure(void *data, struct zwlr_layer_surface_v1 *surface,
                        uint32_t serial, uint32_t w, uint32_t h)
{
    // Swallow events for old/destroyed surface
    if (surface != layer_surface) {
        zwlr_layer_surface_v1_ack_configure(surface, serial);
        return;
    };

    // Not what we expected, or redimension, refresh and restart
    if (keyboard.w != w || keyboard.h != h) {
        zwlr_layer_surface_v1_ack_configure(surface, serial);
        hide();
        show();
        return;
    };

    // Swallow useless events
    if (layer_surface_configured) {
        return;
    };
    layer_surface_configured = true;

    double scale = keyboard.preferred_scale;
    if (forced_scale > 0) {
        scale = forced_scale;
    } else if (keyboard.preferred_fractional_scale) {
        scale = keyboard.preferred_fractional_scale;
    }

    keyboard.scale = scale;
    hidden = false;

    if (wfs_mgr && viewporter) {
        wp_viewport_set_destination(draw_surf_viewport, keyboard.w,
                                    keyboard.h);
    } else {
        wl_surface_set_buffer_scale(draw_surf.surf, keyboard.scale);
    }

    popup_draw_surf.surf = wl_compositor_create_surface(compositor);

    xdg_positioner_set_size(popup_xdg_positioner, w, h * 2);
    xdg_positioner_set_anchor_rect(popup_xdg_positioner, 0, -h, w, h * 2);

    wl_surface_set_input_region(popup_draw_surf.surf, empty_region);
    popup_xdg_surface = xdg_wm_base_get_xdg_surface(wm_base, popup_draw_surf.surf);
    popup_xdg_surface_configured = false;
    xdg_surface_add_listener(popup_xdg_surface, &xdg_popup_surface_listener, NULL);
    popup_xdg_popup = xdg_surface_get_popup(popup_xdg_surface, NULL, popup_xdg_positioner);
    xdg_popup_add_listener(popup_xdg_popup, &xdg_popup_listener, NULL);
    zwlr_layer_surface_v1_get_popup(layer_surface, popup_xdg_popup);

    if (wfs_mgr && viewporter) {
        popup_draw_surf_viewport = wp_viewporter_get_viewport(viewporter, popup_draw_surf.surf);
        wp_viewport_set_destination(popup_draw_surf_viewport, keyboard.w, keyboard.h * 2);
    } else {
        wl_surface_set_buffer_scale(popup_draw_surf.surf, keyboard.scale);
    }

    wl_surface_commit(popup_draw_surf.surf);

    zwlr_layer_surface_v1_ack_configure(surface, serial);

    kbd_resize(&keyboard, layouts, NumLayouts);
    drwsurf_attach(&draw_surf);
}

void
layer_surface_closed(void *data, struct zwlr_layer_surface_v1 *surface)
{
    zwlr_layer_surface_v1_destroy(surface);
    wl_surface_destroy(draw_surf.surf);
    run_display = false;
}

void
usage(char *argv0)
{
    fprintf(stderr,
            "usage: %s [-hov] [-H height] [-L landscape height] [-fn font] [-l "
            "layers]\n",
            argv0);
    fprintf(stderr, "Options:\n");
    fprintf(stderr, "  -D          - Enable debug\n");
    fprintf(stderr, "  -o          - Print pressed keys to standard output\n");
    fprintf(stderr,
            "  -O          - Print intersected keys to standard output\n");
    fprintf(stderr, "  -H [int]    - Height in pixels\n");
    fprintf(stderr, "  -L [int]    - Landscape height in pixels\n");
    fprintf(stderr, "  -R [int]    - Rounding radius in pixels\n");
    fprintf(stderr, "  --fn [font] - Set font (e.g: DejaVu Sans 20)\n");
    fprintf(stderr, "  --hidden    - Start hidden (send SIGUSR2 to show)\n");
    fprintf(stderr, "  --no-popup             - Disable the key-press popup\n");
    fprintf(stderr, "  --no-highlight         - Don't highlight a key while pressed\n");
    fprintf(stderr, "  --no-feedback          - Disable all key-press feedback "
                    "(--no-popup and --no-highlight)\n");
    fprintf(
        stderr,
        "  --alpha [int]          - Set alpha value for all colors [0-255]\n");
    fprintf(stderr, "  --auto                 - Automatically toggle visibility based on focus\n");
    fprintf(stderr, "  --scale [number]       - Force the drawing scale (for fractional HiDPI)\n");
    fprintf(stderr, "  --bg [rrggbb|aa]       - Set color of background\n");
    fprintf(stderr, "  --fg [rrggbb|aa]       - Set color of keys\n");
    fprintf(stderr, "  --fg-sp [rrggbb|aa]    - Set color of special keys\n");
    fprintf(stderr, "  --press [rrggbb|aa]    - Set color of pressed keys\n");
    fprintf(stderr,
            "  --press-sp [rrggbb|aa] - Set color of pressed special keys\n");
    fprintf(stderr, "  --swipe [rrggbb|aa]    - Set color of swiped keys\n");
    fprintf(stderr,
            "  --swipe-sp [rrggbb|aa] - Set color of swiped special keys\n");
    fprintf(stderr, "  --text [rrggbb|aa]     - Set color of text on keys\n");
    fprintf(stderr,
            "  --text-sp [rrggbb|aa]  - Set color of text on special keys\n");
    fprintf(stderr,
            "  --text-press [rrggbb|aa]    - Set color of text on pressed keys\n");
    fprintf(stderr,
            "  --text-press-sp [rrggbb|aa] - Set color of text on pressed special keys\n");
    fprintf(stderr,
            "  --text-swipe [rrggbb|aa]    - Set color of text on swiped keys\n");
    fprintf(stderr,
            "  --text-swipe-sp [rrggbb|aa] - Set color of text on swiped special keys\n");
    fprintf(stderr,
            "  --list-layers      - Print the list of available layers\n");
    fprintf(stderr,
            "  -l                 - Comma separated list of layers\n");
    fprintf(stderr, "  --landscape-layers - Comma separated list of "
                    "landscape layers\n");
    fprintf(stderr, "  --non-exclusive    - Allow the keyboard to overlap"
                    " windows. Do not request an exclusive zone from the"
                    "compositor\n");
}

void
list_layers()
{
    int i;
    for (i = 0; i < NumLayouts; i++) {
        if (layouts[i].name) {
            puts(layouts[i].name);
        }
    }
}

void
hide()
{
    if (!layer_surface) {
        return;
    }

    /* Never leave a virtual key latched when focus loss hides the surface. */
    kbd_release_key(&keyboard, 0);
    stop_key_repeat();
    touch_space_key = NULL;
    touch_space_trackpad = false;
    touch_flick_key = NULL;
    touch_flick_id = -1;
    touch_flicked = false;

    if (wfs_draw_surf) {
        wp_fractional_scale_v1_destroy(wfs_draw_surf);
        wfs_draw_surf = NULL;
    }
    if (draw_surf_viewport) {
        wp_viewport_destroy(draw_surf_viewport);
        draw_surf_viewport = NULL;
    }
    if (popup_xdg_popup) {
        xdg_popup_destroy(popup_xdg_popup);
        popup_xdg_popup = NULL;
    }
    if (popup_xdg_surface) {
        xdg_surface_destroy(popup_xdg_surface);
        popup_xdg_surface = NULL;
    }
    if (popup_draw_surf.surf) {
        wl_surface_destroy(popup_draw_surf.surf);
        popup_draw_surf.surf = NULL;
    }

    zwlr_layer_surface_v1_destroy(layer_surface);
    layer_surface = NULL;
    layer_surface_configured = false;

    // Cancel pending frame callback before destroying surface
    if (draw_surf.frame_cb) {
        wl_callback_destroy(draw_surf.frame_cb);
        draw_surf.frame_cb = NULL;
    }

    wl_surface_destroy(draw_surf.surf);
    draw_surf.attached = false;

    hidden = true;
}

void
show()
{
    if (layer_surface) {
        return;
    }

    z13_visibility_shown(&visibility_policy);
    cancel_touch_reopen();

    refresh_available_dimension();
    redimension_keyboard();

    draw_surf.surf = wl_compositor_create_surface(compositor);
    wl_surface_add_listener(
        draw_surf.surf, &surface_listener, NULL);
    if (wfs_mgr && viewporter) {
        wfs_draw_surf = wp_fractional_scale_manager_v1_get_fractional_scale(
            wfs_mgr, draw_surf.surf);
        wp_fractional_scale_v1_add_listener(
            wfs_draw_surf, &wp_fractional_scale_listener, NULL);
        draw_surf_viewport =
            wp_viewporter_get_viewport(viewporter, draw_surf.surf);
    }

    struct wl_output *current_output_data = NULL;

    layer_surface = zwlr_layer_shell_v1_get_layer_surface(
        layer_shell, draw_surf.surf, current_output_data, layer, namespace);

    zwlr_layer_surface_v1_set_size(layer_surface, keyboard.w, height);
    zwlr_layer_surface_v1_set_anchor(layer_surface, anchor);
    if (keyboard.exclusive) {
        zwlr_layer_surface_v1_set_exclusive_zone(layer_surface, height);
    }
    zwlr_layer_surface_v1_set_keyboard_interactivity(layer_surface, false);
    zwlr_layer_surface_v1_add_listener(layer_surface, &layer_surface_listener,
                                       NULL);
    wl_surface_commit(draw_surf.surf);
}

void
toggle_visibility()
{
    if (hidden)
        show();
    else
        hide();
}

void
pipewarn()
{
    fprintf(stderr, "wvkbd: cannot pipe data out.\n");
}

void
set_kbd_colors(uint8_t *bgra, char *hex)
{
    // bg, fg, text, high, swipe
    int length = strlen(hex);
    if (length == 6 || length == 8) {
        char subhex[3] = { 0 };
        memcpy(subhex, hex, 2);
        bgra[2] = (int)strtol(subhex, NULL, 16);
        memcpy(subhex, hex + 2, 2);
        bgra[1] = (int)strtol(subhex, NULL, 16);
        memcpy(subhex, hex + 4, 2);
        bgra[0] = (int)strtol(subhex, NULL, 16);
        if (length == 8) {
            memcpy(subhex, hex + 6, 2);
            bgra[3] = (int)strtol(subhex, NULL, 16);
        }
    }
}

void
refresh_available_dimension()
{
    struct wl_surface *surface = wl_compositor_create_surface(compositor);
    struct zwlr_layer_surface_v1 *layer_surface = zwlr_layer_shell_v1_get_layer_surface(
        layer_shell, surface, NULL, layer, namespace);
    zwlr_layer_surface_v1_set_anchor(layer_surface,
                                     ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP |
                                     ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM |
                                     ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT |
                                     ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT);
    zwlr_layer_surface_v1_add_listener(layer_surface, &initiate_listener, NULL);
    wl_surface_commit(surface);
    wl_display_roundtrip(display);
    zwlr_layer_surface_v1_destroy(layer_surface);
    wl_surface_destroy(surface);
    wl_display_roundtrip(display);
}

int
main(int argc, char **argv)
{
    /* parse command line arguments */
    char *layer_names_list = NULL, *landscape_layer_names_list = NULL;
    char *fc_font_pattern = NULL;
    height = landscape_height = KBD_PIXEL_LANDSCAPE_HEIGHT;
    normal_height = KBD_PIXEL_HEIGHT;

    char *tmp;
    if ((tmp = getenv("WVKBD_LAYERS")))
        layer_names_list = estrdup(tmp);
    if ((tmp = getenv("WVKBD_LANDSCAPE_LAYERS")))
        landscape_layer_names_list = estrdup(tmp);
    if ((tmp = getenv("WVKBD_HEIGHT")))
        normal_height = atoi(tmp);
    if ((tmp = getenv("WVKBD_LANDSCAPE_HEIGHT")))
        landscape_height = atoi(tmp);

    /* keyboard settings */
    keyboard.layers = (enum layout_id *)&layers;
    keyboard.landscape_layers = (enum layout_id *)&landscape_layers;
    keyboard.schemes = schemes;
    keyboard.landscape = true;
    keyboard.layer_index = 0;
    keyboard.preferred_scale = 1;
    keyboard.preferred_fractional_scale = 0;
    keyboard.exclusive = true;
    keyboard.show_popup = true;
    keyboard.show_highlight = true;

    uint8_t alpha = 0;
    bool alpha_defined = false;

    int i;
    for (i = 1; argv[i]; i++) {
        if ((!strcmp(argv[i], "-v")) || (!strcmp(argv[i], "--version"))) {
            printf("wvkbd-%s\n", VERSION);
            exit(0);
        } else if ((!strcmp(argv[i], "-h")) || (!strcmp(argv[i], "--help"))) {
            usage(argv[0]);
            exit(0);
        } else if (!strcmp(argv[i], "-l")) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            if (layer_names_list)
                free(layer_names_list);
            layer_names_list = estrdup(argv[++i]);
        } else if ((!strcmp(argv[i], "-landscape-layers")) ||
                   (!strcmp(argv[i], "--landscape-layers"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            if (landscape_layer_names_list)
                free(landscape_layer_names_list);
            landscape_layer_names_list = estrdup(argv[++i]);
        } else if ((!strcmp(argv[i], "-bg")) || (!strcmp(argv[i], "--bg"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[0].bg.bgra, argv[++i]);
        } else if ((!strcmp(argv[i], "-alpha")) ||
                   (!strcmp(argv[i], "--alpha"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            alpha = atoi(argv[++i]);
            alpha_defined = true;
        } else if ((!strcmp(argv[i], "-fg")) || (!strcmp(argv[i], "--fg"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[0].fg.bgra, argv[++i]);
        } else if ((!strcmp(argv[i], "-fg-sp")) ||
                   (!strcmp(argv[i], "--fg-sp"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[1].fg.bgra, argv[++i]);
        } else if ((!strcmp(argv[i], "-press")) ||
                   (!strcmp(argv[i], "--press"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[0].high.bgra, argv[++i]);
        } else if ((!strcmp(argv[i], "-press-sp")) ||
                   (!strcmp(argv[i], "--press-sp"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[1].high.bgra, argv[++i]);
        } else if ((!strcmp(argv[i], "-swipe")) ||
                   (!strcmp(argv[i], "--swipe"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[0].swipe.bgra, argv[++i]);
        } else if ((!strcmp(argv[i], "-swipe-sp")) ||
                   (!strcmp(argv[i], "--swipe-sp"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[1].swipe.bgra, argv[++i]);
        } else if ((!strcmp(argv[i], "-text")) ||
                   (!strcmp(argv[i], "--text"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[0].text.bgra, argv[++i]);
        } else if ((!strcmp(argv[i], "-text-sp")) ||
                   (!strcmp(argv[i], "--text-sp"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[1].text.bgra, argv[++i]);
        } else if ((!strcmp(argv[i], "-text-press")) ||
                   (!strcmp(argv[i], "--text-press"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[0].text_press.bgra, argv[++i]);
        } else if ((!strcmp(argv[i], "-text-press-sp")) ||
                   (!strcmp(argv[i], "--text-press-sp"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[1].text_press.bgra, argv[++i]);
        } else if ((!strcmp(argv[i], "-text-swipe")) ||
                   (!strcmp(argv[i], "--text-swipe"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[0].text_swipe.bgra, argv[++i]);
        } else if ((!strcmp(argv[i], "-text-swipe-sp")) ||
                   (!strcmp(argv[i], "--text-swipe-sp"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            set_kbd_colors(keyboard.schemes[1].text_swipe.bgra, argv[++i]);
        } else if (!strcmp(argv[i], "-H")) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            normal_height = atoi(argv[++i]);
        } else if (!strcmp(argv[i], "-L")) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            height = landscape_height = atoi(argv[++i]);
        } else if (!strcmp(argv[i], "-R")) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            rounding = atoi(argv[++i]);
        } else if (!strcmp(argv[i], "-D")) {
            keyboard.debug = true;
        } else if ((!strcmp(argv[i], "-fn")) || (!strcmp(argv[i], "--fn"))) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            fc_font_pattern = estrdup(argv[++i]);
        } else if (!strcmp(argv[i], "-o")) {
            keyboard.print = true;
        } else if (!strcmp(argv[i], "-O")) {
            keyboard.print_intersect = true;
        } else if ((!strcmp(argv[i], "-hidden")) ||
                   (!strcmp(argv[i], "--hidden"))) {
            hidden = true;
        } else if ((!strcmp(argv[i], "-no-popup")) ||
                   (!strcmp(argv[i], "--no-popup"))) {
            keyboard.show_popup = false;
        } else if ((!strcmp(argv[i], "-no-highlight")) ||
                   (!strcmp(argv[i], "--no-highlight"))) {
            keyboard.show_highlight = false;
        } else if ((!strcmp(argv[i], "-no-feedback")) ||
                   (!strcmp(argv[i], "--no-feedback"))) {
            keyboard.show_popup = false;
            keyboard.show_highlight = false;
        } else if ((!strcmp(argv[i], "-list-layers")) ||
                   (!strcmp(argv[i], "--list-layers"))) {
            list_layers();
            exit(0);
        } else if ((!strcmp(argv[i], "-non-exclusive")) || (!strcmp(argv[i], "--non-exclusive"))) {
            keyboard.exclusive = false;
        } else if ((!strcmp(argv[i], "-auto")) ||
                   (!strcmp(argv[i], "--auto"))) {
            im_auto = true;
        } else if (!strcmp(argv[i], "--scale")) {
            if (i >= argc - 1) {
                usage(argv[0]);
                exit(1);
            }
            forced_scale = strtod(argv[++i], NULL);
            if (forced_scale <= 0) {
                fprintf(stderr, "Invalid scale: %s\n", argv[i]);
                exit(1);
            }
        } else {
            fprintf(stderr, "Invalid argument: %s\n", argv[i]);
            usage(argv[0]);
            exit(1);
        }
    }

    if (alpha_defined) {
        keyboard.schemes[0].bg.bgra[3] = alpha;
        keyboard.schemes[0].fg.bgra[3] = alpha;
        keyboard.schemes[0].high.bgra[3] = alpha;
        keyboard.schemes[1].bg.bgra[3] = alpha;
        keyboard.schemes[1].fg.bgra[3] = alpha;
        keyboard.schemes[1].high.bgra[3] = alpha;
    }

    if (fc_font_pattern) {
        for (i = 0; i < countof(schemes); i++)
            schemes[i].font = fc_font_pattern;
    }

    if (rounding != DEFAULT_ROUNDING) {
        for (i = 0; i < countof(schemes); i++)
            schemes[i].rounding = rounding;
    }

    display = wl_display_connect(NULL);
    if (display == NULL) {
        die("Failed to create display\n");
    }

    draw_surf.ctx = &draw_ctx;
    draw_surf.back_buffer = &draw_surf_back_buffer;
    draw_surf.display_buffer = &draw_surf_display_buffer;
    popup_draw_surf.ctx = &draw_ctx;
    popup_draw_surf.back_buffer = &popup_draw_surf_back_buffer;
    popup_draw_surf.display_buffer = &popup_draw_surf_display_buffer;
    keyboard.surf = &draw_surf;
    keyboard.popup_surf = &popup_draw_surf;

    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    wl_display_roundtrip(display);

    if (compositor == NULL) {
        die("wl_compositor not available\n");
    }
    if (draw_ctx.shm == NULL) {
        die("wl_shm not available\n");
    }
    if (layer_shell == NULL) {
        die("layer_shell not available\n");
    }
    if (wm_base == NULL) {
        die("wm_base not available\n");
    }
    if (vkbd_mgr == NULL) {
        die("virtual_keyboard_manager not available\n");
    }

    // A second round-trip to receive wl_outputs events
    wl_display_roundtrip(display);

    empty_region = wl_compositor_create_region(compositor);
    popup_xdg_positioner = xdg_wm_base_create_positioner(wm_base);

    keyboard.vkbd =
        zwp_virtual_keyboard_manager_v1_create_virtual_keyboard(vkbd_mgr, seat);
    if (keyboard.vkbd == NULL) {
        die("failed to init virtual keyboard_manager\n");
    }
    #ifdef SHIFT_SPACE_IS_TAB
    keyboard.shift_space_is_tab = true;
    #else
    keyboard.shift_space_is_tab = false;
    #endif

    kbd_init(&keyboard, (struct layout *)&layouts, layer_names_list,
             landscape_layer_names_list);

    if (im_mgr != NULL) {
        input_method = zwp_input_method_manager_v2_get_input_method(im_mgr, seat);
        zwp_input_method_v2_add_listener(input_method, &input_method_listener, NULL);
    }
    keyboard.commit_codepoint = im_commit_codepoint;

    for (i = 0; i < countof(schemes); i++) {
        schemes[i].font_description =
            pango_font_description_from_string(schemes[i].font);
    }

    if (!hidden)
        show();

    struct pollfd fds[6] = {0};
    int WAYLAND_FD = 0;
    int SIGNAL_FD = 1;
    int REPEAT_FD = 2;
    int HIDE_DELAY_FD = 3;
    int TOUCH_DEVICE_FD = 4;
    int TOUCH_REOPEN_FD = 5;
    fds[WAYLAND_FD].events = POLLIN;
    fds[SIGNAL_FD].events = POLLIN;
    fds[REPEAT_FD].events = POLLIN;
    fds[HIDE_DELAY_FD].events = POLLIN;
    fds[TOUCH_DEVICE_FD].events = POLLIN;
    fds[TOUCH_REOPEN_FD].events = POLLIN;

    fds[WAYLAND_FD].fd = wl_display_get_fd(display);
    if (fds[WAYLAND_FD].fd == -1) {
        die("Failed to get wayland_fd: %d\n", errno);
    }

    sigset_t signal_mask;
    sigemptyset(&signal_mask);
    sigaddset(&signal_mask, SIGUSR1);
    sigaddset(&signal_mask, SIGUSR2);
    sigaddset(&signal_mask, SIGRTMIN);
    sigaddset(&signal_mask, SIGPIPE);
    if (sigprocmask(SIG_BLOCK, &signal_mask, NULL) == -1) {
        die("Failed to disable handled signals: %d\n", errno);
    }

    fds[SIGNAL_FD].fd = signalfd(-1, &signal_mask, 0);
    if (fds[SIGNAL_FD].fd == -1) {
        die("Failed to get signalfd: %d\n", errno);
    }

    repeat_fd = timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC | TFD_NONBLOCK);
    if (repeat_fd == -1) {
        die("Failed to create repeat timer: %d\n", errno);
    }
    fds[REPEAT_FD].fd = repeat_fd;

    hide_delay_fd = timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC | TFD_NONBLOCK);
    if (hide_delay_fd == -1) {
        die("Failed to create hide delay timer: %d\n", errno);
    }
    fds[HIDE_DELAY_FD].fd = hide_delay_fd;

    const char *touch_device = getenv("Z13_TOUCH_DEVICE");
    if (!touch_device || !touch_device[0])
        touch_device = "/dev/input/by-path/platform-AMDI0010:00-event";
    touch_device_fd = open(touch_device, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    fds[TOUCH_DEVICE_FD].fd = touch_device_fd;
    if (touch_device_fd < 0)
        fprintf(stderr, "Touch reopen unavailable for %s: %s\n",
                touch_device, strerror(errno));
    else
        fprintf(stderr, "Touch reopen monitoring %s\n", touch_device);

    touch_reopen_fd = timerfd_create(CLOCK_MONOTONIC,
                                     TFD_CLOEXEC | TFD_NONBLOCK);
    if (touch_reopen_fd == -1) {
        die("Failed to create touch reopen timer: %d\n", errno);
    }
    fds[TOUCH_REOPEN_FD].fd = touch_reopen_fd;

    while (run_display) {
        wl_display_flush(display);
        poll(fds, countof(fds), -1);

        if (fds[WAYLAND_FD].revents & POLLIN)
            wl_display_dispatch(display);
        if (fds[WAYLAND_FD].revents & POLLERR) {
            die("Exceptional condition on wayland socket.\n");
        }
        if (fds[WAYLAND_FD].revents & POLLHUP) {
            die("Wayland socket has been disconnected.\n");
        }

        if (fds[SIGNAL_FD].revents & POLLIN) {
            struct signalfd_siginfo si;

            if (read(fds[SIGNAL_FD].fd, &si, sizeof(si)) != sizeof(si))
                fprintf(stderr, "Signal read error: %d", errno);
            else if (si.ssi_signo == SIGUSR1) {
                z13_visibility_manual_hide(&visibility_policy);
                fprintf(stderr, "Manually hiding keyboard\n");
                hide();
            } else if (si.ssi_signo == SIGUSR2)
                show();
            else if (si.ssi_signo == SIGRTMIN)
                toggle_visibility();
            else if (si.ssi_signo == SIGPIPE)
                pipewarn();
        }

        if (fds[REPEAT_FD].revents & POLLIN) {
            uint64_t expirations = 0;
            if (read(repeat_fd, &expirations, sizeof(expirations)) == sizeof(expirations) &&
                repeat_key && keyboard.last_press == repeat_key) {
                for (uint64_t n = 0; n < expirations; n++) {
                    zwp_virtual_keyboard_v1_key(keyboard.vkbd, 0, repeat_key->code,
                                                WL_KEYBOARD_KEY_STATE_RELEASED);
                    zwp_virtual_keyboard_v1_key(keyboard.vkbd, 0, repeat_key->code,
                                                WL_KEYBOARD_KEY_STATE_PRESSED);
                }
            }
        }

        if (fds[HIDE_DELAY_FD].revents & POLLIN) {
            uint64_t expirations = 0;
            if (read(hide_delay_fd, &expirations, sizeof(expirations)) == sizeof(expirations)) {
                z13_visibility_automatic_hide(&visibility_policy);
                hide();
            }
        }

        if (fds[TOUCH_DEVICE_FD].revents & POLLIN) {
            struct input_event event;
            while (read(touch_device_fd, &event, sizeof(event)) == sizeof(event)) {
                if (event.type == EV_KEY && event.code == BTN_TOUCH) {
                    if (z13_visibility_touch_event(&visibility_policy, hidden,
                                                   event.value == 1)) {
                        fprintf(stderr, "Touch while manually hidden; waiting for focus result\n");
                        schedule_touch_reopen();
                    }
                }
            }
        }

        if (fds[TOUCH_REOPEN_FD].revents & POLLIN) {
            uint64_t expirations = 0;
            if (read(touch_reopen_fd, &expirations, sizeof(expirations)) ==
                    sizeof(expirations) &&
                z13_visibility_reopen_after_touch_delay(&visibility_policy,
                                                        hidden)) {
                fprintf(stderr, "Reopening keyboard after same-field touch\n");
                show();
            }
        }
    }

    if (fc_font_pattern) {
        free((void *)fc_font_pattern);
        for (i = 0; i < countof(schemes); i++)
            schemes[i].font = NULL;
    }

    return 0;
}
