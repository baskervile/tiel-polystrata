"""Install the pinned Tiel runtime and run its authenticated PolyStrata server."""

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

import psutil
import requests
from huggingface_hub import hf_hub_download

from monitor import install_monitor

ROOT = Path(__file__).resolve().parent
SOURCE = 'https://github.com/simplexai-labs/PolyStrata.git'
REVISION = 'fabae0d6445e524a1dc68b2c2fa99b53880f98e6'
MODEL_REPO = 'peculiar-ragdoll/Tiel-Coder-35B-A3B-GGUF-MTP'
MODEL_REVISION = 'bb5f3f441849fc24c2d9037c310bc995404bfa0c'
MODEL_FILE = 'Tiel-Coder-35B-A3B-MTP-UD-Q4_K_XL.gguf'
MODEL_SIZE = 22749880160
MODEL_SHA256 = '54f46c4ce544c225122b0f066c2336f10404be7bc53b0cc94d1dbbc5e826bdc1'
POLY_RELEASE = 'https://github.com/simplexai-labs/PolyStrata/releases/download/v0.1.45-poly.7'
LLAMA_RELEASE = 'https://github.com/ggml-org/llama.cpp/releases/download/b12128'
ASSETS = (
    ('engine', POLY_RELEASE + '/strata-poly-windows-x64-5337e9097187ea1c.zip',
     'a1f40828de0d9f4c1ffa0b1f8d8689f2c16aa150ed3a147d92cff953fcaa72cf', 'strata-poly.exe'),
    ('cuda', LLAMA_RELEASE + '/cudart-llama-bin-win-cuda-13.4-x64.zip',
     '738f8c251ac22b70c3ae6f83a10cf222725df0395246a2cf58f32bdb85fbe668', 'cublas64_13.dll'),
    ('llama', LLAMA_RELEASE + '/llama-b12128-bin-win-cuda-13.4-x64.zip',
     'b93b77ba35c63ae1264fb9eba3b5dfc1d088ffd854ce7eff53c9d97864cf55f1', 'ggml-cuda.dll'),
)


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def install_source(state):
    source = state / 'polystrata'
    if not source.exists():
        print('Fetching the pinned PolyStrata server...', flush=True)
        with tempfile.TemporaryDirectory(dir=state) as stage:
            repo = Path(stage) / 'polystrata'
            run('git', 'init', '-q', str(repo))
            run('git', '-C', str(repo), 'config', 'core.longpaths', 'true')
            run('git', '-C', str(repo), 'sparse-checkout', 'set', 'serve', 'tools', 'data')
            run('git', '-C', str(repo), 'fetch', '--depth=1', SOURCE, REVISION)
            run('git', '-C', str(repo), '-c', 'advice.detachedHead=false', 'checkout', '-q', REVISION)
            repo.rename(source)
    head = run('git', '-C', str(source), 'rev-parse', 'HEAD', capture_output=True, text=True)
    if head.stdout.strip() != REVISION or not (source / 'serve/server.py').is_file():
        raise RuntimeError(f'PolyStrata checkout is incomplete or at a different revision: {source}')


def install_asset(state, name, url, digest, expected_file):
    target = state / name
    marker = target / '.archive-sha256'
    if target.exists():
        if marker.is_file() and marker.read_text() == digest and (target / expected_file).is_file():
            return
        raise RuntimeError(f'Incomplete runtime directory. Move it aside and rerun: {target}')
    print(f'Downloading {name} runtime...', flush=True)
    with tempfile.TemporaryDirectory(dir=state) as stage:
        stage = Path(stage)
        archive = stage / 'release.zip'
        with requests.get(url, stream=True, timeout=(15, 90)) as response, archive.open('wb') as file:
            response.raise_for_status()
            for data in response.iter_content(1024 * 1024):
                file.write(data)
        if sha256(archive) != digest:
            raise RuntimeError(f'Archive checksum failed: {name}')
        output = stage / 'files'
        with zipfile.ZipFile(archive) as release:
            release.extractall(output)
        if not (output / expected_file).is_file():
            raise RuntimeError(f'Expected file missing from {name} archive: {expected_file}')
        (output / marker.name).write_text(digest)
        output.rename(target)


