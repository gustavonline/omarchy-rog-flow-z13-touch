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
: >"$log"

touch "$cover"
Z13_COVER_DEVICE="$cover" Z13_SYSTEMCTL="$repo/z13/tools/mock-systemctl" \
  Z13_TEST_LOG="$log" "$repo/z13/runtime/z13-keyboard-state"

expected_attached=$'--user --no-block stop z13-osk.service\n--user --no-block start omarchy-fcitx5.service'
[[ $(<"$log") == "$expected_attached" ]]

rm -f -- "$cover"
: >"$log"
Z13_COVER_DEVICE="$cover" Z13_SYSTEMCTL="$repo/z13/tools/mock-systemctl" \
  Z13_TEST_LOG="$log" "$repo/z13/runtime/z13-keyboard-state"

expected_detached=$'--user --no-block stop omarchy-fcitx5.service\n--user --no-block start z13-osk.service'
[[ $(<"$log") == "$expected_detached" ]]

: >"$log"
Z13_COVER_DEVICE="$cover" Z13_SYSTEMCTL="$repo/z13/tools/mock-systemctl" \
  Z13_OSK_ACTION=restart Z13_TEST_LOG="$log" \
  "$repo/z13/runtime/z13-keyboard-state"

expected_install_refresh=$'--user --no-block stop omarchy-fcitx5.service\n--user --no-block restart z13-osk.service'
[[ $(<"$log") == "$expected_install_refresh" ]]

if Z13_COVER_DEVICE="$cover" Z13_SYSTEMCTL="$repo/z13/tools/mock-systemctl" \
  Z13_OSK_ACTION=invalid Z13_TEST_LOG="$log" \
  "$repo/z13/runtime/z13-keyboard-state" >/dev/null 2>&1; then
  printf 'invalid Z13_OSK_ACTION unexpectedly succeeded\n' >&2
  exit 1
fi

for mode in light dark; do
  : >"$log"
  Z13_OSK_BINARY="$repo/z13/tools/mock-osk" \
    Z13_OSK_THEME_FILE="$repo/z13/theme.env" \
    Z13_OSK_MODE="$mode" Z13_TEST_LOG="$log" \
    "$repo/z13/runtime/z13-osk"

  args=$(<"$log")
  [[ "$args" == *"--auto --hidden --no-popup"* ]]
  [[ "$args" == *"--fn Inter 19 --alpha 255 -R 10"* ]]
  if [[ "$mode" == light ]]; then
    [[ "$args" == *"--bg eff1f5 --fg ccd0da --fg-sp bcc0cc"* ]]
    [[ "$args" == *"--swipe 1e66f5 --swipe-sp 1e66f5"* ]]
    [[ "$args" == *"--text 4c4f69 --text-sp 4c4f69"* ]]
  else
    [[ "$args" == *"--bg 24273a --fg 363a4f --fg-sp 494d64"* ]]
    [[ "$args" == *"--swipe 8aadf4 --swipe-sp 8aadf4"* ]]
    [[ "$args" == *"--text cad3f5 --text-sp cad3f5"* ]]
  fi
done

printf 'runtime contract: OK (visibility policy, cover transitions, install refresh and Catppuccin light/dark launch)\n'
