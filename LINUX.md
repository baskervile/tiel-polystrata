# Run Tiel Coder on Linux

Start with **upstream PolyStrata** for an 8 GB NVIDIA GPU and 32 GB RAM. It lists the exact Tiel Coder `qwen35moe` GGUF and its embedded MTP head. Use **upstream llama.cpp** as the comparison baseline and **ik_llama.cpp** as the first performance fork to test on NVIDIA. For AMD RDNA 2, see the [RX 6600M route](#amd-radeon-rx-6600m-rdna-2). The measurements in this repository came from Windows. The Linux commands below were checked against the relevant upstream sources and CLI, and still need an end-to-end run on Linux hardware. [PolyStrata model and backend support](https://github.com/simplexai-labs/PolyStrata/blob/main/docs/BACKENDS.md) · [Tiel model card](https://huggingface.co/peculiar-ragdoll/Tiel-Coder-35B-A3B-GGUF-MTP)

## 1. Download or reuse the exact GGUF

Use native Linux for Windows-versus-Linux performance comparisons. On Ubuntu or Debian, install the basic tools with `sudo apt install git python3 python3-venv curl openssl`. Install a driver suitable for your GPU and verify that `nvidia-smi` sees the card before continuing on NVIDIA. The source build below also needs CMake, a C/C++ toolchain, and a CUDA toolkit compatible with your GPU. An RTX 5060 needs a build with Blackwell support. Plan for the 22.75 GB model plus runtime and build files, and put the cache on an SSD.

Run the commands in Bash. Hugging Face reuses its cache and prints the local snapshot file. Set `HF_HUB_CACHE` before the download if you use a different cache directory.

```bash
python3 -m venv "${XDG_DATA_HOME:-$HOME/.local/share}/tiel-hf"
"${XDG_DATA_HOME:-$HOME/.local/share}/tiel-hf/bin/python" -m pip install huggingface_hub==2.4.0
hf_cli="${XDG_DATA_HOME:-$HOME/.local/share}/tiel-hf/bin/hf"
model="$("$hf_cli" download peculiar-ragdoll/Tiel-Coder-35B-A3B-GGUF-MTP \
  Tiel-Coder-35B-A3B-MTP-UD-Q4_K_XL.gguf \
  --revision bb5f3f441849fc24c2d9037c310bc995404bfa0c)"
printf '%s  %s\n' '54f46c4ce544c225122b0f066c2336f10404be7bc53b0cc94d1dbbc5e826bdc1' "$model" | sha256sum -c -
```

Proceed only if the checksum passes. If you already have the GGUF, set `model` to its absolute path and run the same check. Use the published filename for the PolyStrata installer. If your local file is named differently, create a symlink with the published filename in a folder you control, then point `model` at that symlink.

Create a private key file for either server. Keep the same file if you already use this path for OMP.

```bash
key_dir="${XDG_CONFIG_HOME:-$HOME/.config}/tiel-polystrata"
key="$key_dir/api-key.txt"
umask 077
mkdir -p "$key_dir"
if [ ! -s "$key" ]; then openssl rand -hex 32 > "$key"; fi
chmod 600 "$key"
```

## 2. Start PolyStrata

Use the upstream Linux installer. The example pins the server commit used by the Windows starter so the flags and generated filenames are reproducible. To evaluate a newer release, pin its matching source and use the [upgrade runbook](UPGRADING.md#linux-upgrades). The Windows launcher and Libre Hardware Monitor bridge are Windows-specific.

```bash
git clone https://github.com/simplexai-labs/PolyStrata.git polystrata-linux
cd polystrata-linux
git checkout --detach fabae0d6445e524a1dc68b2c2fa99b53880f98e6
./setup.sh --help
./setup.sh --yes --setup --no-start --no-browser \
  --family tiel --model UD-Q4_K_XL --gguf-dir "$(dirname "$model")" \
  --backend cuda --vision none --context 32768 \
  --parallel 1 --vram-reserve-mib 1280 --host 127.0.0.1 --port 8092
STRATA_API_KEY="$(cat "$key")" ./run-tiel-ud-q4_k_xl.sh
```

The explicit `tiel` family matters. Generic `--custom-gguf` detection on this pinned source classified the same file under Qwen3.6. `--gguf-dir` points Tiel setup at the existing file. The generated `strata-tiel-ud-q4_k_xl.json` contains the engine path, arguments and API model ID. Use the reported ID in clients, or set `model_name` to `tiel-coder` in that file before starting if you want the starter's existing OMP alias. Keep the API key in the environment or a private key file.

Once 32K works, rerun setup with `--context 131072` or configure the corresponding `--max-context` in the generated engine args. Compare the actual flags against the Windows profile before attributing any difference to Linux. For example, the Windows profile used Q8_0 KV and 12 threads. If you need those exact values, check the native engine's `--help` and set `--kv q8_0` and `--threads 12` in its generated `args` list. The setup-level `--kv` option has a different scope. Record the effective reserve and measure actual free VRAM. For AMD, check PolyStrata's documented GPU support and follow the HIP path only on a supported card. An AMD iGPU and NVIDIA dGPU on the same system do not establish mixed-device support for this model. [Upstream setup](https://github.com/simplexai-labs/PolyStrata/blob/main/docs/AI_SETUP.md) · [AMD HIP notes](https://github.com/simplexai-labs/PolyStrata/blob/main/docs/AMD_HIP.md)

## 3. Compare with llama.cpp and Linux forks

### AMD Radeon RX 6600M (RDNA 2)

The RX 6600M has 8 GB of VRAM and is expected to report `gfx1032`. On a laptop with integrated graphics, verify that the runtime selected the discrete Radeon. Start with **PolyStrata HIP**. PolyStrata documents a Fedora run on the related desktop RX 6600 XT, using a native `gfx1032` build and Qwen3.6 UD-Q4_K_M. The owner measured 69 tok/s on one generation. That result used a different GPU and model, and Tiel on the RX 6600M still needs a test. [AMD mobile GPU specifications](https://www.amd.com/en/newsroom/press-releases/2021-5-31-amd-unveils-rdna-2-based-mobile-graphics-new-amd-.html) · [PolyStrata HIP notes](https://github.com/simplexai-labs/PolyStrata/blob/main/docs/AMD_HIP.md) · [RX 6600 XT community run](https://github.com/VecSzn/PolyStrata/discussions/49)

In the upstream checkout from step 2, use the same `model` and `key`. If a system ROCm is installed, check `rocminfo` for the discrete GPU and its native target. PolyStrata can build a HIP engine with its documented `gfx103X-all` wheel path where supported. Confirm setup's chosen GPU and backend before loading. If setup lists both GPUs, add `--gpu N` with the discrete GPU's index from setup. Clear any inherited architecture override before setup and launch.

```bash
unset HSA_OVERRIDE_GFX_VERSION
./setup.sh --check --backend hip
./setup.sh --yes --setup --no-start --no-browser \
  --family tiel --model UD-Q4_K_XL --gguf-dir "$(dirname "$model")" \
  --backend hip --vision none --context 8192 \
  --parallel 1 --vram-reserve-mib 1280 --host 127.0.0.1 --port 8092
STRATA_API_KEY="$(cat "$key")" ./run-tiel-ud-q4_k_xl.sh
```

Run the authenticated API checks below and a short coding/tool task. Then raise context to 32K and only try 128K once headroom and stability are measured. The upstream HIP path can allocate KV at startup, so context changes can affect load-time VRAM more than on the CUDA setup. If HIP cannot find a working native runtime, use **llama.cpp Vulkan** as the fallback or comparison. Verify the Vulkan driver with `vulkaninfo --summary`, use the same llama.cpp checkout as the CUDA example below, and build in a separate directory. [llama.cpp Vulkan build instructions](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md#vulkan)

```bash
cmake -S . -B build-vulkan -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build-vulkan --config Release --target llama-server -j 4
build-vulkan/bin/llama-server --list-devices
```

Reuse the llama.cpp server command below with the Vulkan binary, `--device` set to the discrete Radeon device name shown by `--list-devices`, and `-c 8192` for the initial smoke test. Start with `--spec-type none` and omit `--spec-draft-n-max`, then test embedded MTP separately for both correctness and throughput.

The AMD-focused **Strata-rdna3** fork targets RDNA 3 `gfx1100` and its published benchmark is Flash-Next. The **strata-gfx906** builds target Vega hardware such as MI50, MI60, and Radeon VII. These target different GPU architectures from the RX 6600M. [Strata-rdna3](https://github.com/nicejunjie/Strata-rdna3) · [Strata gfx906 build notes](https://github.com/webzone/strata-gfx906/blob/gfx906/docs/GFX906.md)

### Engine shortlist

| Engine | When to test it |
|---|---|
| [PolyStrata](https://github.com/simplexai-labs/PolyStrata/blob/main/docs/BACKENDS.md) | First run for Tiel. Upstream explicitly supports this quant and its embedded draft head. |
| [Upstream llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md) | Reference and fallback. The Windows comparison already ran this exact file with embedded MTP and CPU expert offload. |
| [ik_llama.cpp](https://github.com/ikawrakow/ik_llama.cpp) | First fork to try for Tiel. It has merged [qwen35moe MTP support](https://github.com/ikawrakow/ik_llama.cpp/pull/1745) and a [GPU cache for host experts](https://github.com/ikawrakow/ik_llama.cpp/pull/2644). Verify `--moe-cache-mib` availability on your build and GPU. Compare it with static offload at similar peak VRAM, and check Tiel's embedded template, function calls, and draft acceptance. |
| [Avalon](https://github.com/freriadoc/Avalon) | A Flash-Next-specific experiment. Its expert cache is worth looking at if you switch to Qwen3.8 Flash-Next. Its published speeds are for a different model and setup. |
| [Strata-rdna3](https://github.com/nicejunjie/Strata-rdna3) | Relevant for Qwen3.8 Flash-Next on AMD RDNA3, including dual 7900 XTX. Its HIP optimizations and reported results do not establish a Tiel speedup on an RTX 5060. |

To build the reference on NVIDIA, install CMake, a C++ compiler, the CUDA toolkit, and the distribution's libcurl development package. For a matched starting point, use the llama.cpp tag from the Windows baseline. Use one model server at a time if both cannot fit.

```bash
git clone --branch b12128 --depth 1 https://github.com/ggml-org/llama.cpp.git llama-tiel-baseline
cd llama-tiel-baseline
cmake -S . -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release --target llama-server -j 4
build/bin/llama-server --help
build/bin/llama-server -m "$model" --host 127.0.0.1 --port 8093 \
  --api-key-file "$key" --alias tiel-coder --jinja --fit off \
  -c 32768 -np 1 -ngl 99 --n-cpu-moe 38 -t 12 -tb 16 -b 2048 -ub 1024 \
  -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --spec-draft-n-max 2
```

The offload count is a starting point from the 8 GB Windows profile. If VRAM is tight, try placing more expert layers on the CPU, and measure the effect on speed. Compare one run with `--spec-type none` to check MTP's contribution. For the fork, build separately from a recorded commit and use its own server help. Its cache and MTP options can differ. [llama.cpp build instructions](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md) · [llama.cpp server options](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

## 4. Verify the API and connect OMP

In a second Bash shell, run the following against PolyStrata. Use port 8093 for the llama.cpp example. Expect 401 without credentials, then a model listing and a chat completion with credentials. Copy the model ID returned by the listing into `model_id` if you kept PolyStrata's generated alias.

```bash
base='http://127.0.0.1:8092/v1'
key="${XDG_CONFIG_HOME:-$HOME/.config}/tiel-polystrata/api-key.txt"
model_id='tiel-coder-35b-a3b-ud-q4_k_xl'
curl -sS -o /dev/null -w '%{http_code}\n' "$base/models"
printf 'Authorization: Bearer %s\n' "$(cat "$key")" |
  curl -fsS --header @- "$base/models"
printf 'Authorization: Bearer %s\n' "$(cat "$key")" |
  curl -fsS --header @- -H 'Content-Type: application/json' \
    --data "{\"model\":\"$model_id\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with READY.\"}],\"max_tokens\":256}" \
    "$base/chat/completions"
```

Keep the inference server on loopback for Tailscale. Once both machines are signed in and HTTPS is enabled, inspect Serve before changing it. If port 443 already proxies the desired backend, reuse that mapping. If it serves another app, pick a free HTTPS port with `--https=8443` and include that port in the client URL.

```bash
tailscale serve status
tailscale serve --bg --https=443 http://127.0.0.1:8092
```

Use the printed HTTPS URL plus `/v1` for OMP. For llama.cpp on 8093, point an unused Serve route at 8093, or move the selected production server back to 8092 after testing. Keep tailnet-only Serve and bearer authentication enabled. [Tailscale Serve reference](https://tailscale.com/docs/reference/tailscale-cli/serve)

Copy the [OMP provider template](omp.models.yml) into the client's existing `providers` mapping. Set `baseUrl` to the chosen backend's API URL, and use the model ID and context it reports. For the 32K smoke test, use `contextWindow: 32768` and a smaller output budget such as `maxTokens: 8192`. Load the key as `POLYSTRATA_API_KEY` on the client. Validate reasoning replay and a multi-turn tool call on each backend before using it as your daily provider. The [upgrade runbook](UPGRADING.md) describes the acceptance checks.

## 5. Decide what actually runs faster

On the same host and quantization, measure one cold start and several warm uncached passes. Use actual 8K and 30K inputs first. At 128K capacity, also test about 120K input with a retrieval or coding task. Record prompt and decode tok/s separately, plus time to first token, MTP acceptance, minimum free VRAM and available RAM, and whether the resulting code passes tests. Keep dedicated-host and desktop headroom settings separate. Linux tools such as `nvidia-smi`, `free -h`, `vmstat 1`, and `sensors` can track pressure and exposed hardware temperatures during a run.

Use the [Windows measurements](UPGRADE-AGENT-PROMPT.md#tune-against-measured-results) as reference points. A different model, quantization, context occupancy, warm cache or GPU can change both rates enough to overwhelm the OS difference.