def prepare(state, model_path):
    install_source(state)
    install_monitor(state / 'polystrata')
    for asset in ASSETS:
        install_asset(state, *asset)
    if model_path:
        model = model_path.resolve(strict=True)
    else:
        print('Checking the Hugging Face cache for Tiel Coder (22.75 GB on first download)...', flush=True)
        model = Path(hf_hub_download(MODEL_REPO, MODEL_FILE, revision=MODEL_REVISION))
    if model.stat().st_size != MODEL_SIZE:
        raise RuntimeError(f'Model size does not match the pinned Tiel quantization: {model}')
    token_dir = state / 'tokenizer'
    if not token_dir.exists():
        if sha256(model) != MODEL_SHA256:
            raise RuntimeError(f'Model SHA-256 does not match the pinned Tiel quantization: {model}')
        with tempfile.TemporaryDirectory(dir=state) as stage:
            output = Path(stage) / 'tokenizer'
            run(sys.executable, str(state / 'polystrata/tools/strata_tokenizer.py'),
                '--gguf', str(model), '--out', stage, '--check')
            if not (output / 'vocab.json').is_file():
                raise RuntimeError('PolyStrata tokenizer extraction did not produce vocab.json.')
            output.rename(token_dir)
    elif not (token_dir / 'vocab.json').is_file():
        raise RuntimeError(f'Incomplete tokenizer directory. Move it aside and rerun: {token_dir}')
    elif model_path and sha256(model) != MODEL_SHA256:
        raise RuntimeError(f'Model SHA-256 does not match the pinned Tiel quantization: {model}')
    return model


def config_for(state, model, host, context, threads, vram_reserve, conversation_cache, public_host=None):
    flags = ['--model', str(model), '--max-context', str(context), '--threads', str(threads),
             '--vram-reserve-mib', str(vram_reserve), '--kv', 'q8_0', '--tail-skip', '0',
             '--skip-weight', '0', '--cache-bias', '0', '--expert-profile', str(state / 'experts.bin')]
    if conversation_cache:
        flags += ['--conversation-cache-mib', str(conversation_cache)]
    return {
        'exe': str(state / 'engine/strata-poly.exe'), 'args': flags, 'cwd': str(state / 'polystrata'),
        'tokenizer': str(state / 'tokenizer'), 'model_name': 'tiel-coder', 'arch': 'qwen35moe',
        'context': context, 'host': host, 'log': str(state / 'engine.log'),
        'lib_dirs': [str(state / 'cuda'), str(state / 'llama')],
        'env': {'CUDA_MODULE_LOADING': 'EAGER', 'STRATA_ROUTE_TAIL_SKIP': '0'},
        'reasoning_budget_tokens': 4096, 'sampling': {'top_p': 0.95, 'top_k': 20, 'min_p': 0},
        'allowed_hosts': [public_host] if public_host else [],
    }


def existing_serve_route(status, port, target):
    suffix = f':{port}'
    if any(k.endswith(suffix) and enabled for k, enabled in status.get('AllowFunnel', {}).items()):
        raise RuntimeError(f'Tailscale Funnel uses HTTPS port {port}. Choose another Serve port.')
    routes = [entry for key, entry in status.get('Web', {}).items() if key.endswith(suffix)]
    tcp = status.get('TCP', {}).get(str(port))
    if not routes and not tcp:
        return False
    if tcp == {'HTTPS': True} and len(routes) == 1 and routes[0].get('Handlers') == {'/': {'Proxy': target}}:
        return True
    raise RuntimeError(f'Tailscale Serve port {port} is already in use. Choose another Serve port.')


def tailscale_settings(port, target):
    executable = shutil.which('tailscale') or str(Path(os.environ['ProgramFiles']) / 'Tailscale/tailscale.exe')
    if not Path(executable).is_file():
        raise RuntimeError('Install Tailscale and sign in before using Tailscale mode.')
    status = json.loads(run(executable, 'status', '--json', capture_output=True, text=True).stdout)
    hostname = (status.get('Self') or {}).get('DNSName', '').rstrip('.')
    if status.get('BackendState') != 'Running' or not hostname:
        raise RuntimeError('Connect this PC to your tailnet and enable MagicDNS.')
    status = json.loads(run(executable, 'serve', 'status', '--json', capture_output=True, text=True).stdout or '{}')
    return executable, hostname, existing_serve_route(status, port, target)


def wait_for_server(session, process, api, context):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('PolyStrata exited before becoming ready. See .tiel/engine.log.')
        try:
            response = session.get(api + '/models', timeout=2)
            if response.ok:
                models = response.json().get('data', [])
                if any(m['id'] == 'tiel-coder' and m.get('meta', {}).get('n_ctx') == context for m in models):
                    return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError('Timed out waiting for the configured Tiel model. See .tiel/engine.log.')


def stop_server(process):
    if process.poll() is not None:
        return
    try:
        children = psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    # On Windows, the venv executable can be a redirector. Stop the server and
    # its engine even if terminating that redirector alone would leave them running.
    for child in reversed(children):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    process.terminate()
    process.wait(timeout=15)
    _, alive = psutil.wait_procs(children, timeout=10)
    if alive:
        raise RuntimeError('The PolyStrata process tree did not exit within 10 seconds.')


