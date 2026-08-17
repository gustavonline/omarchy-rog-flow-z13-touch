# Z13 touch keyboard architecture

## Objective

Provide one predictable Danish touch keyboard for the ROG Flow Z13 under
Omarchy/Hyprland.  It combines the Nordic Z13 cover's ISO row structure with
touch-first gestures inspired by iPadOS while retaining the desktop keys Linux
applications need.  Application input hints must never replace the selected
layout.

The implementation is pinned to upstream wvkbd 0.20 (`6b41504`) on the
`z13-ipados` branch.  Upstream remains the Git remote and all Z13 changes stay
reviewable as a small commit series.

## Boundaries

The solution has five independent layers:

1. `wvkbd`: Wayland input, rendering and input-method protocol only.
2. `z13/layout.json`: all key positions, labels, actions and alternate symbols.
3. `z13/runtime/z13-theme`: validated colour roles from Omarchy's active theme.
4. `z13/systemd/`: cover detection, process ownership and theme reload only.
5. Root and `plugins/`: Omarchy bar widgets and touch-only shell interaction.

No layer may contain values owned by another layer.  Generated C headers are
build artefacts and must never be edited by hand.

The renderer honours Hyprland's fractional-scale event even when it arrives
after the first layer configure.  In that ordering case the surface is recreated
once at the preferred scale, preventing the initial 1x buffer from being
stretched and making text appear soft on the Z13's 1.6x panel.

## Installed footprint

The installer may create only these active user files:

- `~/.local/bin/z13-osk`
- `~/.local/bin/z13-theme`
- `~/.local/bin/z13-keyboard-state`
- `~/.local/libexec/z13-osk/wvkbd-z13`
- `~/.config/omarchy/hooks/theme-set.d/50-z13-osk`
- `~/.config/systemd/user/z13-osk.service`
- `~/.config/systemd/user/z13-keyboard-state.service`
- `~/.config/systemd/user/z13-keyboard-watch.path`
- `~/.local/bin/z13-tablet-rotation`
- `~/.config/systemd/user/z13-tablet-rotation.service`
- `~/.config/omarchy/plugins/io.github.gustavonline.z13-touch-tray/`
- `~/.config/omarchy/plugins/io.github.gustavonline.z13-touch-indicators/`
- `~/.config/omarchy/plugins/io.github.gustavonline.z13-touch-active-window/`

The setup script also replaces only the relevant bar-widget IDs in
`~/.config/omarchy/shell.json`; the removal script restores Omarchy's stock
tray, indicators and active-window widgets.

The source repository lives at
`~/.config/omarchy/plugins/io.github.gustavonline.rog-flow-z13-touch`. One
idempotent setup script and one removal script own the complete footprint.

## Layout contract

All applications use the same four views.  App-specific URL, terminal, PIN or
email layouts are intentionally unsupported.

### Letters

| Row | Keys |
| --- | --- |
| 1 | `Escape 1 2 3 4 5 6 7 8 9 0 - + Backspace` |
| 2 | `Tab q w e r t y u i o p å [ ]` |
| 3 | `Caps a s d f g h j k l æ ø Return` |
| 4 | `Shift z x c v b n m , . - Shift` |
| 5 | `Emoji Omarchy Dictation Space .?123 #+= Hide` |

All character, number and punctuation keys use exactly the same width.  The
visible functional keys create the physical stagger without invisible padding:
the Q row begins at 1u, A at 1.5u and Z at 2u.  Rare ISO dead keys are available
on the symbol layer instead of occupying the main view.  Shift is strictly
one-shot; only the dedicated Caps key locks capitals.  The Omarchy/Super key
uses Omarchy's packaged `U+E900` logo glyph and is one-shot, so Super, then `W`,
closes a window without requiring two simultaneous fingers.  Escape follows the
physical ROG cover and reads `ESC`.  Longer control labels use explicit per-key
scales and bold weight instead of changing the legible size of ordinary
letters.  Tab remains as `⇥` because it is useful in forms, terminals and code
editors.  Both sides of the alphabetic row provide one-shot Shift.  There is no
touch `FN` modifier: the main view exposes numbers and symbols directly, while
an explicitly named `F1–12` page link lives on both secondary character views.
Desktop modifiers and arrows live only on that F1–12 view.

