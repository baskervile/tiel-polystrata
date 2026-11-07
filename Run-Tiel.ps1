[CmdletBinding()]
param(
    [ValidateSet('Local', 'LAN', 'Tailscale')][string]$Access = 'Local',
    [string]$LanAddress,
    [ValidateRange(1, 65535)][int]$Port = 8092,
    [ValidateRange(1, 65535)][int]$TailscalePort = 443,
    [ValidateRange(8192, 131072)][int]$Context = 131072,
    [ValidateRange(1, 256)][int]$Threads = 12,
    [ValidateRange(200, 32768)][int]$VramReserveMiB = 640,
    [ValidateRange(0, 65536)][int]$ConversationCacheMiB = 0,
    [string]$ModelPath,
    [switch]$SetupOnly
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'This launcher requires Windows x64.'
}
if ($Access -eq 'LAN' -and -not $LanAddress) {
    throw 'Pass -LanAddress with the private IPv4 address of this PC when using -Access LAN.'
}
if ($LanAddress -and $Access -ne 'LAN') {
    throw '-LanAddress is only used with -Access LAN.'
}

$stateDir = Join-Path $PSScriptRoot '.tiel'
$venv = Join-Path $stateDir 'venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'
$requirements = Join-Path $PSScriptRoot 'requirements.txt'
$stamp = Join-Path $venv '.requirements-sha256'

function Install-PackageWithWinget([string]$Id) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "Install $Id manually or install App Installer to make winget available."
    }
    & winget.exe install --exact --id $Id --source winget --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget could not install $Id (exit $LASTEXITCODE)."
    }
}

function New-TielVenv {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3.11 -c 'import sys; raise SystemExit(sys.maxsize<2**32)'
        if ($LASTEXITCODE -eq 0) {
            & $launcher.Source -3.11 -m venv $venv
            if ($LASTEXITCODE -ne 0) { throw 'Python could not create the virtual environment.' }
            return
        }
    }
    $installed = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
    if (-not (Test-Path -LiteralPath $installed)) {
        Install-PackageWithWinget 'Python.Python.3.11'
    }
    if (-not (Test-Path -LiteralPath $installed)) {
        throw 'Open a new PowerShell window so py.exe can find the newly installed Python 3.11.'
    }
    & $installed -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Python could not create the virtual environment.' }
}

if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { throw 'Install Git for Windows first.' }
if (-not (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue)) { throw 'Install a current NVIDIA driver first.' }
if (-not (Test-Path -LiteralPath (Join-Path $env:SystemRoot 'System32\vcruntime140_1.dll'))) {
    Install-PackageWithWinget 'Microsoft.VCRedist.2015+.x64'
}
if (-not (Test-Path -LiteralPath $venvPython)) { New-TielVenv }
$hasher = [System.Security.Cryptography.SHA256]::Create()
try {
    $digest = [BitConverter]::ToString($hasher.ComputeHash([IO.File]::ReadAllBytes($requirements))).Replace('-', '')
}
finally { $hasher.Dispose() }
if (-not (Test-Path -LiteralPath $stamp) -or (Get-Content -LiteralPath $stamp -Raw).Trim() -ne $digest) {
    & $venvPython -m pip install --disable-pip-version-check --progress-bar off -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Could not install the pinned Python packages.' }
    Set-Content -LiteralPath $stamp -Value $digest -Encoding ASCII
}

$options = @('--access', $Access.ToLowerInvariant(), '--port', $Port, '--tailscale-port', $TailscalePort,
    '--context', $Context, '--threads', $Threads, '--vram-reserve-mib', $VramReserveMiB,
    '--conversation-cache-mib', $ConversationCacheMiB)
if ($LanAddress) { $options += @('--lan-address', $LanAddress) }
if ($ModelPath) { $options += @('--model-path', (Resolve-Path -LiteralPath $ModelPath).Path) }
if ($SetupOnly) { $options += '--setup-only' }
& $venvPython (Join-Path $PSScriptRoot 'launcher.py') @options
exit $LASTEXITCODE
