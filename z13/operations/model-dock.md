# Model Dock on the Z13

Updated 6 November 2026. This extends the machine inventory; runtime source and
its agent instructions stay in the dedicated plugin repository.

- Plugin: **Omarchy Model Dock 0.11.1**, previously Local AI.
- Source: [repository](https://github.com/gustavonline/omarchy-llama-cpp-local-ai),
  [validated commit](https://github.com/gustavonline/omarchy-llama-cpp-local-ai/commit/6173451c57266d5248c3d1e90a36e6d4d58670ad).
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
- Larger text model: `~/.local/share/omarchy/model-dock/weights/Qwen3.8-27B-Q4_K_M.gguf`,
  an SHA-256-verified CoW copy of an existing Ollama artifact; not a second download.
- Last applied settings: Vulkan0; two parallel requests per model; F16 KV;
  4K context per request for 0.6B and 8K for 1.7B; maximum two resident models.
  Qwen 3.8 27B has one 65,536-token slot, F16 KV, MTP draft length 4,
  physical batch 512 / logical batch 2048 and a 12,288 MiB saved-state RAM cap.
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

The 27B follow-up measured about 24–26 output tokens/s on generated Python. A
real Pi CSV-repair task passed 13 unchanged tests in 80.53 seconds with the final
profile. Full new 60K input took 648 seconds to first answer; the repeated prompt
took 0.407 seconds and reused 60,059 tokens. These are separate measurements;
a 64K limit does not make a new long prompt cheap. Larger prompt batches were
slower in the matched short probe, so 512 was retained. See the detailed
[27B/64K record](https://github.com/gustavonline/omarchy-llama-cpp-local-ai/blob/main/docs/QWEN38-Z13.md).

The Mac was tested with its existing Pi client over SSH. A private per-owner
Terminal shortcut was prepared; no Mac app, public control endpoint or new
remote-desktop setup was added. Existing normal client defaults were preserved.
