# Tiel Coder on PolyStrata

A Windows x64 launcher for **Tiel Coder 35B-A3B MTP UD-Q4_K_XL** on NVIDIA CUDA. It uses the tested PolyStrata engine, a 128K context, and a text-only web UI and OpenAI-compatible API. Use the API from Oh My Pi on the same PC or another device.

## Start

Install [Git for Windows](https://git-scm.com/download/win) and a [current NVIDIA driver](https://www.nvidia.com/en-us/drivers/). The tested system used an RTX 5060 with 8 GB VRAM and 32 GB system RAM. Allow about 27 GB of free disk space for a new installation, including the 22.75 GB model. The model cache and repo can be on different drives.

After cloning this repository, open PowerShell in the clone and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Tiel.ps1
```

The launcher uses WinGet to install Python 3.11 and the x64 Visual C++ runtime if missing. Windows may ask for elevation during package installation. It creates its own Python environment, fetches the pinned PolyStrata server and CUDA runtime, downloads or reuses the GGUF from the standard Hugging Face cache, extracts its tokenizer, and starts the server. The same command works on subsequent runs. The execution policy override applies to this PowerShell process.

- Web UI: `http://127.0.0.1:8092/`
- API base: `http://127.0.0.1:8092/v1`
- Model ID: `tiel-coder`
- API key: `.tiel/api-key.txt`, generated once per clone
- Stop: press **Ctrl+C** in the launch window

The launcher runs in the foreground. Stop another PolyStrata, Strata, or llama-server instance before starting this one. Keep the terminal open while using the API.

If you are migrating an existing OMP setup and want to keep its key, copy the old key file to `.tiel/api-key.txt` before launching. Create the `.tiel` folder if needed.

If you already have the **exact** GGUF outside the Hugging Face cache, pass it directly:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Tiel.ps1 -ModelPath 'D:\Models\Tiel-Coder-35B-A3B-MTP-UD-Q4_K_XL.gguf'
```

Add `-SetupOnly` to install and validate files without starting the server. For a cache on another drive, set `$env:HF_HUB_CACHE = 'D:\HuggingFace\hub'` before the first run.

## Tailscale HTTPS

1. [Install Tailscale](https://tailscale.com/download) on the Windows host and the client. Sign in to the same tailnet and enable [MagicDNS and HTTPS certificates](https://tailscale.com/docs/how-to/set-up-https-certificates) for the tailnet.
2. Start Tiel in Tailscale mode.

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Tiel.ps1 -Access Tailscale
   ```

3. Use the printed `https://<device>.<tailnet>.ts.net/v1` API base and the generated key. The printed HTTPS URL without `/v1` opens the UI.

Tailscale Serve proxies HTTPS to the loopback listener. Tailnet access rules still apply. The default external HTTPS port is 443 and the backend port is 8092. If 443 is already used by another route, try `-TailscalePort 8443`. The launcher reuses a matching root route and refuses conflicting routes or an active Funnel on that port. HTTPS Serve and SSH use separate ports.

The Serve mapping persists when you stop Tiel so the URL works again when you restart. If you own the route and want to remove it, use `tailscale serve --https=443 off` (substitute your chosen port).

## Direct LAN HTTP

Use the host's private IPv4 address from `ipconfig`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Tiel.ps1 -Access LAN -LanAddress 192.168.50.20
```

The launcher binds that address only. If Windows Firewall blocks the connection, on a trusted network set to **Private**, run this in an administrator PowerShell with your own IP and port:

```powershell
New-NetFirewallRule -DisplayName 'Tiel PolyStrata LAN' -Direction Inbound -Action Allow -Protocol TCP -LocalAddress 192.168.50.20 -LocalPort 8092 -RemoteAddress LocalSubnet -Profile Private
```

Use the printed HTTP address from the other device. LAN HTTP sends the key without TLS, so use a trusted LAN or choose Tailscale HTTPS.

## Connect Oh My Pi

1. Copy the `polystrata` provider entry from the generated `.tiel/omp.models.yml` into the existing `providers` section of `~/.omp/agent/models.yml` on the OMP machine. If that file is new, copy the whole template. The generated template already has the selected URL and context.
2. Make the key available as `POLYSTRATA_API_KEY` in the shell that starts OMP. Copy `.tiel/api-key.txt` to a private file on the client if needed. The YAML uses the environment-variable name.

   macOS or Linux:

   ```sh
   export POLYSTRATA_API_KEY="$(tr -d '\r\n' < ~/.config/tiel-api-key.txt)"
   omp --model polystrata/tiel-coder
   ```

   Windows, from the launcher folder on the same PC:

   ```powershell
   $env:POLYSTRATA_API_KEY = (Get-Content .\.tiel\api-key.txt -Raw).Trim()
   omp --model polystrata/tiel-coder
   ```

Restart any open OMP sessions so they read the provider. The template includes Qwen thinking and tool-call replay settings. [OMP model configuration reference](https://github.com/can1357/oh-my-pi/blob/main/docs/models.md).

## Options and troubleshooting

| Option | Default | What it changes |
|---|---:|---|
| `-Context` | 131072 | Total context. Try `32768` on a tighter system. |
| `-Threads` | 12 | CPU worker threads. |
| `-VramReserveMiB` | 640 | GPU memory headroom. Try `1280` if other GPU apps cause allocation failures. |
| `-Port` | 8092 | PolyStrata HTTP port. |
| `-TailscalePort` | 443 | Tailscale Serve HTTPS port. |
| `-ConversationCacheMiB` | 0 | Optional host RAM for retaining state across alternating conversations. Try `8192` only if you have spare RAM. Generation remains serial. |

For startup errors, check the terminal and `.tiel/engine.log`. For a remote connection that opens the UI but fails in an API client, verify the `/v1` suffix, bearer key, and model ID.

```powershell
$key = (Get-Content .\.tiel\api-key.txt -Raw).Trim()
Invoke-RestMethod -Uri 'http://127.0.0.1:8092/v1/models' -Headers @{ Authorization = "Bearer $key" }
```

## Versions

This starter fetches the tested upstream PolyStrata code and engine at fixed versions. To evaluate a newer release and tune it for your machine, give a coding agent the [upgrade and tuning prompt](UPGRADE-AGENT-PROMPT.md).

PolyStrata engine `v0.1.45-poly.7` with server commit `fabae0d6445e524a1dc68b2c2fa99b53880f98e6`, CUDA runtime and libraries from llama.cpp `b12128`, and Tiel GGUF revision `bb5f3f441849fc24c2d9037c310bc995404bfa0c`. Downloads come from the upstream projects. The repository contains the launcher and templates. Runtime files, logs and API keys live in the ignored `.tiel` directory.

[PolyStrata](https://github.com/simplexai-labs/PolyStrata) · [llama.cpp](https://github.com/ggml-org/llama.cpp) · [Tiel Coder GGUF](https://huggingface.co/peculiar-ragdoll/Tiel-Coder-35B-A3B-GGUF-MTP) · [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve)
