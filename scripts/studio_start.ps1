# Starts the Commander Studio deck builder on this machine and opens the browser.
# The Studio data folder is outside the repository; default: %LOCALAPPDATA%\CommanderStudio.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not $env:COMMANDER_LAB_STUDIO_DATA) {
    $env:COMMANDER_LAB_STUDIO_DATA = Join-Path $env:LOCALAPPDATA 'CommanderStudio'
}
$bridgeJar = Join-Path $repo 'engine-bridge\target\xmage-engine-bridge-0.1.0-SNAPSHOT.jar'
$studioJar = Join-Path $env:COMMANDER_LAB_STUDIO_DATA 'engine\xmage-engine-bridge.jar'
if ((Test-Path $bridgeJar) -and -not (Test-Path $studioJar)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $studioJar) | Out-Null
    Copy-Item -Path $bridgeJar -Destination $studioJar -Force
}
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }
$env:PYTHONPATH = Join-Path $repo 'src'
Write-Host "Studio data: $env:COMMANDER_LAB_STUDIO_DATA"
& $python -m commander_lab.studio serve --open @args
