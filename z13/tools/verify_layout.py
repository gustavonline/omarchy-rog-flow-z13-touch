#!/usr/bin/env python3

"""Fail fast if the declarative Z13 layout drifts from its design contract."""

from __future__ import annotations

import json
import pathlib
import sys


EXPECTED = {
    "Letters": [
        list("qwertyuiopå"),
        list("asdfghjklæø"),
        ["⇧", *list("zxcvbnm"), "⌫"],
        ["123", "FN", "SUPER", "Dansk", ".", "↵", "⌨↓"],
    ],
    "Numbers": [
        list("1234567890"),
        ["-", "/", ":", ";", "(", ")", "kr", "&", "@", '"'],
        ["#+=", ".", ",", "?", "!", "'", "⌫"],
        ["ABC", "FN", "SUPER", "Dansk", ".", "↵", "⌨↓"],
    ],
    "Symbols": [
        ["[", "]", "{", "}", "#", "%", "^", "*", "+", "="],
        ["_", "\\", "|", "~", "<", ">", "€", "£", "¥", "•"],
        ["`", "·", "√", "π", "÷", "×", "§", "©", "®", "⌫"],
        ["123", "ABC", "FN", "SUPER", "Dansk", "↵", "⌨↓"],
    ],
    "Functions": [
        ["ESC", *[f"F{i}" for i in range(1, 13)], "DEL"],
        ["TAB", "INS", "HOME", "END", "PGUP", "PGDN", "⌫", "ENTER"],
        ["CTRL", "SUPER", "ALT", "ALTGR", "SHIFT", "↑"],
        ["UNDO", "CUT", "COPY", "PASTE", "SHOT", "←", "↓", "→"],
        ["ABC", "123", "SUPER", "Dansk", "⌨↓"],
    ],
}

EXPECTED_GEOMETRY = {
    "height": 340,
    "landscape_height": 340,
    "key_border": 6,
    "panel_margin_ratio": 0.04,
}

EXPECTED_CODES = {
    **{letter: f"KEY_{letter.upper()}" for letter in "qwertyuiopasdfghjklzxcvbnm"},
    **{digit: f"KEY_{digit}" for digit in "1234567890"},
    **{f"F{number}": f"KEY_F{number}" for number in range(1, 13)},
    "å": "KEY_LEFTBRACE",
    "æ": "KEY_SEMICOLON",
    "ø": "KEY_APOSTROPHE",
    "⌫": "KEY_BACKSPACE",
    "Dansk": "KEY_SPACE",
    "↵": "KEY_ENTER",
    "ESC": "KEY_ESC",
    "DEL": "KEY_DELETE",
    "TAB": "KEY_TAB",
    "INS": "KEY_INSERT",
    "HOME": "KEY_HOME",
    "END": "KEY_END",
    "PGUP": "KEY_PAGEUP",
    "PGDN": "KEY_PAGEDOWN",
    "ENTER": "KEY_ENTER",
    "SHOT": "KEY_SYSRQ",
    "↑": "KEY_UP",
    "←": "KEY_LEFT",
    "↓": "KEY_DOWN",
    "→": "KEY_RIGHT",
}

EXPECTED_MODIFIERS = {
    "⇧": "Shift",
    "SHIFT": "Shift",
    "CTRL": "Ctrl",
    "SUPER": "Super",
    "ALT": "Alt",
    "ALTGR": "AltGr",
}

EXPECTED_LAYOUT_TARGETS = {
    "123": "Numbers",
    "ABC": "Letters",
    "#+=": "Symbols",
    "FN": "Functions",
}

EXPECTED_SHORTCUTS = {
    "UNDO": ("KEY_Z", "Ctrl"),
    "CUT": ("KEY_X", "Ctrl"),
    "COPY": ("KEY_C", "Ctrl"),
    "PASTE": ("KEY_V", "Ctrl"),
}

EXPECTED_FLICKS = {
    **dict(zip("qwertyuiop", "1234567890")),
    **dict(zip("asdfghjklæø", ["@", "#", "$", "&", "*", "(", ")", "'", '"', "€", "£"])),
    **dict(zip("zxcvbnm", ["%", "-", "+", "=", "/", ";", ":"])),
}


def labels(row: list[dict]) -> list[str]:
    return [key["label"] for key in row if key.get("type", "code") != "pad"]


