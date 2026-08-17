#!/usr/bin/env python3
"""Install or remove the suite's bar widgets without replacing user settings."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = "io.github.gustavonline.rog-flow-z13-touch"
TRAY = "io.github.gustavonline.z13-touch-tray"
INDICATORS = "io.github.gustavonline.z13-touch-indicators"
ACTIVE = "io.github.gustavonline.z13-touch-active-window"


def replace(section: list[dict], mapping: dict[str, str | None]) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for entry in section:
        current = entry.get("id")
        target = mapping.get(current, current)
        if target is None or target in seen:
            continue
        updated = dict(entry)
        updated["id"] = target
        result.append(updated)
        seen.add(target)
    return result


def insert_after(section: list[dict], entry_id: str, after_id: str | None) -> None:
    if any(item.get("id") == entry_id for item in section):
        return
    index = 0
    if after_id is not None:
        for position, item in enumerate(section):
            if item.get("id") == after_id:
                index = position + 1
                break
    section.insert(index, {"id": entry_id})


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in {"install", "remove"}:
        print("usage: configure_shell.py install|remove SHELL_JSON", file=sys.stderr)
        return 2

    action, filename = sys.argv[1], Path(sys.argv[2])
    data = json.loads(filename.read_text())
    layout = data.setdefault("bar", {}).setdefault("layout", {})
    left = layout.setdefault("left", [])
    center = layout.setdefault("center", [])
    right = layout.setdefault("right", [])

    if action == "install":
        left[:] = replace(left, {
            "omarchy.active-window": ACTIVE,
            "gustav.active-window": ACTIVE,
        })
        center[:] = replace(center, {
            "omarchy.indicators": INDICATORS,
            "gustav.indicators": INDICATORS,
        })
        right[:] = replace(right, {
            "omarchy.tray": TRAY,
            "gustav.tray": TRAY,
            "gustav.keyboard-toggle": ROOT,
        })
        insert_after(left, ACTIVE, "omarchy.menu")
        insert_after(center, INDICATORS, "omarchy.keyboard-layout")
        insert_after(right, TRAY, None)
        insert_after(right, ROOT, TRAY)
    else:
        left[:] = replace(left, {ACTIVE: "omarchy.active-window"})
        center[:] = replace(center, {INDICATORS: "omarchy.indicators"})
        right[:] = replace(right, {TRAY: "omarchy.tray", ROOT: None})

    filename.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".shell.", suffix=".json", dir=filename.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary, filename)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
