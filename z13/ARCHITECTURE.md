# Z13 touch keyboard architecture

## Objective

Provide one predictable Danish touch keyboard for the ROG Flow Z13 under
Omarchy/Hyprland.  It should feel familiar to an iPad user while retaining the
desktop keys Linux applications need.  Application input hints must never
replace the selected layout.

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
| 1 | `q w e r t y u i o p å` |
| 2 | `a s d f g h j k l æ ø` |
| 3 | `Shift z x c v b n m Backspace` |
| 4 | `123 FN SUPER Space . Return Hide` |

`æ` precedes `ø`, matching the supplied iPadOS reference.  Shift is one-shot;
double-tap Shift toggles Caps Lock.  The `SUPER` key is the Linux equivalent of
the Command key and is one-shot, so `SUPER`, then `W`, closes a window without
requiring two simultaneous fingers.

### Numbers

| Row | Keys |
| --- | --- |
| 1 | `1 2 3 4 5 6 7 8 9 0` |
| 2 | `- / : ; ( ) kr & @ \"` |
| 3 | `#+= . , ? ! ' Backspace` |
| 4 | `ABC FN SUPER Space . Return Hide` |

### Symbols

| Row | Keys |
| --- | --- |
| 1 | `[ ] { } # % ^ * + =` |
| 2 | `_ \\ | ~ < > € £ ¥ •` |
| 3 | `` ` · √ π ÷ × § © ® Backspace `` |
| 4 | `123 ABC FN SUPER Space Return Hide` |

### Functions

| Row | Keys |
| --- | --- |
| 1 | `ESC F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 DEL` |
| 2 | `TAB INS HOME END PGUP PGDN Backspace Return` |
| 3 | `CTRL SUPER ALT ALTGR SHIFT Up` |
| 4 | `UNDO CUT COPY PASTE SHOT Left Down Right` |
| 5 | `ABC 123 Space Hide` |

Function labels are uppercase.  Modifier keys latch for exactly one following
key unless tapped again.  Backspace and Delete repeat while held.

## iPad-inspired interactions

- Tap a text field: show once through `zwp_input_method_v2`.
- Leave text input: wait 500 ms before hiding to avoid Enter/focus flicker.
- Tap the same focused field after manual hide: show again.
- Tap Shift: uppercase the next character; double-tap: Caps Lock.
- Swipe down on a letter with an alternate label: enter that alternate symbol.
- Hold Space for 280 ms and drag: move the caret using arrow events.
- Hold Backspace or Delete: repeat after 420 ms, then every 55 ms.
- Tap Hide: hide without changing focus or layout.
- No magnified key popup; pressed-key highlight remains enabled.

The alternate-symbol map is declared per key in `layout.json`.  Gesture code
must never contain Danish labels or key positions.

## Geometry and theme

- Keyboard layer reserves 340 logical pixels at the bottom.
- Visible panel width is 92% of the display and is centred; the outer 4% on
  each side remains transparent while application windows are resized above it.
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

## Verification gate

Installation is not complete until all checks pass:

1. JSON schema/generator test, cover-state transition test and clean compilation.
2. `systemd-analyze --user verify` for every unit.
3. Attach, detach, attach and detach again without duplicate processes.
4. Auto-show, auto-hide, manual hide and same-field re-show in ChatGPT, Chrome,
   Zen, a terminal and a native GTK application.
5. Every key in all four views emits the documented event.
6. One-shot Shift, double-tap Caps Lock, SUPER shortcuts and held Delete work.
7. Light and dark screenshots show crisp text, centred 92% geometry and the
   correct Catppuccin palette.
8. Suspend/resume while detached and attached restores the correct state.
9. Uninstall returns to Fcitx with no active OSK units or files.

## Upstream references

- wvkbd: <https://git.sr.ht/~proycon/wvkbd>
- Hyprland input variables: <https://wiki.hypr.land/Configuring/Basics/Variables/>
- Apple iPad keyboard behaviour: <https://support.apple.com/guide/ipad/type-with-the-onscreen-keyboard-ipad997da459/ipados>
