# Prompt for rebuilding and tuning Tiel Coder on PolyStrata

Copy everything below the divider into your coding agent. It can clone the [public starter repository](https://github.com/baskervile/tiel-polystrata) or work inside an existing clone. The prompt includes the baseline numbers for use without the original benchmark files.

---

Rebuild or update my **Tiel Coder 35B-A3B MTP** setup on the best supported current PolyStrata runtime for my machine. I use it for coding and tool use in Oh My Pi (OMP), sometimes from another device. I want a repeatable clone-and-run installer, measured tuning, and a working OpenAI-compatible API. Carry out the work if you have shell access. Mark untested steps explicitly if you cannot run them.

Use the public starter at `https://github.com/baskervile/tiel-polystrata.git`. If it is already checked out, use that copy. Otherwise, run `git clone https://github.com/baskervile/tiel-polystrata.git`. Read `README.md`, `Run-Tiel.ps1`, `launcher.py`, `monitor/`, and the tests before changing anything. Keep candidate changes on a separate branch or in an isolated checkout. Share the verified commit and results, and publish them only if I ask. If publishing requires GitHub sign-in, use an authorized connector or browser login flow. Keep tokens out of chat and the repo.

Before publishing, check the files and commit history for credentials, real tailnet names and addresses, machine-specific paths, and private logs. Use the repository owner's authorized Git identity for commits. Omit automated co-author trailers and promotional branding.

## Ask me before choosing a performance profile

1. **Context:** What total capacity and typical actual prompt lengths do I need? Offer 32K, 128K, and 256K if supported. Ask separately whether I need a filled-context test. My previous target was 50+ generation tok/s and 700–2,000 prompt tok/s at actual 8K–32K first, then a roughly 120K input test for a 128K profile. A 256K capacity claim needs its own verification.
2. **Machine use:** Is this a dedicated inference host while the model runs, or will I also work on it locally? Ask how much *measured* free VRAM and available system RAM to preserve and what else will run. On a dedicated host I may accept 200–300 MiB free VRAM if the setup proves stable. For a shared desktop, start with a larger margin, such as about 1.3 GiB free VRAM, if that suits my workloads. Ask for a RAM budget separately. Treat these as requested operating margins, not engine flag values.
3. **Access and clients:** Do I need localhost only, LAN HTTP, Tailscale HTTPS, or more than one? Ask whether to keep an existing port, OMP provider ID, key, and Serve route. Ask how many OMP sessions will alternate and whether I actually need simultaneous generation.

While waiting, inspect the machine and existing files without interrupting services. Detect OS, CPU and thread topology, RAM and available RAM, GPU and driver, free VRAM at idle, disk capacity, model cache paths, installed runtimes, current listeners, and active generations. My reference machine was Windows x64, Ryzen 9 8945HX, RTX 5060 8 GB, 32 GB installed RAM, and a single DDR5-5200 DIMM. The AMD iGPU did not participate in the reference tests.

## Preserve the working setup and evaluate the newest runtime

- Follow `UPGRADING.md` to record the resolved config, launch environment, runtime pins, and baseline before replacing any component. Carry forward intentional overrides and keep the original install available for rollback.
- On Linux, follow `LINUX.md`. Start with upstream PolyStrata and compare the same GGUF against llama.cpp and ik_llama.cpp if useful. Qualify forks for the exact model and hardware before treating their published speeds as applicable.
- The starter repo is a launcher around upstream PolyStrata with a small telemetry and web UI overlay under `monitor/`. It keeps the native inference engine upstream. Our known-good combination was **PolyStrata v0.1.45-poly.7** Windows CUDA native engine (`strata-poly.exe`), server commit `fabae0d6445e524a1dc68b2c2fa99b53880f98e6`, and the CUDA DLL/runtime assets from **llama.cpp b12128**. The old bootstrap used a sparse checkout and per-checkout `core.longpaths=true` on Windows, verified release archive SHA-256 hashes, and kept the runtime in an ignored local directory. If I want to retain the hardware monitor, check what the new release provides, port the remaining overlay hooks and verify the optional Libre Hardware Monitor snapshot bridge and authenticated readings.
- Inspect the official [PolyStrata repository and releases](https://github.com/simplexai-labs/PolyStrata/releases), current setup instructions, source, release metadata, and CLI help. Fetch the newest compatible release and matching server into a separate location. Verify that it supports this exact GGUF architecture (`qwen35moe`), embedded MTP, your hardware and driver, and the API behavior below. Prefer its official binary and installer where they meet the requirements. Build from a pinned source commit only if needed. Keep source, binary, runtime dependencies, config, and version or hashes in the results. Separate upstream behavior from any local patch.
- Keep the working install available for rollback. Run the candidate on a separate port and in a separate state directory. On a memory-constrained host, test GPU runtimes one at a time. If an existing service must pause, check for active requests, verify process ownership, restore it after testing, and verify its API. Keep the existing service unless the candidate meets the agreed speed, quality, memory, and API requirements.

## Install the same model through Hugging Face

- Baseline [Tiel Coder MTP repo](https://huggingface.co/peculiar-ragdoll/Tiel-Coder-35B-A3B-GGUF-MTP) is `peculiar-ragdoll/Tiel-Coder-35B-A3B-GGUF-MTP`. Use `Tiel-Coder-35B-A3B-MTP-UD-Q4_K_XL.gguf` at revision `bb5f3f441849fc24c2d9037c310bc995404bfa0c`. Expected size **22,749,880,160 bytes** and SHA-256 `54f46c4ce544c225122b0f066c2336f10404be7bc53b0cc94d1dbbc5e826bdc1`.
- Use `huggingface_hub.hf_hub_download` or the `hf download` equivalent with the pinned revision. Respect `HF_HUB_CACHE`/`HF_HOME` and reuse the returned snapshot path directly. The default hub cache is typically `~/.cache/huggingface/hub`. Avoid creating a second 22.75 GB copy in the repo. Support an explicit path to the same verified file. Verify the model metadata and integrity, use its embedded tokenizer and chat template, and run tokenizer round-trip tests if the backend exposes them. Our tested profile was text-only. Keep the model weights unchanged.

## Make the server usable

- Use the upstream PolyStrata server and web UI when possible. Preserve OpenAI Chat Completions at `/v1/chat/completions`, streaming SSE, `/v1/models`, and model ID `tiel-coder` unless I choose otherwise. Validate text generation, JSON function arguments, a multi-turn tool call and tool result with reasoning replay, and the configured context advertised to the client. Use executable tests to grade the agent's patch. An HTTP 200 alone is insufficient.
- Default to an authenticated loopback listener such as `127.0.0.1:8092`. Reuse a user-selected existing key or generate one once and keep it in ignored local state. Keep secret values out of the repo, command-line arguments, logs and reports. Test that requests without a key return 401 and authenticated requests work. Offer explicit LAN binding to a selected private address. Scope any Windows firewall rule to that interface, port and trusted subnet, and explain that LAN HTTP lacks TLS.
- For remote HTTPS, prefer [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve) forwarding to the loopback API. Detect sign-in, MagicDNS, HTTPS support, and existing routes. Reuse the correct route or choose a free HTTPS port. Preserve unrelated routes and SSH. Keep it tailnet-only, without Funnel. Verify the tailnet HTTPS URL with the bearer key, and report whether verification was from the host or a second device.
- Generate an OMP provider snippet that can be merged into existing `~/.omp/agent/models.yml`. Use API `openai-completions`, model `tiel-coder`, a base URL ending in `/v1`, a key from an environment variable, correct context and output limits, text input, and the current OMP equivalents of Qwen thinking controls and `requiresReasoningContentForToolCalls`. Verify against the [OMP configuration reference](https://github.com/can1357/oh-my-pi/blob/main/docs/models.md).

## Tune against measured results

Start with the quality-preserving baseline: **Q8_0 attention KV**, native MTP, 12 CPU threads, embedded tokenizer/template, and tail skipping, expert weight skipping and cache-biased routing disabled. Native PolyStrata selected hot experts for VRAM and adapted placement as it ran. The 128K starter uses a nominal **640 MiB** reserve, 4,096 reasoning tokens, top-p .95, top-k 20, min-p 0, and a persistent expert profile. The 32K comparison used prompt batch 2048 and a 1,536 reasoning-token test budget. Check what the new build supports before copying flag names. Keep prompt, sampling, output cap, reasoning budget and model revision fixed when comparing settings.

| Historical workload | Capacity | Reserve flag | Prompt tok/s | Generation tok/s | Outcome |
|---|---:|---:|---:|---:|---|
| Tiel, 8,128-token dependency-order task | 32K | 1280 MiB | 1,239.4 | 56.0 | Pass, 38.76 s |
| Tiel, same ~8K task with more expert VRAM | 32K | 896 MiB | 1,249.3 | 60.7 | Pass, 36.25 s, 343 MiB sampled free VRAM minimum |
| Tiel, 30,720-token synthetic code prefill | 128K | 640 MiB | 1,911.7 | 64.2 | 512 output, 24.08 s |
| Tiel, 122,880-token synthetic code prefill | 128K | 640 MiB | 1,528.5 | 54.4 | 512 output, 89.88 s |
| llama.cpp b12128, same 30,720-token test | 128K | — | 563.2 | 36.6 | 512 output, 68.60 s |
| llama.cpp b12128, same 122,880-token test | 128K | — | 506.1 | 32.2 | 512 output, 258.72 s |

The 128K PolyStrata run sampled **429 MiB minimum free VRAM** and about **1.03 GiB minimum available RAM**. A 32K run at 768 MiB reserve sampled **203 MiB free VRAM** and was stopped before grading. These are snapshots from roughly one-second sampling. The reserve flag does not promise that much actual free VRAM. The 120K run demonstrated throughput and completion. It did not grade retrieval or coding across the whole prompt. 256K was untested.

At 32K configured capacity, Tiel passed **4/4** short coding cases on the first attempt and the scripted repair in **3 calls / 7.35 s**. An older 128K configuration failed the same class of agent repair, so recheck tool quality after an update. Apex-35B reached **1,412.9 prompt / 60.3 generation tok/s** at ~8K in the matched screen but failed that coding case, passed **2/4** short tasks first try and failed the repair. We kept Tiel for coding and tool use. These were small local tests.

- Sweep context capacity, nominal VRAM reserve, CPU threads, and prompt batch in a bounded experiment. Compare cold load, warm uncached prefill and decode, then separately measure reusable conversation state. Log actual input and output lengths, cache reuse, MTP acceptance, expert residency, time to first token, wall time, peak and minimum memory, paging, errors, and correctness. Use repeated representative tests, including an actual coding prompt and an edit-and-test tool workflow. Test near the agreed context with a retrieval or code task as well as throughput.
- Start from one inference slot. In our ~8K four-client screen at 128K capacity, one slot finished the wave in **58.9 s** vs **130.3 s** with two slots and **117.9 s** with four, under a 256-token thinking budget. If I alternate between OMP sessions, test conversation parking separately and measure its host RAM cost. It does not imply concurrent generation. Test parallel decode only if I need it.
- Increase VRAM allocation in steps while watching *actual* free VRAM during long prefill, decode and alternating sessions. Test dedicated and shared presets independently if I need both. Back off after allocation failures, heavy paging, unstable output, or breaches of the agreed margins. Keep failures in the experiment log. Prefer the fastest profile that meets the quality, headroom and stability criteria.

## Deliver

Provide a clean repo with a README, install/start script, model-cache reuse, access options, OMP snippet, repeatable benchmark commands, and instructions to stop, upgrade and roll back. Include the tested versions, raw results and a table of every material run, including failed ones. Supply a known-good preset and the best measured preset for the requested hardware and operating mode. Verify first launch, repeat launch without re-downloading the model, authenticated generation, and cleanup. Say which tests you could not run.

If the original workspace is available, the reference records are `results/polystrata-comparison/REPORT.md`, `results/quick-coding-comparison-20261106/REPORT.md`, `results/tiel-parallel-20261106/REPORT.md`, `results/apex-polystrata/matched-32k/apex-8k.json` and `results/tiel-quality/apex-polystrata-matched-32k/results.json`.
