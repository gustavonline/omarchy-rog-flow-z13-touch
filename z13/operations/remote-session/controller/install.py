#!/usr/bin/python3
"""Install/repair only the user-owned night-mode integration, preserving other settings."""

import argparse
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from control import CONTROLLER_VERSION, SERVICE, STATE, CONFIG, locked, read_json, running_controller, write_json

PACKAGE = Path(__file__).resolve().parent
HOME = Path.home()
PLUGIN_ID = "io.github.gustavonline.night-mode"
PLUGIN = HOME / ".config/omarchy/plugins" / PLUGIN_ID
MARK_START = "-- BEGIN Z13 NIGHT MODE (user-owned)"
MARK_END = "-- END Z13 NIGHT MODE"


def command(*args):
    result = subprocess.run(args, text=True, capture_output=True, timeout=25)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip() or f"{args[0]} exited {result.returncode}")
    return result.stdout.strip()


def controller_readback():
    """Read only: is the controller process that runs now the code on disk?

    This never restarts or signals the service. A restart that follows a read of the idle state
    cannot know that a night has begun in between, and the clean stop it causes would release
    that night and light the panel; the update and boot hooks run this at any hour.
    """
    state = read_json(STATE / "state.json", {})
    running = running_controller(state if isinstance(state, dict) else {}, True)
    if running == CONTROLLER_VERSION:
        return f"controller {CONTROLLER_VERSION} is running"
    return (f"controller reload pending: the running process is {running or 'not shown to be this code'}, "
            f"the code on disk is {CONTROLLER_VERSION}; a restart is a separate, deliberate step while night mode is idle")


def install(check=False):
    """With check=True nothing is written, locked, started or run: the same predicates and
    transformations decide which paths a real run would write, and those paths are listed."""
    if os.geteuid() == 0:
        raise RuntimeError("Run as the desktop user, not root")
    root_config = HOME / ".config/hypr/hyprland.lua"
    if not root_config.is_file():
        raise RuntimeError("Expected Hyprland Lua config is missing; no unsupported migration attempted")
    timestamp = dt.datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    backup = STATE / "backups" / timestamp
    changed = []

    def put(path, data, executable=False):
        old = path.read_bytes() if path.is_file() else None
        if check:
            if old != data:
                changed.append(str(path))
            elif executable and (path.stat().st_mode & 0o7777) != 0o755:
                # A real run chmods the wrappers to 0755 whether or not their bytes changed.
                changed.append(f"{path} (mode {path.stat().st_mode & 0o7777:o} to 755)")
            return
        if old != data:
            if old is not None:
                relative = path.relative_to(HOME)
                saved = backup / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, saved)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name("." + path.name + ".night-mode-new")
            temporary.write_bytes(data)
            temporary.chmod(0o755 if executable else 0o644)
            temporary.replace(path)
            changed.append(str(path))
        if executable:
            path.chmod(0o755)

    with (contextlib.nullcontext() if check else locked()):
        if not CONFIG.exists():
            if not check:
                write_json(CONFIG, {
                    "automatic": True, "start": "19:00", "end": "07:00",
                    "timezone": "Europe/Copenhagen",
                })
            changed.append(str(CONFIG))
        for name in ("omarchy-night-mode", "omarchy-brightness-screen-off"):
            put(HOME / ".local/bin" / name, (PACKAGE / name).read_bytes(), executable=True)
        for name in ("omarchy-night-mode.service", "omarchy-night-mode-inhibit.service"):
            put(HOME / ".config/systemd/user" / name, (PACKAGE / name).read_bytes())
        for source in (PACKAGE / "plugin").iterdir():
            if source.is_file():
                put(PLUGIN / source.name, source.read_bytes())
        put(HOME / ".config/hypr/nightmode.lua", (PACKAGE / "nightmode.lua").read_bytes())
        original = root_config.read_text()
        managed = MARK_START + '\nrequire("hypr.nightmode")\n' + MARK_END
        updated = re.sub(re.escape(MARK_START) + r".*?" + re.escape(MARK_END), managed, original, flags=re.S)
        if MARK_START not in original:
            updated = original.rstrip() + "\n\n" + managed + "\n"
        put(root_config, updated.encode())

        # Merge just this widget. Preserve every existing widget, setting and plugin.
        shell_config = HOME / ".config/omarchy/shell.json"
        shell = read_json(shell_config)
        layout = shell["bar"]["layout"]
        present = any(item.get("id") == PLUGIN_ID for section in layout.values() for item in section)
        if not present:
            if not check:
                saved = backup / shell_config.relative_to(HOME)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(shell_config, saved)
                right = layout["right"]
                index = next((i for i, item in enumerate(right) if item.get("id") == "omarchy.monitor"), len(right))
                right.insert(index, {"id": PLUGIN_ID})
                write_json(shell_config, shell)
            changed.append(str(shell_config))

    hook = PACKAGE / "95-z13-night-mode"
    for event in ("post-boot", "post-update"):
        destination = HOME / ".config/omarchy/hooks" / f"{event}.d" / hook.name
        if not destination.is_file() or destination.read_bytes() != hook.read_bytes():
            if not check:
                command("omarchy", "hook", "install", event, str(hook))
            changed.append(str(destination))

    if check:
        print(json.dumps({"check": True, "would_change": changed}, ensure_ascii=False))
        return

    results = {}
    command("systemctl", "--user", "daemon-reload")
    command("systemctl", "--user", "enable", "omarchy-night-mode.service")
    if subprocess.run(["systemctl", "--user", "is-active", "--quiet", "graphical-session.target"], timeout=5).returncode == 0:
        was_running = subprocess.run(["systemctl", "--user", "is-active", "--quiet", SERVICE], timeout=5).returncode == 0
        command("systemctl", "--user", "start", "omarchy-night-mode.service")
        results["controller"] = controller_readback() if was_running else "controller started by this repair"
    # Post-update can also run without a shell. Config persists until next login.
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        command("hyprctl", "reload")
        config_errors = command("hyprctl", "configerrors").strip()
        if config_errors:
            raise RuntimeError("Hyprland config errors: " + config_errors)
        results["hyprland"] = "reloaded; no config errors"
        command("omarchy-shell", "shell", "rescanPlugins")
        results["shell"] = command("omarchy", "plugin", "enable", PLUGIN_ID)
        for attempt in range(5):
            try:
                results["widget"] = command("omarchy-shell", PLUGIN_ID, "status")
                break
            except RuntimeError:
                if attempt == 4:
                    raise RuntimeError("Night-mode widget did not load; inspect normal Omarchy shell logs and reload the shell")
                time.sleep(0.2)
    else:
        results["shell"] = "saved for next graphical session"
    receipt = {
        "at": dt.datetime.now().astimezone().isoformat(),
        "action": "install-or-repair", "changed": changed,
        "backup": str(backup) if backup.exists() else None,
        "integration": results,
        "policy_preserved": read_json(CONFIG),
        "physical_night_transition_exercised": False,
    }
    write_json(STATE / "last-repair.json", receipt)
    initial = STATE / "installation.json"
    if not initial.exists():
        write_json(initial, receipt)
    print(json.dumps(receipt, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair", action="store_true", help="idempotent post-update/post-boot integration repair")
    parser.add_argument("--check", action="store_true",
                        help="read only: list the paths a repair from this package would write, and write nothing")
    args = parser.parse_args()
    try:
        install(check=args.check)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        if not args.check:
            write_json(STATE / "last-repair-error.json", {
                "at": dt.datetime.now().astimezone().isoformat(), "error": str(exc),
            })
        print(f"Z13 night-mode integration: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