Square brackets occupy the two former upper-Return positions; flicking them up
produces curly braces.  Return is a normal rectangular 1.5u key on the home row.
The touch layout intentionally provides only Backspace; forward Delete adds no
useful tablet workflow and is omitted.

### Numbers

| Row | Keys |
| --- | --- |
| 1 | `1 2 3 4 5 6 7 8 9 0 Backspace` |
| 2 | `- / : ; ( ) kr & @ \" Return` |
| 3 | `. , ? ! ' ... #+=` |
| 4 | `Emoji Omarchy Dictation Space ABC F1–12 Hide` |

### Symbols

| Row | Keys |
| --- | --- |
| 1 | `[ ] { } # % ^ * + = Backspace` |
| 2 | `_ \\ | ~ < > € £ ¥ • Return` |
| 3 | `` ` ½ √ π ÷ × § © ® ... .?123 `` |
| 4 | `Emoji Omarchy Dictation Space F1–12 ABC Hide` |

### F1–12 / ROG tools

| Row | Keys |
| --- | --- |
| 1 | `ESC F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 Backspace` |
| 2 | `Tab Caps INS HOME END PGUP PGDN ... Up ... Return` |
| 3 | `Shift CTRL ALT ALT GR ... Left Down Right` |
| 4 | `Emoji Omarchy Dictation Space ABC .?123 Hide` |

The page link says `F1–12`, not `FN`, because it opens a tool view rather than
modifying another key.  Flicking F1–F12 upward emits the same hardware
actions as the Nordic ROG cover: speaker mute, volume down/up, microphone mute,
ROG profile, screenshot, display brightness down/up, display menu, touchpad,
keyboard light and airplane mode.  The 0.8u arrows form a compact physical
inverted-T cluster just left of Return, with Up centred exactly above Down.
Shift is the first desktop modifier;
Ctrl, Alt and Alt Gr follow it.  The duplicated Super key is omitted because
the persistent Omarchy key already occupies the second bottom slot.  Modifiers
latch for exactly one following key unless tapped again.  Caps Lock remains
active until toggled.  Backspace (`⌫`) is top-right, Return is right-aligned
beneath it, and Backspace repeats while held.

Every view uses the same seven-slot bottom strip and the same widths:
`Emoji Omarchy Dictation Space page page Hide`.  Omarchy therefore remains
centered between the two other left-side actions, Space never moves, and only
the two page destinations change.  `ABC`, `.?123`, `#+=` and `F1–12` are all
1.5u navigation keys.  On Numbers and Symbols, Backspace is the sole edit key
at the top right and Return sits directly beneath it; neither is duplicated in
the character rows.

The Numbers and Symbols views preserve the two home-page destination slots:
Numbers places `ABC` then `F1–12` in them, while Symbols places `F1–12` then
`ABC`.  The remaining sibling route lives as the rightmost key in the content
area.  All four views render on a five-row grid, bottom anchored, so switching
pages never changes key height or moves the persistent bottom strip.

## iPad-inspired interactions

- Tap a text field: show once through `zwp_input_method_v2`.
- Leave text input: wait 500 ms before hiding to avoid Enter/focus flicker.
- Tap the same focused field after manual hide: the Z13 touchscreen event arms
  a 140 ms delayed reopen.  A real focus change cancels it through
  `zwp_input_method_v2.deactivate`; an unchanged field remains active and
  reopens exactly once.  The Hide gesture itself is ignored through its touch
  release, and automatic focus-loss hiding never arms this path.  The stable
  `/dev/input/by-path/platform-AMDI0010:00-event` link is used, with
  `Z13_TOUCH_DEVICE` available as a test or hardware override.
- Tap Shift: uppercase the next character.  Repeated Shift taps never lock;
  use the dedicated Caps key for Caps Lock.
- Flick up on a number-row key to enter its visible alternate: `! @ # $ % & / (
  ) = _ ?`; the bracket keys similarly produce `{ }`, and the punctuation keys
  produce `; : _`.  Rare symbols remain on `.?123`/`#+=`.  Hardware alternates
  remain on
  the FN row. Text symbols normally use `zwp_input_method_v2.commit_string`,
  so asynchronous Electron clients cannot turn `$`, `?` or `@` into a context
  menu. Password and PIN fields are the deliberate exception: clients may
  reject secure input-method commits, so those purposes use the existing
  physical-style virtual-keyboard fallback. The full layout is redrawn after
  every flick, preventing stale blue swipe feedback.
