# ROG Flow Z13 Touch for Omarchy

A touch-first Omarchy integration for the 2025 ASUS ROG Flow Z13
(`GZ302EA`, Strix Halo). It packages the working tablet setup as one reviewable
Git repository rather than a collection of edits under `/usr/share`.

## What it provides

- A Danish, iPad-inspired virtual keyboard with four consistent layers,
  flick-up symbols, crisp fractional-scale rendering and ROG media actions.
- Automatic virtual-keyboard/Fcitx switching when the detachable cover is
  removed or attached.
- Keyboard colours derived from the active Omarchy theme's `colors.toml`.
- Tablet-only automatic rotation while laptop mode remains landscape.
- A topbar keyboard toggle, touch-toggleable system tray and indicators, and a
  touch-friendly active-window close control.
- Stock hover behaviour whenever the keyboard cover is attached; persistent
  one-tap topbar drawers are enabled only in tablet mode.
- Password/PIN-safe symbol entry that falls back to physical-style virtual key
  events when a secure field rejects input-method text commits.

The suite intentionally contains no dock, launcher replacement or lock-screen
fork. Those belong to Omarchy itself rather than this hardware integration.

The repository root is a valid Omarchy `bar-widget` plugin. The hardware layer
cannot be installed implicitly by `omarchy plugin add`: Omarchy deliberately
does not run plugin hooks or elevated commands. `setup.sh` is therefore an
explicit, inspectable second step. It performs user-level installation only.

## Requirements

This suite supports the 2025 `GZ302EA` hardware contract. The setup gate checks
the product name and stops before making changes on other hardware unless the
operator explicitly sets `Z13_ALLOW_UNSUPPORTED=1` after reviewing the device
paths.

Required commands are `cc`, `make`, `pkg-config`, `wayland-scanner`, `scdoc`,
`python3`, `systemctl`, `hyprctl`, `monitor-sensor`, `jq`, and `omarchy`.
Development packages must expose `wayland-client`, `xkbcommon`, and
`pangocairo` through `pkg-config`. The installer reports the complete missing
list and never invokes a package manager or `sudo`.

## Install

The supported installation path is:

```bash
omarchy plugin add https://github.com/gustavonline/omarchy-rog-flow-z13-touch.git --enable --yes
~/.config/omarchy/plugins/io.github.gustavonline.rog-flow-z13-touch/setup.sh
```

For a local checkout, place the checkout at:

```text
~/.config/omarchy/plugins/io.github.gustavonline.rog-flow-z13-touch
```

Then run `./setup.sh`. The installer refuses non-`GZ302EA` hardware unless the
operator explicitly sets `Z13_ALLOW_UNSUPPORTED=1`. It also stops with a
concrete dependency list instead of invoking `sudo` or a package manager.

## Update and remove

Normal source updates use:

```bash
omarchy plugin update io.github.gustavonline.rog-flow-z13-touch --yes
~/.config/omarchy/plugins/io.github.gustavonline.rog-flow-z13-touch/setup.sh
```

Removal is explicit and reversible to Omarchy's built-in bar widgets:

```bash
~/.config/omarchy/plugins/io.github.gustavonline.rog-flow-z13-touch/remove.sh
omarchy plugin remove io.github.gustavonline.rog-flow-z13-touch --yes
```

`remove.sh` removes only files and services owned by this suite and restores
the stock tray, indicators and active-window widget IDs in `shell.json`.

## Security and ownership

`setup.sh` is an explicit second step because Omarchy correctly does not run
plugin install hooks. Review it before execution. It performs user-level work
only: building the included GPL keyboard, installing the documented user
executables and systemd units, copying the three companion widgets, and
updating only their bar IDs in the user's `shell.json`.

The suite does not request root, edit `/usr/share/omarchy`, install packages,
upload input, or store typed text. Device and service overrides are accepted
only through documented environment variables used by tests and unsupported
hardware review.

## Theme contract

| Keyboard role | Omarchy colour |
| --- | --- |
| Panel | `background` |
| Character keys | `lighter_background` |
| Function keys | `selection` |
| Pressed keys | `muted` |
| Flick feedback | `accent` |
| Labels | `foreground` |

Invalid values are rejected or replaced with safe fallbacks. Omarchy's
supported `theme-set.d` hook restarts the keyboard service so a theme switch is
visible immediately.

## Development and verification

Run `./test.sh`. The suite verifies the generated layout contract, input
visibility state machine, cover transitions, theme derivation and all four
plugin manifests. If `qmllint` is installed it also lints the QML. See
[`z13/TESTING.md`](z13/TESTING.md) for the physical acceptance checklist and
[`z13/ARCHITECTURE.md`](z13/ARCHITECTURE.md) for ownership boundaries.
See [`RELEASING.md`](RELEASING.md) for the complete release gate.

## Licensing and upstream

The keyboard is derived from
[wvkbd](https://git.sr.ht/~proycon/wvkbd) and remains GPL-3.0 under `LICENSE`.
The Wayland-derived compatibility files retain their licenses documented in
`COPYING` and `COPYING_WESTON`. Omarchy-specific additions in this repository
are distributed under the same GPL-3.0 terms.
