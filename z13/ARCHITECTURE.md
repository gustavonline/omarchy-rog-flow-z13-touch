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

The solution has four independent layers:

1. `wvkbd`: Wayland input, rendering and input-method protocol only.
2. `z13/layout.json`: all key positions, labels, actions and alternate symbols.
3. `z13/theme.env`: Catppuccin colour tokens only.
4. `z13/systemd/`: cover detection, process ownership and theme reload only.

No layer may contain values owned by another layer.  Generated C headers are
build artefacts and must never be edited by hand.

## Installed footprint

The installer may create only these active user files:

- `~/.local/bin/z13-osk`
- `~/.local/bin/z13-keyboard-state`
- `~/.local/libexec/z13-osk/wvkbd-z13`
- `~/.config/omarchy/z13-keyboard/theme.env`
- `~/.config/omarchy/hooks/theme-set.d/50-z13-osk`
- `~/.config/systemd/user/z13-osk.service`
- `~/.config/systemd/user/z13-keyboard-state.service`
- `~/.config/systemd/user/z13-keyboard-watch.path`

The source repository lives at `~/.local/src/z13-touch-keyboard`.  One
idempotent installer and one uninstaller own the complete footprint.

## Layout contract

All applications use the same four views.  App-specific URL, terminal, PIN or
email layouts are intentionally unsupported.

### Letters

| Row | Keys |
| --- | --- |
| 1 | `... 1 2 3 4 5 6 7 8 9 0 - + ...` |
| 2 | `Tab q w e r t y u i o p å Backspace` |
| 3 | `Shift a s d f g h j k l æ ø Return` |
| 4 | `z x c v b n m , . -` |
| 5 | `123 FN Super Space #+= Hide` |

All character, number and punctuation keys use exactly the same width.  Rare
ISO dead keys are available on the symbol layer instead of occupying the main
view.  Shift is one-shot; double-tap Shift toggles Caps Lock.  The Windows
glyph is the Linux Super key and is one-shot, so Super, then `W`, closes a
window without requiring two simultaneous fingers.  Tab remains as the compact
`⇥` symbol because it is useful in forms, terminals and code editors.  Desktop
modifiers and arrows live only on the function view.

### Numbers

| Row | Keys |
| --- | --- |
| 1 | `1 2 3 4 5 6 7 8 9 0 Backspace` |
| 2 | `- / : ; ( ) kr & @ \"` |
| 3 | `#+= . , ? ! ' Backspace Return` |
| 4 | `ABC FN Super Space #+= Hide` |

### Symbols

| Row | Keys |
| --- | --- |
| 1 | `[ ] { } # % ^ * + =` |
| 2 | `_ \\ | ~ < > € £ ¥ •` |
| 3 | `` ` · √ π ÷ × § © ® Backspace Return `` |
| 4 | `123 ABC FN Super Space Emoji Hide` |

### Functions

| Row | Keys |
| --- | --- |
| 1 | `ESC F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 Delete` |
| 2 | `Tab Caps INS HOME END PGUP PGDN Backspace Return ... Up` |
| 3 | `CTRL Super ALT ALT GR Shift ... Left Down Right` |
| 4 | `ABC 123 #+= Space Hide` |

Function labels are uppercase.  Flicking F1–F12 upward emits the same hardware
actions as the Nordic ROG cover: speaker mute, volume down/up, microphone mute,
ROG profile, screenshot, display brightness down/up, display menu, touchpad,
keyboard light and airplane mode.  The arrows form the physical inverted-T
cluster at the far right.  Shift, Ctrl, Alt, Alt Gr and Super latch for exactly
one following key unless tapped again.  Caps Lock remains active until toggled.
Backspace (`⌫`) deletes left, while Delete (`⌦`) deletes right; both repeat
while held.

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
- Tap Shift: uppercase the next character; double-tap: Caps Lock.
- Flick up on a key with an alternate label: preview and enter its literal
  symbol or hardware action.  Text symbols use
  `zwp_input_method_v2.commit_string`, never a temporary COMP/Menu keymap, so
  asynchronous Electron clients cannot turn `$`, `?` or `@` into a context
  menu.  The full layout is redrawn after every flick, preventing stale blue
  swipe feedback.
- Hold Space for 280 ms and drag: move the caret using arrow events.
- Hold Backspace or Delete: repeat after 420 ms, then every 55 ms.
- Tap Emoji on the symbol view: open Omarchy's built-in emoji overlay through
  its supported `Super+Ctrl+E` binding.
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
- Light palette: Catppuccin Latte.
- Dark palette: Catppuccin Macchiato.
- Theme changes restart only `z13-osk.service`; layout and device state are
  untouched.

## Device and service model

The cover identity is the stable udev path:

`/dev/input/by-id/usb-ASUSTeK_Computer_Inc._GZ302EA-Keyboard-if02-event-kbd`

`z13-keyboard-watch.path` watches `/dev/input/by-id` rather than polling
Hyprland every second.  Its one-shot state service applies exactly one state:

- cover present: stop `z13-osk.service`, start `omarchy-fcitx5.service`;
- cover absent: stop Fcitx, start `z13-osk.service`.

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
