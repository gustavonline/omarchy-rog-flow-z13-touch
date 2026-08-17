#!/usr/bin/env bash

set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly plugin_root="$HOME/.config/omarchy/plugins"
readonly shell_config="$HOME/.config/omarchy/shell.json"
readonly extra_ids=(
  io.github.gustavonline.z13-touch-tray
  io.github.gustavonline.z13-touch-indicators
  io.github.gustavonline.z13-touch-active-window
)

python3 "$repo/z13/tools/configure_shell.py" remove "$shell_config"

systemctl --user disable --now z13-tablet-rotation.service 2>/dev/null || true
rm -f -- \
  "$HOME/.local/bin/z13-tablet-rotation" \
  "$HOME/.config/systemd/user/z13-tablet-rotation.service"
systemctl --user daemon-reload

"$repo/z13/uninstall.sh"
for id in "${extra_ids[@]}"; do
  rm -rf -- "$plugin_root/$id"
done
omarchy-shell shell rescanPlugins >/dev/null
omarchy-restart-shell

printf 'ROG Flow Z13 Touch runtime and companion widgets removed.\n'
printf 'The root plugin checkout remains; remove it with: omarchy plugin remove io.github.gustavonline.rog-flow-z13-touch\n'
