#!/usr/bin/env bash

set -euo pipefail

systemctl --user disable --now \
  z13-keyboard-watch.path z13-keyboard-state.service z13-osk.service \
  2>/dev/null || true

rm -f -- \
  "$HOME/.local/bin/z13-osk" \
  "$HOME/.local/bin/z13-theme" \
  "$HOME/.local/bin/z13-keyboard-state" \
  "$HOME/.local/libexec/z13-osk/wvkbd-z13" \
  "$HOME/.config/omarchy/hooks/theme-set.d/50-z13-osk" \
  "$HOME/.config/systemd/user/z13-osk.service" \
  "$HOME/.config/systemd/user/z13-keyboard-state.service" \
  "$HOME/.config/systemd/user/z13-keyboard-watch.path"

rmdir -- "$HOME/.local/libexec/z13-osk" \
  2>/dev/null || true
systemctl --user daemon-reload
systemctl --user start omarchy-fcitx5.service

printf 'z13 touch keyboard uninstalled\n'
