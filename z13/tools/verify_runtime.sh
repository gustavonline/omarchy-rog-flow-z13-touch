#!/usr/bin/env bash

set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

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

printf 'runtime contract: OK (attached and detached transitions)\n'
