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
   Immediately after a service restart, show the keyboard once and confirm the
   journal settles on `Resize 1600x360 1.600000`; labels must be sharp on that
   very first appearance rather than only after hiding and reopening it.
5. Confirm that Return is one rectangular key on the home row.  Confirm the two
   bracket keys type `[ ]` and flick upward to type `{ }`.  Confirm one-shot
   left and right Shift, verify that double-tapping Shift does not lock, then
   verify direct Caps Lock, Omarchy/Super then `W`, held Backspace (`⌫`) and
   upward alternate flicks
   and hold/drag Space.  Flick the complete number-row set
   `! @ # $ % & / ( ) = _ ?` plus `{ }` and `; : _`: every
   value must arrive through input-method text commit; none may open a context
   menu or leave blue feedback behind, the journal must contain no pixman
   rectangle warnings, and every key must still render.
6. Tap `☻` on the main view; Omarchy's native emoji overlay must open and insert
   the chosen emoji into the previous text field.  Tap the microphone and verify
   that Omarchy's native toggle-dictation action opens.
7. Visit all four pages and confirm the bottom strip never moves: Emoji,
   Omarchy, Dictation, Space, two page choices and Hide must occupy the same
   seven slots.  Confirm `ABC`, `.?123`, `#+=` and `F1–12` have equal physical
   width.  Numbers and Symbols must each have exactly one Backspace at the top
   right and one Return directly beneath it.  No page may contain a button
   labelled `FN`, and every page must remain reachable in at most two taps.
   On F1–12, confirm there is no forward Delete or duplicated Omarchy key;
   Backspace must be top-right, Return right-aligned beneath it, Shift the first
   desktop modifier, and the arrow cluster compact and inset.  Then tap each key
   for its normal function and flick each upward to
   verify speaker mute, volume down/up, microphone mute, ROG profile,
   screenshot, brightness down/up, display menu, touchpad, keyboard light and
   airplane mode.  Test airplane mode last because it disconnects networking.
8. Switch between two visually different Omarchy themes. Confirm that panel,
   character keys, function keys, pressed state, flick state and labels follow
   each theme without retaining colours from the previous one.
9. Attach, detach, attach and detach once more.  At every point there must be
   exactly one input-method process appropriate to the current mode.
10. Suspend/resume once attached and once detached, then repeat steps 1–3.
11. Verify the transparent topbar, keyboard icon, indicator reveal, tray reveal
   and active-window close control. Each touch must produce one state change.

Only after all checks pass may the pre-rebuild archive be deleted.
