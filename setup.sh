#!/usr/bin/env bash

set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly plugin_root="$HOME/.config/omarchy/plugins"
readonly shell_config="$HOME/.config/omarchy/shell.json"
readonly root_id="io.github.gustavonline.rog-flow-z13-touch"
readonly extra_ids=(
  io.github.gustavonline.z13-touch-tray
  io.github.gustavonline.z13-touch-indicators
  io.github.gustavonline.z13-touch-active-window
)

product=$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)
if [[ "$product" != *GZ302EA* && "${Z13_ALLOW_UNSUPPORTED:-0}" != 1 ]]; then
  printf 'Unsupported machine: %s\nSet Z13_ALLOW_UNSUPPORTED=1 only if you reviewed the device paths.\n' "$product" >&2
  exit 1
fi

missing=()
for command in cc make pkg-config wayland-scanner scdoc python3 systemctl hyprctl monitor-sensor jq omarchy; do
  command -v "$command" >/dev/null || missing+=("$command")
done
for package in wayland-client xkbcommon pangocairo; do
  pkg-config --exists "$package" 2>/dev/null || missing+=("pkg-config:$package")
done
if (( ${#missing[@]} )); then
  printf 'Missing build/runtime dependencies: %s\n' "${missing[*]}" >&2
  exit 1
fi

"$repo/test.sh"
Z13_SKIP_VERIFY=1 "$repo/z13/install.sh"

install -Dm755 "$repo/z13/rotation/z13-tablet-rotation" \
  "$HOME/.local/bin/z13-tablet-rotation"
install -Dm644 "$repo/z13/rotation/z13-tablet-rotation.service" \
  "$HOME/.config/systemd/user/z13-tablet-rotation.service"
systemctl --user daemon-reload
systemctl --user enable --now z13-tablet-rotation.service

for id in "${extra_ids[@]}"; do
  target="$plugin_root/$id"
  rm -rf -- "$target"
  mkdir -p -- "$target"
  cp -a -- "$repo/plugins/$id/." "$target/"
done

omarchy-shell shell rescanPlugins >/dev/null
for id in "$root_id" "${extra_ids[@]}"; do
  omarchy plugin enable "$id" >/dev/null
done
python3 "$repo/z13/tools/configure_shell.py" install "$shell_config"
omarchy-restart-shell

printf 'ROG Flow Z13 Touch installed. The active Omarchy theme now drives the keyboard palette.\n'
