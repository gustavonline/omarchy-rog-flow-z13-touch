#!/usr/bin/env python3

"""Fail fast if the declarative Z13 layout drifts from its design contract."""

from __future__ import annotations

import json
import pathlib
import sys


EXPECTED = {
    "Letters": [
        [*list("1234567890"), "-", "+"],
        ["⇥", *list("qwertyuiopå"), "⌫"],
        ["⇧", *list("asdfghjklæø"), "↵"],
        [*list("zxcvbnm"), ",", ".", "-"],
        ["123", "FN", "", "━━━━", "#+=", "⌨↓"],
    ],
    "Numbers": [
        [*list("1234567890"), "⌫"],
        ["-", "/", ":", ";", "(", ")", "kr", "&", "@", '"'],
        ["#+=", ".", ",", "?", "!", "'", "⌫", "↵"],
        ["ABC", "FN", "", "━━━━", "#+=", "⌨↓"],
    ],
    "Symbols": [
        ["[", "]", "{", "}", "#", "%", "^", "*", "+", "="],
        ["_", "\\", "|", "~", "<", ">", "€", "£", "¥", "•"],
        ["`", "·", "√", "π", "÷", "×", "§", "©", "®", "⌫", "↵"],
        ["123", "ABC", "FN", "", "━━━━", "☺", "⌨↓"],
    ],
    "Functions": [
        ["ESC", *[f"F{i}" for i in range(1, 13)], "⌦"],
        ["⇥", "⇪", "INS", "HOME", "END", "PG↑", "PG↓", "⌫", "↵", "↑"],
        ["CTRL", "", "ALT", "ALT GR", "⇧", "←", "↓", "→"],
        ["ABC", "123", "#+=", "━━━━", "⌨↓"],
    ],
}

EXPECTED_GEOMETRY = {
    "height": 360,
    "landscape_height": 360,
    "key_border": 6,
    "panel_margin_ratio": 0.008,
}

EXPECTED_CODES = {
    **{letter: f"KEY_{letter.upper()}" for letter in "qwertyuiopasdfghjklzxcvbnm"},
    **{digit: f"KEY_{digit}" for digit in "1234567890"},
    **{f"F{number}": f"KEY_F{number}" for number in range(1, 13)},
    "å": "KEY_LEFTBRACE",
    "æ": "KEY_SEMICOLON",
    "ø": "KEY_APOSTROPHE",
    "+": "KEY_MINUS",
    "-": "KEY_SLASH",
    ",": "KEY_COMMA",
    ".": "KEY_DOT",
    "⌫": "KEY_BACKSPACE",
    "━━━━": "KEY_SPACE",
    "ESC": "KEY_ESC",
    "⌦": "KEY_DELETE",
    "⇥": "KEY_TAB",
    "INS": "KEY_INSERT",
    "HOME": "KEY_HOME",
    "END": "KEY_END",
    "PG↑": "KEY_PAGEUP",
    "PG↓": "KEY_PAGEDOWN",
    "↵": "KEY_ENTER",
    "↑": "KEY_UP",
    "←": "KEY_LEFT",
    "↓": "KEY_DOWN",
    "→": "KEY_RIGHT",
}

EXPECTED_MODIFIERS = {
    "⇧": "Shift",
    "⇪": "CapsLock",
    "CTRL": "Ctrl",
    "": "Super",
    "ALT": "Alt",
    "ALT GR": "AltGr",
}

EXPECTED_LAYOUT_TARGETS = {
    "123": "Numbers",
    "ABC": "Letters",
    "#+=": "Symbols",
    "FN": "Functions",
}

EXPECTED_TEXT_FLICKS = {
    **dict(zip("qwertyuiop", ["[", "]", "{", "}", "<", ">", "\\", "|", "!", "?"])),
    **dict(zip("asdfghjklæø", ["@", "#", "$", "&", "*", "(", ")", "'", '"', "€", "£"])),
    "x": "~",
    "c": "^",
    "v": "=",
    "b": "/",
}

