#!/usr/bin/env bash

set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

"${CC:-cc}" -std=c99 -Wall -Wextra -Werror -I"$repo" \
  "$repo/z13/tools/verify_visibility_policy.c" \
  -o "$test_dir/verify-visibility-policy"
"$test_dir/verify-visibility-policy"

cover="$test_dir/cover"
log="$test_dir/systemctl.log"
state_file="$test_dir/cover-state"
: >"$log"

touch "$cover"
Z13_COVER_DEVICE="$cover" Z13_STATE_FILE="$state_file" Z13_SYSTEMCTL="$repo/z13/tools/mock-systemctl" \
  Z13_TEST_LOG="$log" "$repo/z13/runtime/z13-keyboard-state"

expected_attached=$'--user --no-block stop z13-osk.service\n--user --no-block start omarchy-fcitx5.service'
[[ $(<"$log") == "$expected_attached" ]]
[[ $(<"$state_file") == attached ]]

rm -f -- "$cover"
: >"$log"
Z13_COVER_DEVICE="$cover" Z13_STATE_FILE="$state_file" Z13_SYSTEMCTL="$repo/z13/tools/mock-systemctl" \
  Z13_TEST_LOG="$log" "$repo/z13/runtime/z13-keyboard-state"

expected_detached=$'--user --no-block stop omarchy-fcitx5.service\n--user --no-block start z13-osk.service'
[[ $(<"$log") == "$expected_detached" ]]
[[ $(<"$state_file") == detached ]]

: >"$log"
Z13_COVER_DEVICE="$cover" Z13_STATE_FILE="$state_file" Z13_SYSTEMCTL="$repo/z13/tools/mock-systemctl" \
  Z13_OSK_ACTION=restart Z13_TEST_LOG="$log" \
  "$repo/z13/runtime/z13-keyboard-state"

expected_install_refresh=$'--user --no-block stop omarchy-fcitx5.service\n--user --no-block restart z13-osk.service'
[[ $(<"$log") == "$expected_install_refresh" ]]

if Z13_COVER_DEVICE="$cover" Z13_STATE_FILE="$state_file" Z13_SYSTEMCTL="$repo/z13/tools/mock-systemctl" \
  Z13_OSK_ACTION=invalid Z13_TEST_LOG="$log" \
  "$repo/z13/runtime/z13-keyboard-state" >/dev/null 2>&1; then
  printf 'invalid Z13_OSK_ACTION unexpectedly succeeded\n' >&2
  exit 1
fi

theme_dir="$test_dir/theme"
mkdir -p "$theme_dir"
cat >"$theme_dir/colors.toml" <<'EOF'
background = "#102030"
lighter_background = "#203040"
selection = "#304050"
muted = "#405060"
accent = "#506070"
foreground = "#607080"
EOF

palette=$(Z13_OSK_THEME_DIR="$theme_dir" "$repo/z13/runtime/z13-theme")
[[ "$palette" == $'102030\n203040\n304050\n405060\n506070\n607080' ]]

: >"$log"
Z13_OSK_BINARY="$repo/z13/tools/mock-osk" \
  Z13_OSK_THEME_HELPER="$repo/z13/runtime/z13-theme" \
  Z13_OSK_THEME_DIR="$theme_dir" Z13_TEST_LOG="$log" \
  "$repo/z13/runtime/z13-osk"

args=$(<"$log")
[[ "$args" == *"--auto --hidden --no-popup"* ]]
[[ "$args" == *"--fn Inter 19 --alpha 255 -R 10"* ]]
[[ "$args" == *"--bg 102030 --fg 203040 --fg-sp 304050"* ]]
[[ "$args" == *"--press 405060 --press-sp 405060"* ]]
[[ "$args" == *"--swipe 506070 --swipe-sp 506070"* ]]
[[ "$args" == *"--text 607080 --text-sp 607080"* ]]

printf 'runtime contract: OK (visibility policy, cover transitions, install refresh and Omarchy theme launch)\n'
