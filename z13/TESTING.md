# Z13 runtime acceptance test

Run this list in order after installing with `z13/install.sh`.

1. With the cover attached, `omarchy-fcitx5.service` is active and
   `z13-osk.service` is inactive.
2. Detach the cover.  `z13-osk.service` becomes active exactly once and Fcitx
   stops.  The keyboard remains hidden until a text field is touched.
3. In ChatGPT, Zen, Chromium, a terminal and a native GTK application:
   touch a field, type Danish text, press Return, wait 500 ms, tap Hide, and
   touch the same field directly without scrolling or changing focus first.
   The keyboard must reappear exactly once after the short touch delay.  Hide
   again and tap outside all text fields; focus loss must cancel the pending
   reopen without a flash.  Repeat after an automatic focus-loss hide; it must
   remain hidden until a field activates again.
4. Confirm the four fixed layers and their labels against `layout.json`.
5. Confirm one-shot Shift, double-tap Caps Lock, Super then `W`, held
   Backspace (`⌫`), held forward Delete (`⌦`), upward alternate flicks and
   hold/drag Space.  Flick `$`, `?` and at least eight other symbols: every
   value must arrive through input-method text commit; none may open a context
   menu or leave blue feedback behind, the journal must contain no pixman
   rectangle warnings, and every key must still render.
6. Open `#+=` directly from the bottom row and tap `☺`; Omarchy's native emoji
   overlay must open and insert the chosen emoji into the previous text field.
7. On the FN view, tap F1–F12 for normal function keys and flick each upward to
   verify speaker mute, volume down/up, microphone mute, ROG profile,
   screenshot, brightness down/up, display menu, touchpad, keyboard light and
   airplane mode.  Test airplane mode last because it disconnects networking.
8. Confirm the light and dark Catppuccin palettes after a theme switch.
9. Attach, detach, attach and detach once more.  At every point there must be
   exactly one input-method process appropriate to the current mode.
10. Suspend/resume once attached and once detached, then repeat steps 1–3.
11. Verify the transparent topbar and its touch toggle independently; the OSK
   install does not own or modify topbar files.

Only after all checks pass may the pre-rebuild archive be deleted.
