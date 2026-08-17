# Z13 runtime acceptance test

Run this list in order after installing with `z13/install.sh`.

1. With the cover attached, `omarchy-fcitx5.service` is active and
   `z13-osk.service` is inactive.
2. Detach the cover.  `z13-osk.service` becomes active exactly once and Fcitx
   stops.  The keyboard remains hidden until a text field is touched.
3. In ChatGPT, Zen, Chromium, a terminal and a native GTK application:
   touch a field, type Danish text, press Return, wait 500 ms, and touch the
   same field again.  Show/hide must be stable and app-independent.
4. Confirm the four fixed layers and their labels against `layout.json`.
5. Confirm one-shot Shift, double-tap Caps Lock, Super then `W`, held
   Backspace/Delete, upward alternate flicks and hold/drag Space.  After at
   least ten flicks, the journal must contain no pixman rectangle warnings and
   every key must still render.
6. Confirm the light and dark Catppuccin palettes after a theme switch.
7. Attach, detach, attach and detach once more.  At every point there must be
   exactly one input-method process appropriate to the current mode.
8. Suspend/resume once attached and once detached, then repeat steps 1–3.
9. Verify the transparent topbar and its touch toggle independently; the OSK
   install does not own or modify topbar files.

Only after all checks pass may the pre-rebuild archive be deleted.
