#!/usr/bin/env bash

set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

jq -e '
  .schemaVersion == 1 and
  .id == "io.github.gustavonline.rog-flow-z13-touch" and
  .version == "0.3.0" and
  .license == "GPL-3.0-only" and
  .entryPoints.barWidget == "KeyboardToggle.qml"
' "$repo/manifest.json" >/dev/null
for manifest in "$repo"/plugins/*/manifest.json; do
  jq -e '
    .schemaVersion == 1 and
    .version == "0.3.0" and
    .license == "GPL-3.0-only" and
    (.kinds | index("bar-widget")) != null
  ' "$manifest" >/dev/null
done

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

if command -v omarchy >/dev/null; then
  omarchy plugin validate "$repo" >/dev/null
  for plugin in "$repo"/plugins/*; do
    omarchy plugin validate "$plugin" >/dev/null
  done
fi

# Tablet touch must be governed only by the explicit one-tap state. Omarchy's
# center-wide hover hold can be set by a synthetic pointer left behind after a
# tap on the right tray; allowing it here causes the middle indicators to flash.
indicators_qml="$repo/plugins/io.github.gustavonline.z13-touch-indicators/Indicators.qml"
grep -Fq 'readonly property bool shellCenterReveal: !tabletMode' "$indicators_qml"
grep -Fq 'alwaysShowIndicators || touchRevealPinned || pointerReveal || shellCenterReveal' "$indicators_qml"
grep -Fq 'id: feedbackClearTimer' "$repo/KeyboardToggle.qml"
grep -Fq '"--signal=RTMIN", "--", "z13-osk.service"' "$repo/KeyboardToggle.qml"

if git -C "$repo" grep -I -n -E '/home/gustav|Documents/Codex|local-qwen' -- . ':!CHANGELOG.md' ':!test.sh'; then
  printf 'test: found machine-specific release content\n' >&2
  exit 1
fi

qml_lint=$(command -v qmllint || true)
if [[ -z "$qml_lint" && -x /usr/lib/qt6/bin/qmllint ]]; then
  qml_lint=/usr/lib/qt6/bin/qmllint
fi
if [[ -n "$qml_lint" ]]; then
  qml_log="$python_cache/qmllint.log"
  if ! "$qml_lint" -I /usr/share/omarchy/shell "$repo/KeyboardToggle.qml" >"$qml_log" 2>&1; then
    cat "$qml_log" >&2
    exit 1
  fi
  for qml in "$repo"/plugins/*/*.qml "$repo"/plugins/*/indicators/*.qml; do
    if ! "$qml_lint" -I /usr/share/omarchy/shell "$qml" >"$qml_log" 2>&1; then
      cat "$qml_log" >&2
      exit 1
    fi
  done
else
  printf 'qmllint unavailable; Omarchy manifest validation still passed.\n'
fi

printf 'ROG Flow Z13 Touch test suite: OK\n'
