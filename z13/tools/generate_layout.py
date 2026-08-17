#!/usr/bin/env python3

"""Generate wvkbd's C layout header from the single Z13 JSON mapping."""

from __future__ import annotations

import json
import pathlib
import sys


VALID_TYPES = {"code", "copy", "hide", "layout", "macro", "modifier", "pad", "shortcut"}
VALID_MODIFIERS = {
    "Shift", "CapsLock", "Ctrl", "Alt", "Super", "AltGr", "Super|Ctrl"
}


def c_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def fail(message: str) -> None:
    raise SystemExit(f"layout error: {message}")


def validate(data: dict) -> None:
    if data.get("version") != 1:
        fail("version must be 1")
    geometry = data.get("geometry", {})
    if not isinstance(geometry.get("grid_rows"), int) or geometry["grid_rows"] < 1:
        fail("geometry.grid_rows must be a positive integer")
    layers = data.get("layers")
    if not isinstance(layers, list) or not layers:
        fail("layers must be a non-empty list")
    ids = [layer.get("id") for layer in layers]
    if len(ids) != len(set(ids)) or not all(isinstance(item, str) and item for item in ids):
        fail("layer ids must be unique non-empty strings")
    interaction = data.get("interaction", {})
    if not isinstance(interaction, dict):
        fail("interaction must be an object")
    if "shift_double_tap_caps" in interaction and not isinstance(
        interaction["shift_double_tap_caps"], bool
    ):
        fail("interaction.shift_double_tap_caps must be a boolean")

    for layer in layers:
        rows = layer.get("rows")
        if not isinstance(rows, list) or not rows:
            fail(f"{layer['id']}: rows must be non-empty")
        for row_index, row in enumerate(rows):
            if not isinstance(row, list) or not row:
                fail(f"{layer['id']} row {row_index + 1}: row must be non-empty")
            for key_index, key in enumerate(row):
                where = f"{layer['id']} row {row_index + 1} key {key_index + 1}"
                key_type = key.get("type", "code")
                if key_type not in VALID_TYPES:
                    fail(f"{where}: unsupported type {key_type!r}")
                if float(key.get("width", 1.0)) <= 0:
                    fail(f"{where}: width must be positive")
                if "label_scale" in key and not (
                    isinstance(key["label_scale"], (int, float))
                    and 0.0 < float(key["label_scale"]) <= 1.5
                ):
                    fail(f"{where}: label_scale must be in (0, 1.5]")
                if "label_bold" in key and not isinstance(key["label_bold"], bool):
                    fail(f"{where}: label_bold must be a boolean")
                if key_type != "pad" and not key.get("label"):
                    fail(f"{where}: label is required")
                if key_type in {"code", "shortcut"} and not key.get("code"):
                    fail(f"{where}: code is required")
                if key_type == "copy" and len(key.get("text", "")) != 1:
                    fail(f"{where}: copy text must contain one Unicode character")
                if key_type == "layout" and key.get("target") not in ids:
                    fail(f"{where}: unknown target {key.get('target')!r}")
                if key_type == "macro" and not key.get("codes"):
                    fail(f"{where}: macro requires codes")
                if key_type in {"modifier", "shortcut"} and key.get("modifier") not in VALID_MODIFIERS:
                    fail(f"{where}: invalid modifier")
                if "flick_text" in key and len(key["flick_text"]) != 1:
                    fail(f"{where}: flick_text must contain one Unicode character")
                if "flick" in key and not (key.get("flick_code") or key.get("flick_text")):
                    fail(f"{where}: flick requires flick_code or flick_text")

