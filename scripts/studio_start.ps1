# Starts the Commander Studio deck builder on this machine and opens the browser.
# The Studio data folder is outside the repository; default: %LOCALAPPDATA%\CommanderStudio.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not $env:COMMANDER_LAB_STUDIO_DATA) {
    $env:COMMANDER_LAB_STUDIO_DATA = Join-Path $env:LOCALAPPDATA 'CommanderStudio'
}
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }
$env:PYTHONPATH = Join-Path $repo 'src'
Write-Host "Studio data: $env:COMMANDER_LAB_STUDIO_DATA"
& $python -m commander_lab.studio serve --open @args
