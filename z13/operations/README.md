# Z13 operations and configuration

A source bundle and configuration map for the 2025 ROG Flow Z13 running Omarchy. This complements the keyboard, rotation and touch integration already in this repository. Inspected 6 November 2026 on Omarchy 4.0.6.

## What is configured

| Area | Current behaviour | Source or owner |
|---|---|---|
| Touch keyboard | Danish four-layer keyboard, cover detection and input-method switching | Existing z13/runtime, layout and setup files |
| Tablet rotation | Tablet-only rotation; laptop orientation remains landscape | Existing z13/rotation |
| Touch bar | One-tap tray/indicators and an active-window close button | Existing companion widgets |
| Phone-approved root | One phone code opens a chosen 1–15 minute window for multiple agent commands | Separate Omarchy Agent Access repository |
| Closed cover | Selected NetworkManager profile + AC + an already unlocked desktop may retain the session | remote-session/controller |
| Idle/sleep inhibition | A user service holds an inhibitor while the controller owns the appropriate state | remote-session/controller systemd units |
| Night mode | Scheduled 19:00–07:00 black display, quiet audio and bounded manual overrides | remote-session/controller and its plugin |
| Brightness | Minimum brightness can hold the panel black; brightness-up exits that state | omarchy-brightness-screen-off |
| Appearance | Light at 07:00, dark at 19:00; theme, supplied wallpaper and derived screensaver follow | appearance/ |
| App startup | Existing desktop launch starts the chosen ChatGPT/Codex wrapper, T3 Code and Hyprsunset | apps/ and examples/autostart.lua |
| Login | SDDM currently auto-logs in the owner after disk unlock | Owner system configuration; no password/key is included here |
| Remote connection | Existing SSH over Tailscale | Owner access configuration; credentials and host addresses are excluded |
| Local inference | llama.cpp user service with a loopback endpoint; current slot uses Vulkan | Separate Local AI plugin and owner runtime configuration |
| Local transcription | Voxtype with optional local summaries | Separate Local Transcript plugin |

[Omarchy Agent Access](https://github.com/gustavonline/omarchy-passwordless-sudo) owns its root broker, QR enrollment, CLI and agent skill. It is not copied here as a second editable implementation. Its 0.5.0 source includes the centre-bar quick action, configurable duration and native Omarchy panel style.

## Current remote-session policy

The controller checks AC0, the selected NetworkManager connection UUID, lid state, its own running service and Omarchy's native lock state. It does not treat an SSID string as authentication. It only preserves an already unlocked session; it does not unlock the desktop. Loss of a condition requests native lock and restores previously owned idle/inhibitor settings. Opening the cover releases the special closed-cover hold when the normal session is healthy.

A display blackout, a sleep inhibitor, a desktop lock and disk encryption are separate controls. The existing logind drop-in ignores the lid switch on external power. The user controller supplies the narrower network/session rule. The machine can remain reachable while its desktop is locked; phone-approved root access works over the existing SSH connection independently of desktop unlock.

The current optional virtual-output feature is disabled. Its presence in the controller source is not evidence that every headless portal/capture path is qualified.

## Source layout

- remote-session/controller: current controller, brightness and launch wrappers, Lua bindings and user units.
- remote-session/controller/plugin: current night-mode bar widget and manifest.
- appearance: day/night theme script and timer. Wallpaper files are not included; supply your own at the configured paths.
- apps: existing app wrappers. The T3 Code path is normalized to HOME; no application binary is bundled.
- examples: portable templates, not a copy of the owner's private network settings.

The included install.py and 95-z13-night-mode hook preserve user-owned integration after post-boot/post-update events. Its --check mode lists proposed writes without changing the desktop. It does not automatically restart an already running controller merely because source changed.

The night-mode UI reports version 1.1.4 and its separate controller identifies itself as 1.2.0. They are separate components. No installer in the existing touch suite automatically applies this operations bundle.

## Reusing the configuration

Review each component before copying it. The complete controller folder can be kept as the dedicated night-mode package; run python3 install.py --check first and inspect proposed writes before any explicit repair. Keep the controller at ~/.local/share/omarchy-night-mode/control.py, wrappers in ~/.local/bin, the config at ~/.config/omarchy/night-mode.json and user units in ~/.config/systemd/user. Lua additions belong in the user's Hyprland config. The included user units use %h rather than a fixed account path.

Start from examples/night-mode.example.json. Trusted-session mode is deliberately disabled there and its UUID is a synthetic placeholder. Select the intended local NetworkManager profile before enabling it. Do not publish the resulting machine config or Wi-Fi credentials. Adapt timezone, schedule, AC device and lid paths for the actual host. The AC/lid paths in this bundle are the observed Z13 contract, not a universal laptop API.

The example logind file documents an observed root setting. Do not apply it indiscriminately: ignoring a lid on AC alone is broader than a trusted-network condition. The other observed root settings are HandlePowerKey=ignore and InhibitDelayMaxSec=15. Preserve Omarchy's native sleep-lock integration when reviewing them.

Keep setup explicit. Do not overwrite /usr/share/omarchy, reset the owner's shell layout or remove unrelated services. The existing touch setup/remove scripts retain their original scope.

## Disk, reboot and unattended maintenance

The root/home filesystem is LUKS-encrypted. Inspection found one keyslot and no enrolled token types. The active mkinitcpio drop-in uses Omarchy's encrypt hook; the boot loader is Limine. TPM hardware is present, Secure Boot is disabled and existing TPM/PCR units report failures. Those observations do not prove defective TPM hardware, and no new disk key or token was enrolled.

Unattended reboot is not ready. SDDM/app autostart only applies after the encrypted disk has been unlocked. It does not prove that an interrupted agent job resumes. No reboot, automatic OS update, new update timer or early-boot unlock policy was installed during this work.

The remaining work is:

1. Extend the existing controller to a deliberate server mode for network + AC in both cover states, preserving manual lock, night mode and failure recovery.
2. Qualify early-boot disk unlock with the desired conditions. A network-bound service must live outside the disk it unlocks; TPM enrollment alone does not check the network or AC. Keep the existing passphrase/recovery route and a protected header/boot backup before changing boot policy.
3. Add a maintenance flow that checks active work, waits for a safe boundary, updates, reboots only when authorized and verifies return of the desktop, services and actual agent workflows.
4. Test correct/wrong/missing network, AC loss, manual lock, suspend and a controlled reboot with owner recovery available.

## Verification and limits

Agent Access was live-tested using phone codes sent by the owner in chat: multiple root commands shared one window; a later command was denied after expiry; ordinary passwordless sudo remained denied. The old broad Omarchy timer is closed. Fresh installation, enrollment, upgrade preservation and rollback also passed in an isolated container with synthetic credentials.

The bundled policy tests exercise synthetic network, power, cover, native-lock and controller-health inputs without touching the real desktop:

    python3 -B remote-session/controller/test_policy.py

Physical cable/network changes and reboot were not tested here. The final desktop quick-click behaviour is covered by command-level tests and a fresh component compilation; a full pointer test of the latest panel awaits an unlocked desktop. This repository does not claim complete history of every past experiment: it collects the relevant current components found in the touch suite, selected user scripts/units, dedicated night-mode source and plugin repositories. Personal context, model weights, recordings, credentials and raw application state are not mirrored.
