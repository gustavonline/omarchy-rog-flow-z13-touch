#!/usr/bin/python3
"""Local Z13 display/idle policy. No remote network calls, root privileges or app control."""

import argparse
import contextlib
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from zoneinfo import ZoneInfo

# Identifies the controller code; the running process stamps it with its service invocation.
CONTROLLER_VERSION = "1.2.0"
HOME = Path.home()
STATE = HOME / ".local/state/omarchy-night-mode"
CONFIG = HOME / ".config/omarchy/night-mode.json"
AWAKE = HOME / ".local/state/omarchy/indicators/stay-awake"
HELD = STATE / "screen-held"
INHIBITOR = "omarchy-night-mode-inhibit.service"
SERVICE = "omarchy-night-mode.service"
TRUSTED = STATE / "trusted-session.json"
AC_POWER = Path("/sys/class/power_supply/AC0/online")
LID_STATE = Path("/proc/acpi/button/lid/LID/state")
WAKE_OPTIONS = ("mouse_move_enables_dpms", "key_press_enables_dpms")
# Optional "headless" object in night-mode.json; omitted keys use these defaults.
HEADLESS_DEFAULTS = {"enabled": True, "name": "Z13-NIGHT", "capture_probe": True, "retry_seconds": 300}
# The configured name is a prefix: every request adds "-" and six hex digits, so the whole
# name stays within 32 characters and is one nobody else can have chosen.
HEADLESS_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,24}")
WINDOW_ADDRESS = re.compile(r"0x[0-9a-fA-F]{1,16}")
GRIM = "/usr/bin/grim"
# How long a freshly created output may take to appear and become ready, and how long
# one that was ready may report not-ready before it counts as lost.
READY_TIMEOUT = 30
UNREADY_GRACE = 10
# Rate limits, not the end of an obligation: removal requests per round and the pause between
# rounds for an output that stays listed; how often requests of unknown outcome are looked for;
# and how many of them may be under watch before no further request is made.
REMOVE_TRIES = 3
REMOVE_COOLDOWN = 600
WATCH_INTERVAL = 30
WATCH_LIMIT = 8
WATCH_CHECKED = [0.0]
# Replies HyprCtl.cpp (dispatchOutput) gives before it acts on a create or remove request. Only
# these show that nothing was started; any other failure to get a valid reply leaves it unknown.
OUTPUT_REFUSALS = (
    "not enough args", "name already taken", "a real monitor already uses that name.",
    "no backend replied to the request", "output not found",
    "cannot remove a real display. use the monitor keyword.",
)


class NativeLockPending(RuntimeError):
    """Lock was requested; do not issue duplicate requests from the same error path."""


class HeadlessUnavailable(RuntimeError):
    """The owned virtual output cannot be established or kept. It is reported, never a reason to light the panel."""


class HeadlessAmbiguous(HeadlessUnavailable):
    """Ownership of an output cannot be shown. It is left untouched and reported."""


class OutputRefused(RuntimeError):
    """Hyprland answered with a reply it gives before acting, so the request started nothing."""