EXPECTED_MEDIA_FLICKS = {
    "F1": ("󰝟", "KEY_MUTE"),
    "F2": ("󰕿", "KEY_VOLUMEDOWN"),
    "F3": ("󰖀", "KEY_VOLUMEUP"),
    "F4": ("󰍭", "KEY_F20"),
    "F5": ("󰈐", "KEY_PROG1"),
    "F6": ("󰄀", "KEY_SYSRQ"),
    "F7": ("󰃞", "KEY_BRIGHTNESSDOWN"),
    "F8": ("󰃠", "KEY_BRIGHTNESSUP"),
    "F9": ("󰍹", "KEY_SWITCHVIDEOMODE"),
    "F10": ("󰟸", "KEY_F21"),
    "F11": ("󰌌", "KEY_KBDILLUMDOWN"),
    "F12": ("󰀝", "KEY_RFKILL"),
}

CONTROL_LABELS = {
    "⌫", "↵", "ESC", "⌦", "⇥", "↑", "↓", "←", "→", "INS",
    "HOME", "END", "PG↑", "PG↓", "━━━━",
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
    elif key_type == "macro":
        if label != "kr" or key.get("codes") != ["KEY_K", "KEY_R"]:
            raise SystemExit(f"{layer_id} row {row_index}: invalid kr macro")
    elif key_type == "shortcut":
        if label != "☺" or key.get("code") != "KEY_E" or key.get("modifier") != "Super|Ctrl":
            raise SystemExit(f"{layer_id} row {row_index}: invalid emoji shortcut")
    elif key_type != "hide":
        raise SystemExit(f"{layer_id} row {row_index} {label}: unsupported type {key_type}")

    is_character = (
        key_type in {"copy", "macro"}
        or (key_type == "code" and label not in CONTROL_LABELS and not label.startswith("F"))
    )
    if is_character and abs(float(key.get("width", 1.0)) - 1.0) > 0.001:
        raise SystemExit(
            f"{layer_id} row {row_index} {label}: character keys must have width 1"
        )


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
            if abs(width - 14.0) > 0.001:
                raise SystemExit(f"{layer_id} row {index}: width is {width}, expected 14")
            for key in row:
                verify_action(layer_id, index, key)

    letters = layers["Letters"]["rows"]
    text_flick_keys = [key for row in letters for key in row if key.get("flick")]
    actual_text_flicks = {key["label"]: key["flick"] for key in text_flick_keys}
    if actual_text_flicks != EXPECTED_TEXT_FLICKS:
        raise SystemExit(
            "Letters: flick map mismatch:\n"
            f"expected {EXPECTED_TEXT_FLICKS}\nactual   {actual_text_flicks}"
        )
    for key in text_flick_keys:
        if key.get("flick_text") != key["flick"] or "flick_code" in key:
            raise SystemExit(f"Letters {key['label']}: flick must emit its literal label")

    function_keys = {
        key["label"]: key for key in layers["Functions"]["rows"][0]
        if key.get("label", "").startswith("F")
    }
    actual_media = {
        label: (key.get("flick"), key.get("flick_code"))
        for label, key in function_keys.items()
    }
    if actual_media != EXPECTED_MEDIA_FLICKS:
        raise SystemExit(
            "Functions: media flick map mismatch:\n"
            f"expected {EXPECTED_MEDIA_FLICKS}\nactual   {actual_media}"
        )
    if any("flick_text" in key for key in function_keys.values()):
        raise SystemExit("Functions: media flicks must emit key codes, not text")

    letter_keys = [
        key
        for row in letters[:4]
        for key in row
        if key.get("type", "code") == "code"
        and len(key.get("label", "")) == 1
        and key["label"].isalpha()
    ]
    for key in letter_keys:
        if key.get("shift") != key["label"].upper():
            raise SystemExit(f"Letters {key['label']}: invalid Shift label")

    print(
        "layout contract: OK (4 layers, 17 rows, width 14, equal character keys, "
        "25 text flicks, 12 ROG media flicks, compact physical arrow cluster)"
    )


if __name__ == "__main__":
    main()
