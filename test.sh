#!/usr/bin/env bash

set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

python3 "$repo/z13/tools/verify_layout.py" "$repo/z13/layout.json"
"$repo/z13/tools/verify_runtime.sh"
python_cache=$(mktemp -d)
trap 'rm -rf -- "$python_cache"' EXIT
PYTHONPYCACHEPREFIX="$python_cache" python3 -m py_compile \
  "$repo/z13/runtime/z13-theme" \
  "$repo/z13/tools/configure_shell.py" \
  "$repo/z13/tools/generate_layout.py" \
  "$repo/z13/tools/verify_layout.py"

shell_fixture="$python_cache/shell.json"
cat >"$shell_fixture" <<'EOF'
{"bar":{"layout":{"left":[{"id":"omarchy.menu"},{"id":"gustav.active-window"}],"center":[{"id":"omarchy.keyboard-layout"},{"id":"gustav.indicators"}],"right":[{"id":"gustav.tray"},{"id":"gustav.keyboard-toggle"},{"id":"omarchy.power"}]}}}
EOF
python3 "$repo/z13/tools/configure_shell.py" install "$shell_fixture"
jq -e '
  [.bar.layout.left[].id] == ["omarchy.menu", "io.github.gustavonline.z13-touch-active-window"] and
  [.bar.layout.center[].id] == ["omarchy.keyboard-layout", "io.github.gustavonline.z13-touch-indicators"] and
  [.bar.layout.right[].id] == ["io.github.gustavonline.z13-touch-tray", "io.github.gustavonline.rog-flow-z13-touch", "omarchy.power"]
' "$shell_fixture" >/dev/null
python3 "$repo/z13/tools/configure_shell.py" remove "$shell_fixture"
jq -e '
  [.bar.layout.left[].id] == ["omarchy.menu", "omarchy.active-window"] and
  [.bar.layout.center[].id] == ["omarchy.keyboard-layout", "omarchy.indicators"] and
  [.bar.layout.right[].id] == ["omarchy.tray", "omarchy.power"]
' "$shell_fixture" >/dev/null

omarchy plugin validate "$repo"
for plugin in "$repo"/plugins/*; do
  omarchy plugin validate "$plugin"
done

if command -v qmllint >/dev/null; then
  qmllint -I /usr/share/omarchy/shell "$repo/KeyboardToggle.qml"
  for qml in "$repo"/plugins/*/*.qml "$repo"/plugins/*/indicators/*.qml; do
    qmllint -I /usr/share/omarchy/shell "$qml"
  done
else
  printf 'qmllint unavailable; Omarchy manifest validation still passed.\n'
fi

printf 'ROG Flow Z13 Touch test suite: OK\n'