def key_initializer(key: dict, macro_name: str | None) -> str:
    key_type = key.get("type", "code")
    fields = [
        f".label = {c_string(key.get('label', ''))}",
        f".shift_label = {c_string(key.get('shift', key.get('label', '')))}",
        f".flick_label = {c_string(key.get('flick', ''))}",
        f".width = {float(key.get('width', 1.0)):.3f}",
    ]

    if key_type == "pad":
        fields.append(".type = Pad")
    elif key_type == "code":
        fields.extend((".type = Code", f".code = {key['code']}"))
    elif key_type == "copy":
        fields.extend((".type = Copy", f".code = {ord(key['text'])}"))
    elif key_type == "modifier":
        fields.extend((".type = Mod", f".code = {key['modifier']}"))
    elif key_type == "layout":
        fields.extend((".type = Layout", f".layout = &layouts[{key['target']}]"))
    elif key_type == "shortcut":
        fields.extend((
            ".type = Code",
            f".code = {key['code']}",
            f".code_mod = {key['modifier']}",
            ".reset_mod = true",
        ))
    elif key_type == "macro":
        fields.extend((
            ".type = Macro",
            f".macro_codes = {macro_name}",
            f".macro_len = {len(key['codes'])}",
        ))
    elif key_type == "hide":
        fields.append(".type = Hide")

    if key.get("style") == "special":
        fields.append(".scheme = 1")
    if key.get("flick_code"):
        fields.append(f".flick_code = {key['flick_code']}")
    if key.get("flick_text"):
        fields.append(f".flick_codepoint = {ord(key['flick_text'])}")
    if "label_scale" in key:
        fields.append(f".label_scale = {float(key['label_scale']):.3f}")
    if key.get("label_bold"):
        fields.append(".label_bold = true")
    return "  { " + ", ".join(fields) + " },"


def generate(data: dict) -> str:
    geometry = data["geometry"]
    layers = data["layers"]
    lines = [
        "/* Generated by z13/tools/generate_layout.py; do not edit. */",
        f"#define KBD_PIXEL_HEIGHT {int(geometry['height'])}",
        f"#define KBD_PIXEL_LANDSCAPE_HEIGHT {int(geometry['landscape_height'])}",
        f"#define KBD_GRID_ROWS {int(geometry['grid_rows'])}",
        f"#define KBD_KEY_BORDER {int(geometry['key_border'])}",
        f"#define KBD_PANEL_MARGIN_RATIO {float(geometry['panel_margin_ratio']):.6f}",
        "",
        "enum layout_id {",
    ]
    lines.extend(f"  {layer['id']}," for layer in layers)
    lines.extend(("  NumLayouts,", "  Index = Letters,", "};", ""))
    lines.extend(f"static struct key keys_{layer['name']}[];" for layer in layers)
    lines.extend(("", "static struct layout layouts[NumLayouts] = {"))
    disable_shift_double_tap_caps = not data.get("interaction", {}).get(
        "shift_double_tap_caps", True
    )
    for layer in layers:
        abc = "true" if layer.get("alphabetic") else "false"
        interaction_field = (
            ", .disable_shift_double_tap_caps = true"
            if disable_shift_double_tap_caps
            else ""
        )
        lines.append(
            f"  [{layer['id']}] = {{ keys_{layer['name']}, {c_string(data['keymap'])}, "
            f"{c_string(layer['name'])}, {abc}{interaction_field} }},"
        )
    lines.extend(("};", ""))

    for layer in layers:
        for row_index, row in enumerate(layer["rows"]):
            for key_index, key in enumerate(row):
                if key.get("type") == "macro":
                    macro_name = f"macro_{layer['name']}_{row_index}_{key_index}"
                    lines.append(
                        f"static const uint32_t {macro_name}[] = {{ {', '.join(key['codes'])} }};"
                    )
    lines.append("")

    for layer in layers:
        lines.append(f"static struct key keys_{layer['name']}[] = {{")
        for row_index, row in enumerate(layer["rows"]):
            for key_index, key in enumerate(row):
                macro_name = None
                if key.get("type") == "macro":
                    macro_name = f"macro_{layer['name']}_{row_index}_{key_index}"
                lines.append(key_initializer(key, macro_name))
            if row_index + 1 < len(layer["rows"]):
                lines.append("  { .type = EndRow },")
        lines.extend(("  { .type = Last },", "};", ""))
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: generate_layout.py INPUT.json OUTPUT.h")
    source = pathlib.Path(sys.argv[1])
    target = pathlib.Path(sys.argv[2])
    data = json.loads(source.read_text(encoding="utf-8"))
    validate(data)
    target.write_text(generate(data), encoding="utf-8")


if __name__ == "__main__":
    main()