def verify_action(layer_id: str, row_index: int, key: dict) -> None:
    key_type = key.get("type", "code")
    if key_type == "pad":
        if "label" in key:
            raise SystemExit(f"{layer_id} row {row_index}: padding must not have a label")
        return

    label = key.get("label")
    if not label:
        raise SystemExit(f"{layer_id} row {row_index}: non-padding key has no label")

    if key_type == "code":
        expected = EXPECTED_CODES.get(label)
        if expected is None or key.get("code") != expected:
            raise SystemExit(
                f"{layer_id} row {row_index} {label}: expected code {expected}, "
                f"found {key.get('code')}"
            )
    elif key_type == "modifier":
        expected = EXPECTED_MODIFIERS.get(label)
        if expected is None or key.get("modifier") != expected:
            raise SystemExit(
                f"{layer_id} row {row_index} {label}: expected modifier {expected}, "
                f"found {key.get('modifier')}"
            )
    elif key_type == "layout":
        expected = EXPECTED_LAYOUT_TARGETS.get(label)
        if key.get("target") != expected:
            raise SystemExit(
                f"{layer_id} row {row_index} {label}: expected target {expected}, "
                f"found {key.get('target')}"
            )
    elif key_type == "copy":
        if key.get("text") != label:
            raise SystemExit(
                f"{layer_id} row {row_index} {label}: copy text differs from label"
            )
    elif key_type == "shortcut":
        expected = EXPECTED_SHORTCUTS.get(label)
        actual = (key.get("code"), key.get("modifier"))
        if actual != expected:
            raise SystemExit(
                f"{layer_id} row {row_index} {label}: expected shortcut {expected}, "
                f"found {actual}"
            )
    elif key_type == "macro":
        if label != "kr" or key.get("codes") != ["KEY_K", "KEY_R"]:
            raise SystemExit(f"{layer_id} row {row_index}: invalid kr macro")
    elif key_type != "hide":
        raise SystemExit(f"{layer_id} row {row_index} {label}: unsupported type {key_type}")


def main() -> None:
    path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "z13/layout.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or data.get("keymap") != "latin":
        raise SystemExit("layout metadata mismatch")
    if data.get("geometry") != EXPECTED_GEOMETRY:
        raise SystemExit(
            f"geometry mismatch:\nexpected {EXPECTED_GEOMETRY}\nactual   {data.get('geometry')}"
        )
    layers = {layer["id"]: layer for layer in data["layers"]}

    if list(layers) != list(EXPECTED):
        raise SystemExit(f"layer order mismatch: {list(layers)}")
    for layer_id, expected_rows in EXPECTED.items():
        actual_rows = layers[layer_id]["rows"]
        if len(actual_rows) != len(expected_rows):
            raise SystemExit(f"{layer_id}: expected {len(expected_rows)} rows")
        for index, (row, expected) in enumerate(zip(actual_rows, expected_rows), 1):
            actual = labels(row)
            if actual != expected:
                raise SystemExit(
                    f"{layer_id} row {index}:\nexpected {expected}\nactual   {actual}"
                )
            width = sum(float(key.get("width", 1.0)) for key in row)
            if abs(width - 12.0) > 0.001:
                raise SystemExit(f"{layer_id} row {index}: width is {width}, expected 12")
            for key in row:
                verify_action(layer_id, index, key)

    letters = layers["Letters"]["rows"]
    flick_keys = [key for row in letters for key in row if key.get("flick")]
    actual_flicks = {key["label"]: key["flick"] for key in flick_keys}
    if actual_flicks != EXPECTED_FLICKS:
        raise SystemExit(
            f"Letters: flick map mismatch:\nexpected {EXPECTED_FLICKS}\nactual   {actual_flicks}"
        )
    for key in flick_keys:
        if key["flick"].isascii() and key["flick"].isalnum():
            expected_code = f"KEY_{key['flick'].upper()}"
            if key.get("flick_code") != expected_code or "flick_text" in key:
                raise SystemExit(f"Letters {key['label']}: invalid keycode flick")
        elif key.get("flick_text") != key["flick"] or "flick_code" in key:
            raise SystemExit(f"Letters {key['label']}: invalid text flick")

    letter_keys = [
        key
        for row in letters[:3]
        for key in row
        if key.get("type", "code") == "code" and len(key.get("label", "")) == 1
        and key["label"].isalpha()
    ]
    for key in letter_keys:
        if key.get("shift") != key["label"].upper():
            raise SystemExit(f"Letters {key['label']}: invalid Shift label")

    print(
        "layout contract: OK (4 layers, 17 rows, width 12, Danish iPad order, "
        "actions, Shift and 28 flicks)"
    )


if __name__ == "__main__":
    main()
