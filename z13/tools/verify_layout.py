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


def labels(row: list[dict]) -> list[str]:
    return [key["label"] for key in row if key.get("type", "code") != "pad"]


def main() -> None:
    path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "z13/layout.json")
    data = json.loads(path.read_text(encoding="utf-8"))
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

    letters = layers["Letters"]["rows"]
    flick_keys = [key for row in letters for key in row if key.get("flick")]
    if len(flick_keys) != 28:
        raise SystemExit(f"Letters: expected 28 flick-enabled keys, found {len(flick_keys)}")

    print("layout contract: OK (4 layers, 17 rows, uniform width 12, Danish iPad order)")


if __name__ == "__main__":
    main()