def read_json(path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text() == payload:
        return
    fd, name = tempfile.mkstemp(prefix=".night-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run(*args, timeout=12):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-600:]
        raise RuntimeError(f"{args[0]}: {detail or 'exit ' + str(result.returncode)}")
    return result.stdout.strip()


@contextlib.contextmanager
def locked(timeout=None):
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (STATE / "lock").open("a") as lock:
        if timeout is None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        else:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Display controller is busy; native lid lock required")
                    time.sleep(0.025)
        yield


def settings():
    config = read_json(CONFIG)
    if not isinstance(config, dict) or type(config.get("automatic")) is not bool:
        raise ValueError(f"Invalid automatic setting in {CONFIG}")
    zone = ZoneInfo(config["timezone"])
    start = dt.time.fromisoformat(config["start"])
    end = dt.time.fromisoformat(config["end"])
    if start == end or start.tzinfo or end.tzinfo:
        raise ValueError("Night start/end must be different local times")
    return config, zone, start, end


def runtime():
    stored = read_json(STATE / "state.json", {})
    if not isinstance(stored, dict):
        raise ValueError(f"Invalid night-mode state in {STATE / 'state.json'}")
    # State written by an earlier controller lacks the headless keys.
    state = {
        "night": None, "display": None, "manual_blank": False,
        "override": None, "error": "", "headless": None, "headless_block": None,
    }
    state.update(stored)
    return state


def save(state):
    write_json(STATE / "state.json", state)


def next_boundary(now, at):
    boundary = dt.datetime.combine(now.date(), at, now.tzinfo)
    if boundary <= now:
        boundary = dt.datetime.combine(now.date() + dt.timedelta(days=1), at, now.tzinfo)
    return boundary.timestamp()


def desired(state, config, zone, start, end):
    now = dt.datetime.now(zone)
    override = state.get("override")
    if override and override["until"] > now.timestamp():
        return override["on"]
    state["override"] = None
    clock = now.time().replace(tzinfo=None)
    in_window = (start <= clock < end) if start < end else (clock >= start or clock < end)
    return config["automatic"] and in_window


def sinks():
    return {s["name"]: bool(s["mute"]) for s in json.loads(run("pactl", "-f", "json", "list", "sinks"))}


def set_wake_options(values):
    body = ", ".join(f"{name} = {'true' if value else 'false'}" for name, value in values.items())
    result = run("hyprctl", "eval", "hl.config({ misc = { " + body + " } })")
    if result and "error" in result.lower():
        raise RuntimeError(result)


def backlights():
    return sorted(Path("/sys/class/backlight").glob("*"))


def light_value(path):
    return int((path / "brightness").read_text().strip())


def set_light(name, value):
    run("brightnessctl", "-d", name, "set", str(value))


def internal_monitors():
    return [m for m in json.loads(run("hyprctl", "monitors", "-j"))
            if m["name"].startswith(("eDP-", "LVDS-", "DSI-"))]


def set_dpms(name, enabled):
    action = "enable" if enabled else "disable"
    result = run("hyprctl", "dispatch", "hl.dsp.dpms({ action = " + json.dumps(action) + ", monitor = " + json.dumps(name) + " })")
    if "error" in result.lower():
        raise RuntimeError(result)


def headless_settings(config):
    raw = config.get("headless", {})
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid headless setting in {CONFIG}")
    unknown = sorted(set(raw) - set(HEADLESS_DEFAULTS))
    if unknown:
        raise ValueError(f"Unknown headless setting in {CONFIG}: {', '.join(unknown)}")
    merged = {**HEADLESS_DEFAULTS, **raw}
    if type(merged["enabled"]) is not bool or type(merged["capture_probe"]) is not bool:
        raise ValueError(f"headless.enabled and headless.capture_probe must be true or false in {CONFIG}")
    if not isinstance(merged["name"], str) or not HEADLESS_NAME.fullmatch(merged["name"]):
        raise ValueError(f"Invalid headless.name in {CONFIG}: 1 to 25 letters, digits, '.', '_' or '-', starting with a letter or digit")
    if type(merged["retry_seconds"]) is not int or not 30 <= merged["retry_seconds"] <= 86400:
        raise ValueError(f"headless.retry_seconds must be 30-86400 in {CONFIG}")
    return merged


def all_monitors():
    return {m["name"]: m for m in json.loads(run("hyprctl", "monitors", "all", "-j"))}


def headless_ready(monitor):
    workspace = monitor.get("activeWorkspace") if monitor else None
    return bool(
        monitor and monitor.get("disabled") is False and monitor.get("dpmsStatus") is True
        and isinstance(monitor.get("width"), int) and monitor["width"] > 0
        and isinstance(monitor.get("height"), int) and monitor["height"] > 0
        and isinstance(workspace, dict) and isinstance(workspace.get("id"), int) and workspace["id"] > 0)


def describe_monitor(monitor):
    if not monitor:
        return "absent"
    return (f'disabled={monitor.get("disabled")} dpms={monitor.get("dpmsStatus")} '
            f'size={monitor.get("width")}x{monitor.get("height")}')


def clock(timestamp):
    return dt.datetime.fromtimestamp(timestamp).strftime("%H:%M")


def dispatch(expression):
    # With the Lua config manager, `hyprctl dispatch X` evaluates `return hl.dispatch(X)`
    # and answers "ok" on success; anything else is the Lua error text.
    result = run("hyprctl", "dispatch", expression)
    if not result.lower().startswith("ok"):
        raise RuntimeError(result or "empty dispatch reply")
    return result


def focus_monitor(name):
    dispatch("hl.dsp.focus({ monitor = " + json.dumps(name) + " })")


def output_command(*args):
    # Create and remove answer "ok" when requested, before the compositor has finished.
    result = run("hyprctl", "output", *args)
    if result.lower() != "ok":
        error = f"hyprctl output {args[0]}: {result or 'empty reply'}"
        raise (OutputRefused if result.lower() in OUTPUT_REFUSALS else RuntimeError)(error)


def capture_focus(monitors):
    focused = next((name for name, m in monitors.items() if m.get("focused")), None)
    window = None
    try:
        active = json.loads(run("hyprctl", "activewindow", "-j") or "{}")
        address = active.get("address") if isinstance(active, dict) else None
        if isinstance(address, str) and WINDOW_ADDRESS.fullmatch(address):
            window = address
    except (ValueError, RuntimeError, subprocess.SubprocessError):
        pass
    return {"monitor": focused, "window": window}


def probe_capture(name):
    """One named-output screencopy frame. This proves that route only, not the desktop portal."""
    if not Path(GRIM).is_file():
        raise HeadlessUnavailable(f"{GRIM} is missing, so headless capture cannot be verified")
    try:
        result = subprocess.run([GRIM, "-o", name, "-t", "ppm", "-"], capture_output=True, timeout=10)
    except subprocess.TimeoutExpired:
        raise HeadlessUnavailable(f"Capture of {name} timed out; its frames may be stalled") from None
    if result.returncode:
        detail = result.stderr.decode(errors="replace").strip()[-300:]
        raise HeadlessUnavailable(f"Capture of {name} failed: {detail or 'exit ' + str(result.returncode)}")
    frame = re.match(rb"P6\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s", result.stdout)
    if not frame:
        raise HeadlessUnavailable(f"Capture of {name} was not a PPM frame")
    width, height, depth = (int(part) for part in frame.groups())
    if not (width > 0 and height > 0 and depth == 255
            and len(result.stdout) == frame.end() + width * height * 3):
        raise HeadlessUnavailable(f"Capture of {name} returned an incomplete frame")


def current_session():
    return os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")


def record_session(record):
    """'same', 'other' (an earlier compositor instance, whose outputs are gone) or 'unknown'."""
    session = current_session()
    if not record.get("session") or not session:
        return "unknown"
    return "same" if record["session"] == session else "other"


def headless_request_name(base):
    # Every attempt asks for a name nobody else can have chosen, so an output carrying it is ours.
    return f"{base}-{os.urandom(3).hex()}"


def locate_headless(state, record, monitors):
    """The output night mode created, or None while it is absent.

    Ownership is shown, never guessed, each time: the name is unique to this request, was absent
    before it, was on record before the compositor was asked, belongs to this compositor instance
    and keeps the monitor id first seen. Otherwise the output is left untouched (HeadlessAmbiguous).
    """
    if record_session(record) != "same":
        raise HeadlessAmbiguous("The Hyprland instance cannot be matched to the one that made the record, so ownership of the virtual output cannot be shown")
    name = record["requested"]
    monitor = monitors.get(name)
    if monitor is None:
        return None
    if record.get("create_refused") or record.get("create_at") is None or name in record["before"]:
        raise HeadlessAmbiguous(f"Output {name} is not shown to have been created by night mode; it was left untouched")
    ident = monitor.get("id")
    if not isinstance(ident, int):
        raise HeadlessAmbiguous(f"Output {name} reports no monitor id, so it cannot be identified; it was left untouched")
    if record.get("monitor_id") is None:
        record["monitor_id"] = ident
        record["actual"] = name
        save(state)
    elif ident != record["monitor_id"]:
        raise HeadlessAmbiguous(f"Output {name} is not the output night mode first saw (monitor id {ident}, was {record['monitor_id']}); it was left untouched")
    return monitor


def find_headless(state, hs, record, monitors):
    try:
        return locate_headless(state, record, monitors)
    except HeadlessAmbiguous as exc:
        headless_failed(state, hs, str(exc))


def headless_failed(state, hs, reason, hold=None):
    """Settle only what night mode made, hold off retries, and report. The panel is never touched."""
    problems = []
    try:
        release_headless(state)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        problems.append(f"cleanup: {exc}")
    if problems:
        reason += " (" + "; ".join(problems) + ")"
    until = time.time() + (hold or hs["retry_seconds"])
    state["headless_block"] = {"until": until, "reason": reason}
    save(state)
    raise HeadlessUnavailable(f"{reason} (next attempt {clock(until)})")


def ensure_headless(state, hs):
    """Create, find and focus the owned virtual output. True when ready, False while it is appearing.

    This runs after the panel has been blanked and never changes it.
    """
    now = time.time()
    held = state.get("headless")
    if held is not None and held.get("abandon"):
        # settle_active has just had its turn this tick; what is still owed blocks a replacement.
        why = (held.get("unresolved") or {}).get("reason") or (state.get("headless_block") or {}).get("reason")
        raise HeadlessUnavailable("The previous virtual output is still being settled; no replacement is made" + (f": {why}" if why else ""))
    block = state.get("headless_block")
    if block and block["until"] > now:
        raise HeadlessUnavailable(f'{block["reason"]} (next attempt {clock(block["until"])})')
    if block:
        state["headless_block"] = None
    record = state.get("headless")
    if record is not None and record_session(record) == "other":
        # Recorded under an earlier compositor instance, whose outputs no longer exist.
        state["headless"] = record = None
        save(state)
    monitors = all_monitors()
    if record is None:
        session = current_session()
        if not session:
            headless_failed(state, hs, "The Hyprland instance signature is not visible, so ownership of a virtual output could not be shown; none was created")
        watch = state.get("headless_watch") or []
        owed = next((r for r in watch if r.get("unresolved")), None)
        if owed:
            headless_failed(state, hs, "An earlier virtual output is still owed, so no replacement is made: " + owed["unresolved"]["reason"])
        if len(watch) >= WATCH_LIMIT:
            headless_failed(state, hs, f"{len(watch)} earlier virtual output requests are still unresolved, so no further request is made until they are")
        name = headless_request_name(hs["name"])
        if name in monitors:
            headless_failed(state, hs, f"Output {name} already exists and is not owned by night mode; it was left untouched")
        if hs["capture_probe"] and not Path(GRIM).is_file():
            headless_failed(state, hs, f"{GRIM} is missing, so headless capture cannot be verified")
        record = {
            "requested": name, "actual": None, "monitor_id": None, "before": sorted(monitors),
            "started": now, "create_at": None, "created": None, "create_refused": False,
            "ready_at": None, "verified": False,
            "session": session, "focus_before": capture_focus(monitors),
        }
        state["headless"] = record
        save(state)  # the name is on record before the compositor is asked for anything
    monitor = find_headless(state, hs, record, monitors)
    if monitor is None and record.get("create_at") is None:
        record["create_at"] = time.time()
        save(state)  # the request is on record before it is sent, so a restart never sends it twice
        try:
            output_command("create", "headless", record["requested"])
        except (OutputRefused, OSError) as exc:
            # Hyprland refused before acting, or hyprctl could not even be started: nothing was sent.
            record["create_refused"] = True
            save(state)
            headless_failed(state, hs, f"Could not create the headless output: {exc}")
        except (RuntimeError, subprocess.SubprocessError) as exc:
            # No valid reply (a timeout, a hyprctl failure, unexpected text): the request may have
            # been sent and acted on. It stays on record; the unique name settles it if it is listed.
            record["create_unknown"] = str(exc)
            save(state)
        else:
            record["created"] = time.time()
            save(state)
        monitor = find_headless(state, hs, record, all_monitors())
    waited = now - (record.get("create_at") or record["started"])
    if monitor is None:
        if record["actual"] is not None:
            headless_failed(state, hs, "The headless output disappeared")
        if waited <= READY_TIMEOUT:
            return False
        strays = sorted(n for n in all_monitors() if n not in record["before"] and n != record["requested"])
        if strays:
            headless_failed(state, hs, "The requested output name was not used; new output(s) that cannot be shown to be night mode's were left untouched: " + ", ".join(strays), hold=86400)
        unknown = record.get("create_unknown")
        headless_failed(state, hs, "The headless output did not appear; "
                        + (f"the request had no valid reply ({unknown}) and " if unknown else "")
                        + "its outcome is unknown, so the request stays under watch")
    if not headless_ready(monitor):
        if record["ready_at"] is None:
            if waited <= READY_TIMEOUT:
                return False
        else:
            # Ready before: a short blip, such as a config reload, is not a loss.
            since = record.setdefault("unready_since", now)
            save(state)
            if now - since <= UNREADY_GRACE:
                return True
        headless_failed(state, hs, f"The headless output is not ready ({describe_monitor(monitor)})")
    if record.pop("unready_since", None) is not None:
        save(state)
    if record["ready_at"] is None:
        try:
            focus_monitor(record["actual"])
            if not all_monitors().get(record["actual"], {}).get("focused"):
                raise HeadlessUnavailable("Focus did not move to the headless output")
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            headless_failed(state, hs, f"Could not focus the headless output: {exc}")
        record["ready_at"] = time.time()
        save(state)
    return True


def verify_headless(state, hs):
    """With the panel confirmed dark, check once that the owned output still produces a frame."""
    record = state.get("headless")
    if record is None or record.get("verified"):
        return
    panels = internal_monitors()
    if not panels or any(m["dpmsStatus"] for m in panels):
        return  # the panel has not reported dark yet; the next tick checks
    if hs["capture_probe"]:
        try:
            probe_capture(record["actual"])
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            headless_failed(state, hs, f"Headless capture failed while the panel is dark: {exc}")
    record["verified"] = True
    save(state)


def headless_step(state, config, night=True):
    """Best effort, after the panel is already dark. Report truthfully; never touch the panel.

    What is already owed is settled first, in a night or not, whether new work is enabled or not
    and whatever the headless settings say. Only a night with new work enabled starts anything."""
    issue = ""
    try:
        settle_watch(state)   # earlier requests of unknown outcome
        settle_active(state)  # the active record, once its teardown has begun
        if night:
            hs = headless_settings(config)
            if hs["enabled"]:
                if ensure_headless(state, hs):
                    verify_headless(state, hs)
                record = state.get("headless")
                if not record or not record.get("verified"):
                    issue = "The virtual screen is still being prepared; the panel stays dark"
            elif (state.get("headless") or {}).get("abandon"):
                issue = "A virtual output is still being settled although new work is disabled; the panel stays dark"
    except HeadlessUnavailable as exc:
        issue = f"Virtual screen unavailable; the panel stays dark: {exc}"
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        issue = f"Virtual screen error; the panel stays dark: {exc}"
    if issue != state.get("headless_issue", ""):
        state["headless_issue"] = issue
        if issue:
            print(f"Night mode: {issue}", file=sys.stderr, flush=True)


def restore_window_focus(record, notes):
    address = (record.get("focus_before") or {}).get("window")
    if not address:
        return
    try:
        clients = {c.get("address") for c in json.loads(run("hyprctl", "clients", "-j"))}
        if address in clients:
            dispatch("hl.dsp.focus({ window = " + json.dumps("address:" + address) + " })")
    except (ValueError, TypeError, AttributeError, RuntimeError, subprocess.SubprocessError) as exc:
        notes.append(f"window focus: {exc}")


def forget_headless(state, notes):
    state["headless"] = None
    state["headless_last"] = {"at": time.time(), "notes": notes}
    save(state)


def previous_focus(record, monitors):
    # Focus goes back only to a monitor that is lit. A panel held dark by night mode
    # is never given focus, warped to or otherwise disturbed by cleanup.
    previous = (record.get("focus_before") or {}).get("monitor")
    return previous, (monitors.get(previous) or {}).get("dpmsStatus") is True


def remove_owned(state, record, monitors, monitor, notes, restore_window=True):
    """Ask Hyprland to remove an output shown to be ours: 'done' once it is gone, 'busy' while it is owed.

    A round of REMOVE_TRIES requests that leaves it listed does not end the obligation. It is
    marked unresolved (status, journal), asked again after REMOVE_COOLDOWN, and no replacement
    output is made until it is gone."""
    now = time.time()
    name = record["requested"]
    sent = record.get("remove_sent")
    if sent and now - sent <= READY_TIMEOUT:
        return "busy"  # removal was requested; wait for the compositor to finish it
    if record.get("remove_tries", 0) >= REMOVE_TRIES:
        detail = record.get("remove_error") or "it is still listed"
        reason = f"{name} is still present after {REMOVE_TRIES} removal requests ({detail}); it is still owed"
        record["unresolved"] = {"at": (record.get("unresolved") or {}).get("at", now), "reason": reason}
        record["next_try"] = now + REMOVE_COOLDOWN
        record["remove_tries"] = 0
        record["remove_sent"] = None
        save(state)
        print(f"Night mode: {reason}; next removal request {clock(record['next_try'])}", file=sys.stderr, flush=True)
        return "busy"
    if record.get("next_try") and now < record["next_try"]:
        return "busy"  # pausing between rounds; the output is still owed
    previous, previous_lit = previous_focus(record, monitors)
    # A dark panel still counts: it stays enabled and in the layout. This only refuses
    # to remove an output when nothing else is in the layout at all.
    usable = [n for n, m in monitors.items() if n != name and m.get("disabled") is False]
    if not usable:
        raise RuntimeError("Refusing to remove the headless output while no other output is in the layout")
    if previous_lit and monitor.get("focused"):
        try:
            focus_monitor(previous)
        except (RuntimeError, subprocess.SubprocessError) as exc:
            notes.append(f"monitor focus: {exc}")
    elif previous and not previous_lit:
        notes.append(f"focus not restored: {previous} is dark")
    record["removing"] = now
    record["next_try"] = None
    record["remove_sent"] = None
    record["remove_tries"] = record.get("remove_tries", 0) + 1
    save(state)  # the intent is on record before Hyprland is asked, so a crash here is retried, not waited on
    try:
        output_command("remove", name)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        record["remove_error"] = str(exc)
        save(state)
        if name in all_monitors():
            raise
    else:
        record["remove_sent"] = time.time()
        record["remove_error"] = None
        save(state)
        if name in all_monitors():
            return "busy"  # the compositor is still finishing; a later tick confirms
    if previous_lit and restore_window:
        restore_window_focus(record, notes)
    return "done"


def settle_record(state, record, monitors, notes, restore_window=True):
    """One step of teardown for one record.

    'done': nothing is owed. 'waiting': a request was sent and nothing is listed. 'busy': the output
    is listed and ours, and its removal is in flight or still owed. restore_window is off for an
    entry under watch, which is old: it must not pull focus back to a window from long ago."""
    if record.get("create_refused") or (record.get("create_at") is None and record.get("actual") is None):
        return "done"  # the compositor was never asked: nothing exists to remove
    if record_session(record) != "same":
        notes.append("record dropped: it belongs to an earlier compositor instance or names none, so its output cannot be shown to exist here")
        return "done"
    try:
        monitor = locate_headless(state, record, monitors)
    except HeadlessAmbiguous as exc:
        notes.append(f"left untouched: {exc}")  # ownership cannot be shown, so it is not removed
        return "done"
    if monitor is None:
        if record.get("actual") is None:
            return "waiting"
        if restore_window and previous_focus(record, monitors)[1]:
            restore_window_focus(record, notes)
        return "done"  # it was ours and is gone
    return remove_owned(state, record, monitors, monitor, notes, restore_window)


def retire_headless(state, record):
    """A request was sent and nothing is listed. Nothing shows that it was never acted on, and no
    delay is known after which it cannot appear, so the request stays on record under watch (the
    controller's ticks look for it) and no longer holds up a fresh attempt."""
    watch = state.get("headless_watch") or []
    watch.append(record)
    state["headless_watch"] = watch
    state["headless"] = None
    state["headless_last"] = {"at": time.time(), "notes": [f"{record['requested']} was requested but is not listed; its outcome is unknown, so the request is kept under watch"]}
    save(state)


def release_headless(state):
    """Settle the output night mode made: remove it while it is shown to be ours, keep watching a
    request whose output is not listed, and leave anything else alone. Nothing is forgotten merely
    because time has passed or a retry budget ran out, so a restart, a crash or a deliberate wake
    in between does not lose it."""
    record = state.get("headless")
    if record is None:
        return
    if record.get("abandon") is None:
        record["abandon"] = time.time()
        save(state)
    if not current_session():
        return  # this process cannot tell which compositor it talks to; the controller settles it on its next tick
    notes = []
    outcome = settle_record(state, record, all_monitors(), notes)
    if outcome == "done":
        forget_headless(state, notes)
    elif outcome == "waiting":
        retire_headless(state, record)


def settle_active(state):
    """Settle the active record once its teardown has begun (a failure, or a removal still owed).

    It does not depend on the headless settings: disabling new work, or an invalid setting, must
    not pause an obligation already taken on. A healthy held output has no teardown and stays
    until the deliberate wake or the scheduled exit."""
    record = state.get("headless")
    if record is not None and record.get("abandon"):
        release_headless(state)


def settle_watch(state):
    """Look for requests of unknown outcome and remove any that is listed and shown to be ours.

    An entry leaves the watch only when it is settled or its compositor instance has ended. Looked
    at most every WATCH_INTERVAL seconds, from the controller's ordinary ticks. Never touches the panel."""
    watch = state.get("headless_watch") or []
    if not watch or not current_session():
        return
    now = time.time()
    if now - WATCH_CHECKED[0] < WATCH_INTERVAL:
        return
    WATCH_CHECKED[0] = now
    monitors = all_monitors()
    notes = []
    kept = [record for record in watch if settle_record(state, record, monitors, notes, restore_window=False) != "done"]
    if len(kept) != len(watch):
        state["headless_watch"] = kept
        state["headless_last"] = {"at": time.time(), "notes": notes}
        save(state)


def hold_display(state, config, night):
    # The panel is blanked first, before any virtual-output work in the same tick, and whatever
    # happens to the virtual output afterwards: nothing in this function lights it. Like every
    # action this runs under the controller lock, so it queues behind a tick in progress, and an
    # audio failure earlier in reconcile skips it for that tick (1.0.x behavior).
    if state["display"] is None:
        panels = backlights()
        if not panels:
            raise RuntimeError("No internal backlight found; refusing an unsupported display-off fallback")
        wake = {}
        for name in WAKE_OPTIONS:
            result = json.loads(run("hyprctl", "getoption", f"misc:{name}", "-j"))
            if type(result.get("bool")) is not bool:
                raise RuntimeError(f"Unexpected Hyprland option: {name}")
            wake[name] = result["bool"]
        state["display"] = {
            "backlights": {p.name: light_value(p) for p in panels},
            "keyboard": {p.name: light_value(p) for p in Path("/sys/class/leds").glob("*kbd_backlight*")},
            "wake_options": wake,
            "dpms_monitors": [],
        }
        save(state)  # Save recovery before the first hardware change.
    snapshot = state["display"]
    # Z13's AMD driver leaves actual_brightness=1348 at requested brightness=0.
    # Use normal DPMS power-off too; keep the monitor in the layout.
    HELD.touch(mode=0o600, exist_ok=True)
    for panel in backlights():
        if panel.name not in snapshot["backlights"]:
            snapshot["backlights"][panel.name] = light_value(panel)
            save(state)
        if light_value(panel):
            set_light(panel.name, 0)
    for keyboard in Path("/sys/class/leds").glob("*kbd_backlight*"):
        if keyboard.name not in snapshot["keyboard"]:
            snapshot["keyboard"][keyboard.name] = light_value(keyboard)
            save(state)
        if light_value(keyboard):
            set_light(keyboard.name, 0)
    for name in WAKE_OPTIONS:
        current = json.loads(run("hyprctl", "getoption", f"misc:{name}", "-j"))
        if current.get("bool") is not False:
            set_wake_options({key: False for key in WAKE_OPTIONS})
            break
    monitors = internal_monitors()
    if not monitors:
        raise RuntimeError("No internal monitor found for real screen power-off")
    for monitor in monitors:
        names = snapshot.setdefault("dpms_monitors", [])
        if monitor["name"] not in names:
            names.append(monitor["name"])
            save(state)
        if monitor["dpmsStatus"]:
            set_dpms(monitor["name"], False)
    # With a manual latch and no night this still settles what is owed, and starts nothing.
    headless_step(state, config, night)


def release_display(state):
    snapshot = state["display"]
    if snapshot is None:
        return
    for name, value in snapshot["backlights"].items():
        if (Path("/sys/class/backlight") / name).exists():
            # A zero brightness captured before entry is not a useful wake value.
            minimum = max(1, int((Path("/sys/class/backlight") / name / "max_brightness").read_text()) // 100)
            set_light(name, value if value > 0 else minimum)
    for name, value in snapshot["keyboard"].items():
        if (Path("/sys/class/leds") / name).exists():
            set_light(name, value)
    set_wake_options(snapshot["wake_options"])
    current = {m["name"] for m in internal_monitors()}
    for name in snapshot.get("dpms_monitors", current):
        if name in current:
            set_dpms(name, True)
    HELD.unlink(missing_ok=True)
    state["display"] = None
    save(state)


def hold_night(state):
    if state["night"] is None:
        state["night"] = {"stay_awake": AWAKE.exists(), "sinks": sinks()}
        save(state)
    # Native idle control plus a logind sleep inhibitor: work keeps running.
    if not AWAKE.exists():
        run("omarchy", "toggle", "idle", "stay-awake")
    if subprocess.run(["systemctl", "--user", "is-active", "--quiet", INHIBITOR], timeout=5).returncode:
        run("systemctl", "--user", "start", INHIBITOR)
    current_sinks = sinks()
    for name, muted in current_sinks.items():
        if name not in state["night"]["sinks"]:
            state["night"]["sinks"][name] = muted
            save(state)
        if not muted:
            run("pactl", "set-sink-mute", name, "1")


def release_night(state):
    snapshot = state["night"]
    if snapshot is None:
        return
    current = sinks()
    for name, muted in snapshot["sinks"].items():
        if name in current and current[name] != muted:
            run("pactl", "set-sink-mute", name, "1" if muted else "0")
    run("omarchy", "toggle", "idle", "stay-awake" if snapshot["stay_awake"] else "allow-idle")
    run("systemctl", "--user", "stop", INHIBITOR)
    state["night"] = None
    save(state)


def trusted_settings(config):
    """Opt-in, local connection-profile identity; an SSID is not authentication."""
    policy = config.get("trusted_session", {"enabled": False})
    if not isinstance(policy, dict) or type(policy.get("enabled")) is not bool:
        raise ValueError("trusted_session.enabled must be true or false")
    if set(policy) - {"enabled", "network_uuid"}:
        raise ValueError("Unknown trusted_session setting")
    if policy["enabled"] and not re.fullmatch(
            r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", str(policy.get("network_uuid", ""))):
        raise ValueError("trusted_session.network_uuid must identify the selected NetworkManager profile")
    return policy


def native_lock_status(timeout=1):
    # This Omarchy uses Quickshell WlSessionLock, not logind LockedHint.
    info = json.loads(run("omarchy-shell", "lock", "status", timeout=timeout))
    if not isinstance(info, dict) or any(type(info.get(k)) is not bool for k in
            ("locked", "requested", "pending", "sessionLocked", "secure")):
        raise RuntimeError("Native Omarchy lock state is unknown")
    return info


def desktop_session(require_active=True, timeout=1):
    session = run("loginctl", "show-user", str(os.getuid()), "-p", "Display", "--value", timeout=timeout)
    if not re.fullmatch(r"[A-Za-z0-9]+", session):
        raise RuntimeError("No unambiguous owner desktop session")
    props = dict(line.split("=", 1) for line in run(
        "loginctl", "show-session", session, "-p", "User", "-p", "Active", "-p", "LockedHint", timeout=timeout).splitlines())
    if props.get("User") != str(os.getuid()) or (require_active and props.get("Active") != "yes"):
        raise RuntimeError("Desktop session is not this active user")
    info = native_lock_status(timeout=timeout)
    is_locked = any(info[k] for k in ("locked", "requested", "pending", "sessionLocked", "secure"))
    return session, is_locked


def trusted_candidate(state, config, require_closed=True):
    policy = trusted_settings(config)
    if not policy["enabled"] or state["manual_blank"]:
        return None
    fields = LID_STATE.read_text().strip().split()
    lid = fields[-1] if fields else "unknown"
    if lid not in ("open", "closed"):
        raise RuntimeError("Unknown lid state")
    if require_closed and lid != "closed":
        return None
    override = state.get("override")
    if override and override["until"] > time.time() and override["on"]:
        return None  # An explicit night/blank request has priority over automatic operation.
    if AC_POWER.read_text().strip() != "1":
        return None
    # Local D-Bus only. No network probe or remote source participates in unlocking policy.
    profiles = run("nmcli", "-t", "-f", "UUID,STATE", "connection", "show", "--active", timeout=1).splitlines()
    activated = {row.rsplit(":", 1)[0].lower() for row in profiles if row.endswith(":activated")}
    if policy["network_uuid"].lower() not in activated:
        return None
    session, is_locked = desktop_session()
    if is_locked:
        return None
    active = subprocess.run(["systemctl", "--user", "is-active", "--quiet", SERVICE], timeout=1).returncode == 0
    if not active or running_controller(state, active) != CONTROLLER_VERSION:
        raise RuntimeError("No matching live display controller; native lid lock required")
    return session


def trusted_snapshot():
    if not TRUSTED.exists():
        return None
    try:
        snapshot = read_json(TRUSTED)
        valid = (isinstance(snapshot, dict)
                 and all(type(snapshot.get(key)) is bool for key in ("stay_awake", "inhibitor"))
                 and isinstance(snapshot.get("session"), str)
                 and snapshot.get("phase") in ("held", "lock-pending", "restore-pending"))
    except (OSError, ValueError):
        valid = False
    if not valid:
        # Preserve damaged evidence. Unknown preferences return to native idle defaults,
        # after a confirmed lock; this separate receipt prevents a permanent re-lock loop.
        damaged = STATE / f"trusted-session-invalid-{time.time_ns()}.json"
        TRUSTED.replace(damaged)
        snapshot = {"session": "", "stay_awake": False, "inhibitor": False,
                    "phase": "lock-pending", "damaged_record": str(damaged)}
        write_json(TRUSTED, snapshot)
    return snapshot


def release_trusted(lock_required=True):
    """Confirm lock once, then retry only resource restoration, even after owner unlock."""
    snapshot = trusted_snapshot()
    if snapshot is None:
        return
    if snapshot["phase"] == "held":
        snapshot["phase"] = "lock-pending" if lock_required else "restore-pending"
        write_json(TRUSTED, snapshot)
    if snapshot["phase"] == "lock-pending":
        def lock_observed(timeout=0.4):
            try:
                info = native_lock_status(timeout=timeout)
                return info["secure"] and info["sessionLocked"]
            except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
                return False
        is_locked = lock_observed()
        if not is_locked:
            # Unknown session state must not prevent the independent native lock request.
            # A persisted throttle also prevents duplicate requests from another CLI process.
            now = time.time()
            last_request = snapshot.get("lock_requested_at", 0)
            if type(last_request) not in (int, float) or not 0 <= last_request <= now:
                last_request = 0  # Damaged metadata must never suppress a lock request.
            if now - last_request >= 5:
                snapshot["lock_requested_at"] = time.time()
                write_json(TRUSTED, snapshot)
                try:
                    reply = run("hyprctl", "dispatch", 'hl.dsp.exec_cmd("omarchy-system-lock")', timeout=1)
                    if not reply.lower().startswith("ok"):
                        raise RuntimeError("Native compositor rejected lock dispatch")
                except (OSError, RuntimeError, subprocess.SubprocessError):
                    pass  # Still poll: a timed-out IPC may already have initiated locking.
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if lock_observed(timeout=max(0.02, min(0.4, remaining / 2))):
                    is_locked = True
                    break
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        if not is_locked:
            raise NativeLockPending("Native lock not confirmed; trusted cleanup remains pending")
        snapshot["phase"] = "restore-pending"
        write_json(TRUSTED, snapshot)
    run("omarchy", "toggle", "idle", "stay-awake" if snapshot["stay_awake"] else "allow-idle")
    if not snapshot["inhibitor"]:
        run("systemctl", "--user", "stop", INHIBITOR)
    write_json(STATE / "trusted-recovery-last.json", {**snapshot, "restored": True, "at": time.time()})
    TRUSTED.unlink()


def hold_trusted(session):
    snapshot = trusted_snapshot()
    if snapshot is None:
        inhibitor = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", INHIBITOR], timeout=5).returncode == 0
        write_json(TRUSTED, {"session": session, "stay_awake": AWAKE.exists(), "inhibitor": inhibitor, "phase": "held"})
    elif snapshot["session"] != session or snapshot["phase"] != "held":
        release_trusted()
        raise RuntimeError("Desktop session changed; normal unlock is required")
    if not AWAKE.exists():
        run("omarchy", "toggle", "idle", "stay-awake")
    if subprocess.run(["systemctl", "--user", "is-active", "--quiet", INHIBITOR], timeout=5).returncode:
        run("systemctl", "--user", "start", INHIBITOR)


def trusted_cleanup():
    # Also used after malformed settings and abnormal service exits; no config read is needed.
    with locked():
        release_trusted()


def reconcile(state, config, zone, start, end, release=False):
    errors = []
    lock_pending = False
    try:
        session = None if release else trusted_candidate(state, config)
        if session:
            # Release the old night snapshot before taking ownership of idle/sleep controls.
            release_night(state)
            hold_trusted(session)
            release_display(state)
            release_headless(state)
            settle_watch(state)
            monitors = internal_monitors()
            if not monitors:
                raise RuntimeError("No active internal monitor; trusted session cannot promise GUI access")
            for monitor in monitors:
                if not monitor["dpmsStatus"]:
                    set_dpms(monitor["name"], True)
            state["error"] = ""
            save(state)
            return
        healthy_open = (not release and TRUSTED.exists()
                        and LID_STATE.read_text().strip().endswith("open")
                        and trusted_candidate(state, config, require_closed=False))
        release_trusted(lock_required=not bool(healthy_open))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        errors.append(str(exc))
        lock_pending = isinstance(exc, NativeLockPending)
        if not lock_pending:
            try:
                release_trusted()
            except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as cleanup_error:
                lock_pending = isinstance(cleanup_error, NativeLockPending)
                errors.append(str(cleanup_error))
    night = False if release else desired(state, config, zone, start, end)
    blank = False if release else (night or state["manual_blank"])
    night_setup_ok = True
    try:
        if night:
            hold_night(state)
        else:
            release_night(state)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        errors.append(str(exc))
        night_setup_ok = False
    # A missing audio server must never prevent an intentional screen wake.
    try:
        if not blank:
            # Only a deliberate wake or the scheduled exit gets here. The panel is lit
            # again before the owned virtual output is removed.
            release_display(state)
            release_headless(state)
            settle_watch(state)
            state["headless_issue"] = ""
        elif night_setup_ok:
            hold_display(state, config, night)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        errors.append(str(exc))
    state["error"] = "; ".join(errors)
    save(state)
    if errors:
        raise (NativeLockPending if lock_pending else RuntimeError)(state["error"])


def headless_status(state, config, zone):
    # "issue" is the truthful reason graphical operation is not available; the panel stays dark.
    info = {"enabled": False, "name": "", "ready": False, "focused": False, "verified": False,
            "settling": False, "watching": 0, "unresolved": "",
            "issue": state.get("headless_issue", ""), "blockedUntil": "", "blockReason": "",
            "notes": state.get("headless_last", {}).get("notes", [])}
    try:
        info["enabled"] = headless_settings(config)["enabled"]
        block = state.get("headless_block")
        if block and block["until"] > time.time():
            info["blockedUntil"] = dt.datetime.fromtimestamp(block["until"], zone).strftime("%H:%M")
            info["blockReason"] = block["reason"]
        record = state.get("headless")
        watch = state.get("headless_watch") or []
        if record:
            info["settling"] = bool(record.get("abandon"))
        info["watching"] = len(watch)
        owed = [r["unresolved"]["reason"] for r in ([record] if record else []) + watch if r.get("unresolved")]
        info["unresolved"] = "; ".join(owed)
        if owed and not info["issue"]:
            info["issue"] = "A virtual output is still owed; the panel is not affected: " + info["unresolved"]
        if record and record.get("actual"):
            info["name"] = record["actual"]
            info["verified"] = bool(record.get("verified"))
            monitor = all_monitors().get(record["actual"])
            # Read only: the same instance and monitor id that were first seen, as in locate_headless.
            ours = bool(monitor) and record_session(record) == "same" and monitor.get("id") == record.get("monitor_id")
            info["ready"] = ours and headless_ready(monitor)
            info["focused"] = ours and bool(monitor.get("focused"))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        info["error"] = str(exc)
    return info


def running_controller(state, active):
    """Version of the controller process that systemd runs now, or "" when that cannot be shown.

    The stamp is bound to the service invocation, so one left by an earlier process, for example
    before a rollback, never counts as the running one.
    """
    stamp = state.get("controller_run")
    if not active or not isinstance(stamp, dict) or not isinstance(stamp.get("version"), str) or not stamp.get("invocation"):
        return ""
    try:
        current = run("systemctl", "--user", "show", "--property=InvocationID", "--value", SERVICE)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return ""
    same = current.replace("-", "").lower() == str(stamp["invocation"]).replace("-", "").lower()
    return stamp["version"] if same else ""


def status(state, config, zone, start, end):
    active = bool(state["night"])
    display = state["display"]
    now = dt.datetime.now(zone)
    override = state.get("override")
    if override and override["until"] <= now.timestamp():
        override = None
    service = subprocess.run(["systemctl", "--user", "is-active", "--quiet", SERVICE], timeout=5).returncode == 0
    held = bool(display) and bool(backlights()) and all(
        light_value(p) == 0 and int((p / "actual_brightness").read_text()) == 0 for p in backlights())
    monitors = internal_monitors() if display else []
    powered_off = bool(display) and bool(monitors) and all(not m["dpmsStatus"] for m in monitors)
    try:
        trusted_enabled = trusted_settings(config)["enabled"]
        trusted_error = ""
    except ValueError as exc:
        trusted_enabled, trusted_error = False, str(exc)
    return {
        "active": active, "screenHeld": bool(display), "backlightZero": held,
        "screenPoweredOff": powered_off,
        "automatic": config["automatic"], "schedule": f'{config["start"]}–{config["end"]}',
        "timezone": config["timezone"], "serviceActive": service, "error": state.get("error", ""),
        "pausedUntil": dt.datetime.fromtimestamp(override["until"], zone).strftime("%H:%M") if override and not override["on"] else "",
        "stayAwake": AWAKE.exists(), "manualBlank": state["manual_blank"],
        "headless": headless_status(state, config, zone),
        "trustedSessionEnabled": trusted_enabled,
        "trustedSessionError": trusted_error,
        "trustedSessionHeld": TRUSTED.exists(),
        "controllerVersion": CONTROLLER_VERSION, "runningControllerVersion": running_controller(state, service),
    }


def action(command):
    # One action at a time. A deliberate wake queues behind a tick in progress (a command may take
    # up to 12 s and a capture up to 10 s, several in one tick); it is lit when the lock is free.
    with locked(timeout=0.5 if command == "lid-close" else None):
        config, zone, start, end = settings()
        state = runtime()
        if command == "status":
            return status(state, config, zone, start, end)
        if command == "lid-close" and not trusted_candidate(state, config):
            release_trusted()
            raise RuntimeError("Trusted session is inactive; use the native lid handler")
        now = dt.datetime.now(zone)
        if command == "toggle":
            command = "off" if state["display"] or desired(state, config, zone, start, end) else "on"
        if command in ("on", "off", "wake"):
            if command != "wake" or state["display"] or desired(state, config, zone, start, end):
                on = command == "on"
                state["override"] = {"on": on, "until": next_boundary(now, end if on else start)}
            if command == "on":
                state["headless_block"] = None  # an explicit request tries the virtual output again
            state["manual_blank"] = False
            save(state)
        elif command == "blank":
            state["manual_blank"] = True
            save(state)
        elif command in ("schedule-on", "schedule-off", "schedule-toggle"):
            config["automatic"] = (not config["automatic"]) if command == "schedule-toggle" else command == "schedule-on"
            write_json(CONFIG, config)
        elif command == "auto":
            config["automatic"] = True
            state["override"] = None
            state["manual_blank"] = False
            state["headless_block"] = None
            write_json(CONFIG, config)
            save(state)
        reconcile(state, config, zone, start, end, release=command == "release")
        if command == "lid-close" and not TRUSTED.exists():
            raise RuntimeError("Trusted session is inactive; use the native lid handler")
        return status(state, config, zone, start, end) if command != "tick" else None


def daemon():
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    last_error = ""
    try:
        with locked():
            state = runtime()
            # Bound to this service invocation: a stamp from an earlier process is never the running one.
            stamp = {"version": CONTROLLER_VERSION, "invocation": os.environ.get("INVOCATION_ID", ""), "pid": os.getpid()}
            if state.get("controller_run") != stamp:
                state["controller_run"] = stamp
                save(state)
    except (OSError, ValueError) as exc:
        print(f"Night mode: {exc}", file=sys.stderr, flush=True)
    while not stop.is_set():
        try:
            action("tick")
            last_error = ""
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
            try:
                if not isinstance(exc, NativeLockPending):
                    trusted_cleanup()
            except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as cleanup_error:
                print(f"Trusted-session cleanup: {cleanup_error}", file=sys.stderr, flush=True)
            if str(exc) != last_error:
                print(f"Night mode: {exc}", file=sys.stderr, flush=True)
                last_error = str(exc)
        # This is a local host controller, not an agent/model polling job.
        stop.wait(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "on", "off", "wake", "blank", "toggle", "auto", "schedule-on", "schedule-off", "schedule-toggle", "tick", "daemon", "release", "lid-close"))
    command = parser.parse_args().command
    if command == "daemon":
        daemon()
        return
    # systemd sets SERVICE_RESULT for ExecStopPost. After a crash, timeout or kill the
    # night keeps its saved state and the panel stays dark; only a clean stop releases.
    try:
        if command == "release" and os.environ.get("SERVICE_RESULT", "success") != "success":
            trusted_cleanup()
            print(f"Night mode: abnormal exit ({os.environ['SERVICE_RESULT']}); night state preserved", file=sys.stderr)
            return
        result = action(command)
        if result is not None:
            print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        try:
            if command != "lid-close" and not isinstance(exc, NativeLockPending):  # Do not queue the native lid fallback.
                trusted_cleanup()
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as cleanup_error:
            print(f"Trusted-session cleanup: {cleanup_error}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
