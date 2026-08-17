#!/usr/bin/env bash

set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

python3 "$repo/z13/tools/verify_layout.py" "$repo/z13/layout.json"
"$repo/z13/tools/verify_runtime.sh"
python3 "$repo/z13/tools/generate_layout.py" \
  "$repo/z13/layout.json" "$repo/layout.z13.h"
make -C "$repo" LAYOUT=z13

install -Dm755 "$repo/wvkbd-z13" \
  "$HOME/.local/libexec/z13-osk/wvkbd-z13"
install -Dm755 "$repo/z13/runtime/z13-osk" "$HOME/.local/bin/z13-osk"
install -Dm755 "$repo/z13/runtime/z13-keyboard-state" \
  "$HOME/.local/bin/z13-keyboard-state"
install -Dm644 "$repo/z13/theme.env" \
  "$HOME/.config/omarchy/z13-keyboard/theme.env"
install -Dm755 "$repo/z13/runtime/50-z13-osk" \
  "$HOME/.config/omarchy/hooks/theme-set.d/50-z13-osk"
install -Dm644 "$repo/z13/systemd/z13-osk.service" \
  "$HOME/.config/systemd/user/z13-osk.service"
install -Dm644 "$repo/z13/systemd/z13-keyboard-state.service" \
  "$HOME/.config/systemd/user/z13-keyboard-state.service"
install -Dm644 "$repo/z13/systemd/z13-keyboard-watch.path" \
  "$HOME/.config/systemd/user/z13-keyboard-watch.path"

systemd-analyze --user verify \
  "$HOME/.config/systemd/user/z13-osk.service" \
  "$HOME/.config/systemd/user/z13-keyboard-state.service" \
  "$HOME/.config/systemd/user/z13-keyboard-watch.path"

systemctl --user daemon-reload
systemctl --user enable z13-keyboard-state.service z13-keyboard-watch.path
systemctl --user start z13-keyboard-watch.path z13-keyboard-state.service

printf 'z13 touch keyboard installed\n'