def serve(state, model, args, host):
    target = f'http://{host}:{args.port}'
    ts = tailscale_settings(args.tailscale_port, target) if args.access == 'tailscale' else None
    with socket.socket() as check:
        check.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            check.bind((host, args.port))
        except OSError as error:
            raise RuntimeError(f'Cannot bind {target}. Check the address and whether the port is in use.') from error
    if any((p.info['name'] or '').lower() in {'strata-poly.exe', 'strata.exe', 'llama-server.exe'}
           for p in psutil.process_iter(['name'])):
        raise RuntimeError('Another model engine is running. Stop it before launching Tiel.')

    key_path = state / 'api-key.txt'
    if not key_path.exists():
        key_path.write_text('sk-polystrata-' + secrets.token_hex(24) + '\n', encoding='ascii')
    key = key_path.read_text(encoding='ascii').strip()
    if not key:
        raise RuntimeError(f'API key file is empty: {key_path}')
    cfg = config_for(state, model, host, args.context, args.threads, args.vram_reserve_mib,
                     args.conversation_cache_mib, ts[1] if ts else None)
    config_path = state / 'tiel.json'
    config_path.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    local_api = target + '/v1'
    session = requests.Session()
    session.trust_env = False
    session.headers['Authorization'] = 'Bearer ' + key
    command = [sys.executable, str(state / 'polystrata/serve/server.py'), '--engine', 'strata',
               '--config', str(config_path), '--host', host, '--port', str(args.port)]
    process = subprocess.Popen(command, cwd=cfg['cwd'], env=dict(os.environ, STRATA_API_KEY=key))
    try:
        wait_for_server(session, process, local_api, args.context)
        public = target
        if ts:
            executable, hostname, already_enabled = ts
            if not already_enabled:
                run(executable, 'serve', '--bg', f'--https={args.tailscale_port}', target)
            suffix = '' if args.tailscale_port == 443 else f':{args.tailscale_port}'
            public = f'https://{hostname}{suffix}'
        context_line = '        contextWindow: '
        omp = (ROOT / 'omp.models.yml').read_text(encoding='utf-8').replace('http://127.0.0.1:8092/v1', public + '/v1')
        omp = omp.replace(' - PolyStrata 128K', ' - PolyStrata').replace(
            context_line + '131072', context_line + str(args.context)).replace(
            '        maxTokens: 32768', f'        maxTokens: {min(32768, args.context // 4)}')
        (state / 'omp.models.yml').write_text(omp, encoding='utf-8')
        print(f'\nWeb UI: {public}/\nAPI base: {public}/v1\nModel: tiel-coder ({args.context:,} tokens)\n'
              f'API key file: {key_path}\nOMP provider: {state / "omp.models.yml"}\n'
              'Press Ctrl+C to stop PolyStrata.\n', flush=True)
        code = process.wait()
        if code:
            raise RuntimeError(f'PolyStrata exited with code {code}. See .tiel/engine.log.')
    except KeyboardInterrupt:
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            pass
    finally:
        stop_server(process)
        session.close()


def main():
    import msvcrt

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--access', choices=('local', 'lan', 'tailscale'), default='local')
    parser.add_argument('--lan-address', type=ipaddress.IPv4Address)
    parser.add_argument('--port', type=int, default=8092)
    parser.add_argument('--tailscale-port', type=int, default=443)
    parser.add_argument('--context', type=int, default=131072)
    parser.add_argument('--threads', type=int, default=12)
    parser.add_argument('--vram-reserve-mib', type=int, default=640)
    parser.add_argument('--conversation-cache-mib', type=int, default=0)
    parser.add_argument('--model-path', type=Path)
    parser.add_argument('--setup-only', action='store_true')
    args = parser.parse_args()
    if args.access == 'lan':
        private = ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')
        if not args.lan_address or not any(args.lan_address in ipaddress.ip_network(net) for net in private):
            parser.error('LAN mode requires a private IPv4 address assigned to this PC.')
    host = str(args.lan_address) if args.access == 'lan' else '127.0.0.1'
    state = ROOT / '.tiel'
    state.mkdir(exist_ok=True)
    with (state / 'run.lock').open('a+b') as lock:
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError('Another launcher is already using this clone.') from error
        model = prepare(state, args.model_path)
        if args.setup_only:
            print('Setup complete. Run the same launcher without -SetupOnly to start Tiel.')
        else:
            serve(state, model, args, host)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, requests.RequestException, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