- Hold Space for 280 ms and drag: move the caret using arrow events.
- Hold Backspace or Delete: repeat after 420 ms, then every 55 ms.
- Tap Emoji on the main view: open Omarchy's built-in emoji overlay through its
  supported `Super+Ctrl+E` binding.
- Tap Dictation on the main view: invoke this installation's native
  `Super+Ctrl+X` toggle-dictation binding.
- Tap Hide: hide without changing focus or layout; the next touchscreen tap is
  resolved by the delayed focus-aware rule above.
- No magnified key popup; pressed-key highlight remains enabled.

The alternate-symbol map is declared per key in `layout.json`.  Gesture code
must never contain Danish labels or key positions.

## Geometry and theme

- Keyboard layer reserves 360 logical pixels at the bottom.
- Visible panel follows Omarchy's normal outer gap (0.8% per side) while the
  full-width layer keeps application windows resized above it.
- Outer panel corners remain square to match Omarchy windows.
- Key corners are 10 logical pixels with equal 6-pixel internal gaps.
- Font is `Inter 19`; rendering follows the compositor scale without a second
  manual rescale.
- Palette roles come from the active Omarchy theme's `colors.toml`.
- Theme changes restart only `z13-osk.service`; layout and device state are
  untouched.

## Device and service model

The cover identity is the stable udev path:

`/dev/input/by-id/usb-ASUSTeK_Computer_Inc._GZ302EA-Keyboard-if02-event-kbd`

`z13-keyboard-watch.path` watches `/dev/input/by-id` rather than polling
Hyprland every second.  Its one-shot state service applies exactly one state:

- cover present: stop `z13-osk.service`, start `omarchy-fcitx5.service`;
- cover absent: stop Fcitx, start `z13-osk.service`.

The same event-driven transition writes `z13-cover-state` under
`$XDG_RUNTIME_DIR`. The two topbar wrappers watch that file: with the cover
attached they retain Omarchy's stock hover behaviour, while a detached cover
enables persistent one-tap indicator and tray drawers. No polling service is
introduced.

The OSK service has a negated `ConditionPathExists` for the cover, owns the
single keyboard process and uses `Restart=on-failure`.  Omarchy's supported
`theme-set` hook restarts the OSK only when it is already active.  There is no
timer, polling loop, Hyprland override or edit under `/usr/share/omarchy`.
The state script accepts test-only environment overrides, allowing both cover
transitions to be verified without spoofing or removing a real `/dev` device.
The installer uses the same state script with `Z13_OSK_ACTION=restart`, so a
detached keyboard immediately adopts a newly installed binary; ordinary cover
events keep the non-disruptive `start` action.

## Verification gate

Installation is not complete until all checks pass:

1. JSON schema/generator test, cover-state transition test and clean compilation.
2. `systemd-analyze --user verify` for every unit.
3. Attach, detach, attach and detach again without duplicate processes.
4. Auto-show, auto-hide, manual hide and direct same-field re-show in ChatGPT,
   Chrome, Zen, a terminal and a native GTK application.  A same-field tap must
   log the delayed touch reopen; a tap outside text input must deactivate and
   cancel it without flashing the keyboard.
5. Every key in all four views emits the documented event; every visible corner
   symbol is actionable through an upward flick, including all twelve ROG
   hardware actions.
6. One-shot Shift, direct/double-tap Caps Lock, Super shortcuts and held Delete
   work.
7. Light and dark screenshots show crisp text, Omarchy-gap geometry and the
   correct Catppuccin palette.
8. Suspend/resume while detached and attached restores the correct state.
9. Uninstall returns to Fcitx with no active OSK units or files.

## Upstream references

- wvkbd: <https://git.sr.ht/~proycon/wvkbd>
- Hyprland input variables: <https://wiki.hypr.land/Configuring/Basics/Variables/>
- ASUS ROG Flow Z13 gallery: <https://rog.asus.com/us/laptops/rog-flow/rog-flow-z13-2025/gallery/>
- Danish XKB symbols: `/usr/share/X11/xkb/symbols/dk`
- Apple iPad keyboard behaviour: <https://support.apple.com/guide/ipad/type-with-the-onscreen-keyboard-ipad997da459/ipados>
