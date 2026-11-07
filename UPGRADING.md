# Upgrade PolyStrata without losing the working Tiel setup

The launcher pins PolyStrata, its Windows runtime assets, and the Tiel GGUF. An upstream release is a candidate until it passes the same model, API, and workload checks as the current install.

## 1. Record the working install

Keep the current clone and its `.tiel` directory in place. Before stopping it, save a private record of what is running. If the service is already stopped, use its last config, launch command, and logs.

| Record | Where to look |
|---|---|
| Starter commit, PolyStrata source commit, engine version, CUDA and llama.cpp DLL versions and asset checksums | `git rev-parse HEAD`, `git -C .tiel/polystrata rev-parse HEAD`, `launcher.py`, and the installed engine's `BUILD.json` when present |
| Actual launch command and resolved run config | Your start command and `.tiel/tiel.json`, including context, threads, VRAM reserve, KV format, batching, MTP, expert profile, conversation cache, sampling and reasoning limits |
| Python, dependencies, driver, and runtime environment | `.tiel/venv/Scripts/python.exe --version`, `-m pip freeze`, `nvidia-smi`, and the config's `env` and `lib_dirs` fields. Record intentional overrides such as `HF_HOME`, `HF_HUB_CACHE`, `CUDA_VISIBLE_DEVICES`, relevant `STRATA_*` flags, and `TIEL_SENSOR_FILE`. The engine config can override the launch shell. |
| Model and local data | Exact GGUF revision, cache or local path, SHA-256, tokenizer, and current expert profile. Save the profile after a clean shutdown if you want a stable backup. |
| Network and clients | Bind address, HTTP port, model ID, Tailscale HTTPS port and proxy target, OMP provider and context limits, key file location, and any sensor bridge settings |
| Performance and quality | Exact prompts, inputs and outputs, sampling settings, hardware load, scores, and raw timing and memory logs |

These commands help record the environment from the working clone. Keep their output local.

```powershell
git rev-parse HEAD
git -C .tiel/polystrata rev-parse HEAD
& .\.tiel\venv\Scripts\python.exe --version
& .\.tiel\venv\Scripts\python.exe -m pip freeze
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv
tailscale serve status --json   # if you use Tailscale
```

Save the existing API key in its private location. Record the name and source of secret environment variables, excluding their values. Avoid exporting the full process environment or committing local configs, API keys, real prompts, or logs.

## 2. Build a candidate beside the old version

From the working starter clone, make a separate worktree. It gets its own `.tiel` directory and Python environment.

```powershell
git worktree add -b polystrata-upgrade ..\tiel-polystrata-candidate HEAD
cd ..\tiel-polystrata-candidate
```

1. Check the [upstream releases](https://github.com/simplexai-labs/PolyStrata/releases) for a Windows CUDA build that supports your GPU, driver, Tiel's `qwen35moe` GGUF, and its embedded MTP head. Identify the matching server source and required libraries. Use official verified artifacts when available. If a source build is needed, follow the build instructions for the selected commit and record the compiler, CUDA version, build flags, and binary hashes.
2. Update the source revision, release URLs, expected filenames, and SHA-256 hashes in `launcher.py`. Update `requirements.txt` if the matching server needs different Python packages. Check every saved flag and environment override against the candidate's CLI and config schema. Check the sensor overlay against the new server and UI, and adapt its hooks if upstream changed.
3. Recreate the runtime from those pins. Keep the same Tiel GGUF revision and reuse the Hugging Face cache or the same `-ModelPath`. Extract the tokenizer again. Start with the same tuning values and a fresh expert profile unless the new version documents profile compatibility. Leave the original venv, binaries and profile in the original clone.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Tiel.ps1 -SetupOnly
& .\.tiel\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Pause the old server after active requests finish. The starter checks for another running model engine before it loads Tiel. Use a spare loopback port and the saved context, threads and reserve. The command below uses the starter's 128K defaults as an example. Add your saved conversation cache or model path options as needed.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Tiel.ps1 -Access Local -Port 8093 -Context 131072 -Threads 12 -VramReserveMiB 640
```

## 3. Run the same tests on both versions

In a second PowerShell in the candidate folder, check the advertised model and run an authenticated completion. An unauthenticated request to `/v1/models` should return 401.

```powershell
$base = 'http://127.0.0.1:8093/v1'
$key = (Get-Content .\.tiel\api-key.txt -Raw).Trim()
$headers = @{ Authorization = "Bearer $key" }
(Invoke-RestMethod "$base/models" -Headers $headers).data |
    Select-Object id, @{Name='Context'; Expression={$_.meta.n_ctx}}
$body = @{
    model = 'tiel-coder'
    messages = @(@{ role = 'user'; content = 'Reply with exactly READY.' })
    temperature = 0
    max_tokens = 192
    reasoning_budget_tokens = 64
} | ConvertTo-Json -Depth 5
(Invoke-RestMethod "$base/chat/completions" -Method Post -Headers $headers `
    -ContentType 'application/json' -Body $body).choices[0].message.content
```

- **Compatibility.** Confirm MTP is active from engine logs, SSE streaming works, and a multi-turn OMP edit-and-test task handles tool arguments and results correctly. Check the UI and authenticated sensor metrics if you use the overlay.
- **Quality and speed.** Run the same representative coding and tool fixtures on both versions. Match GGUF, prompts, actual token counts as closely as possible, sampling, reasoning and output budgets. Separate warm-up, uncached requests and conversation reuse. Record prompt and generation tok/s, time to first token, wall time, MTP acceptance, and executable test results.
- **Context and stability.** Start with actual 8K–32K prompts. If you use 128K, also test about 120K actual input with a retrieval or coding check. Track minimum free VRAM and available RAM, paging, allocation failures, and temperatures under repeated load. Reapply your actual headroom target for a dedicated or shared PC. The reserve flag alone cannot tell you how much free memory remained.

Use the [upgrade agent prompt](UPGRADE-AGENT-PROMPT.md) for the historical Tiel measurements and a fuller tuning checklist. Establish parity with the old settings before sweeping new ones.

## 4. Cut over or roll back

Promote the candidate when it meets the agreed quality, speed, and headroom targets. Stop the test instance. To keep existing clients connected, copy the old key file directly into the candidate's private `.tiel/api-key.txt` and start with the original model ID, bind mode, and port. If using Tailscale, use the original HTTPS port and backend port so the launcher can reuse the existing Serve mapping. Recheck authenticated model listing, streaming generation, OMP tool use and Monitor through the actual client URL.

If anything regresses, stop the candidate and start the original clone with its recorded command and environment. Restore only a Serve mapping you changed, then check the original API and client again. Keep both pinned configurations and the comparison results until the new version has proved stable in normal use.
