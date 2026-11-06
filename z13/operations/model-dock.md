# Model Dock on the Z13

Updated 6 November 2026. This extends the machine inventory; runtime source and
its agent instructions stay in the dedicated plugin repository.

- Plugin: **Omarchy Model Dock 0.11.0**, previously Local AI.
- Source: [repository](https://github.com/gustavonline/omarchy-llama-cpp-local-ai),
  [validated commit](https://github.com/gustavonline/omarchy-llama-cpp-local-ai/commit/ccc28086d8f8fa99aadeb3370750e24ff1311954).
- Manifest ID: `io.github.gustavonline.local-ai`; older checkouts can still have
  the directory name `gustav.local-ai`. The native widget remains on the right.
- Human interface: numbered model hotbar, 1–5 selection while open, loading pulse,
  start/stop, API URL/model-ID copy and opt-in start at login.
- CLI: `~/.local/bin/omarchy-model-dock`; root skill linked into the owner's
  `.agents/skills`, `.claude/skills` and `.codex/skills` under `omarchy-model-dock`.
- User service: `omarchy-model-dock.service`, with a maintained llama.cpp router.
- Private settings/presets/key: `~/.config/omarchy/model-dock/`.
- Model files: `~/.local/share/models/model-dock/`; small official Qwen3 0.6B and
  1.7B Q8 GGUF starters, pinned and SHA-256 verified.
- Last applied settings: Vulkan0; two parallel requests per model; F16 KV;
  4K context per request for 0.6B and 8K for 1.7B; maximum two resident models.
- Listener: loopback port 8090, authenticated. Use existing SSH/private-network
  access from another machine. No public ingress or firewall changes.
- Tests left the server running; autostart remains **off**. Existing user-manager
  linger was already enabled, but disk encryption and unattended reboot remain
  separate, unresolved machine-policy work.
- A pinned CPU build was also installed under the user's `.local/opt` for a
  fresh-build/inference check; it is not the active serving backend.

The service has read-only home/system protection, private temp and protected
SSH/cloud directories. It runs without root and does not enable built-in runtime
agent/MCP proxy tools. Client profiles use private launchers under
`~/.local/state/omarchy/model-dock/clients/`, without changing normal client defaults.

See the plugin's [setup](https://github.com/gustavonline/omarchy-llama-cpp-local-ai/blob/main/SETUP.md),
[client guide](https://github.com/gustavonline/omarchy-llama-cpp-local-ai/blob/main/docs/CLIENTS.md)
and [live test record](https://github.com/gustavonline/omarchy-llama-cpp-local-ai/blob/main/docs/Z13-VALIDATION.md).
Mac Studio/MLX is [open issue #13](https://github.com/gustavonline/omarchy-llama-cpp-local-ai/issues/13).
The production panel awaits normal owner unlock for the queued shell refresh;
the session was not unlocked or rebooted to test it.

No real key, private profile, network identity, model weights or client credential
file belongs in this repository or its configuration bundle.
