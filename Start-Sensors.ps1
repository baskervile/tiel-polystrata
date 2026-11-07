[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$LibraryPath,
    [string]$OutputPath = (Join-Path $env:LOCALAPPDATA 'TielHardwareMonitor\sensors.json'),
    [switch]$Once
)

$ErrorActionPreference = 'Stop'
$assembly = (Resolve-Path -LiteralPath $LibraryPath).Path
if ([IO.Path]::GetFileName($assembly) -ne 'LibreHardwareMonitorLib.dll') {
    throw 'Pass the path to LibreHardwareMonitorLib.dll from the official Windows release.'
}
Add-Type -Path $assembly
$target = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputPath)
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) > $null
$staging = "$target.$PID.tmp"
$utf8 = New-Object Text.UTF8Encoding($false)

function Get-HardwareNode($Hardware) {
    $Hardware.Update()
    $children = @(
        foreach ($sensor in $Hardware.Sensors) {
            $type = $sensor.SensorType.ToString()
            if ($type -in @('Temperature', 'Fan', 'Power', 'Voltage') -and $null -ne $sensor.Value) {
                $value = [double]$sensor.Value
                if (-not ([double]::IsNaN($value) -or [double]::IsInfinity($value))) {
                    @{ Text = $sensor.Name; Type = $type; RawValue = $value }
                }
            }
        }
        foreach ($child in $Hardware.SubHardware) {
            Get-HardwareNode $child
        }
    )
    @{ HardwareId = $Hardware.Identifier.ToString(); Text = $Hardware.Name; Children = $children }
}

$computer = New-Object LibreHardwareMonitor.Hardware.Computer
$computer.IsCpuEnabled = $true
$computer.IsGpuEnabled = $true
$computer.IsMotherboardEnabled = $true
$computer.IsStorageEnabled = $true
$computer.IsControllerEnabled = $true

try {
    $computer.Open()
    Write-Host "Writing read-only sensor snapshots to $target"
    do {
        $snapshot = @{ Children = @(foreach ($device in $computer.Hardware) { Get-HardwareNode $device }) }
        $json = ConvertTo-Json -InputObject $snapshot -Depth 30 -Compress
        [IO.File]::WriteAllText($staging, $json, $utf8)
        if ([IO.File]::Exists($target)) {
            [IO.File]::Replace($staging, $target, [NullString]::Value)
        } else {
            [IO.File]::Move($staging, $target)
        }
        if (-not $Once) { Start-Sleep -Seconds 5 }
    } until ($Once)
} finally {
    $computer.Close()
    if ([IO.File]::Exists($staging)) { [IO.File]::Delete($staging) }
}
