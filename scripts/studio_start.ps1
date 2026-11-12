# Starts the Commander Studio deck builder on this machine and opens the browser.
# The Studio data folder is outside the repository; default: %LOCALAPPDATA%\CommanderStudio.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not $env:COMMANDER_LAB_STUDIO_DATA) {
    $env:COMMANDER_LAB_STUDIO_DATA = Join-Path $env:LOCALAPPDATA 'CommanderStudio'
}
$bridgeJar = Join-Path $repo 'engine-bridge\target\xmage-engine-bridge-0.1.0-SNAPSHOT.jar'
$studioJar = Join-Path $env:COMMANDER_LAB_STUDIO_DATA 'engine\xmage-engine-bridge.jar'
# Re-stage whenever the built bridge differs from the staged copy: a stale copy carries an
# older engine commit and the full-game runner then refuses every game (commit mismatch).
if ((Test-Path $bridgeJar) -and (-not (Test-Path $studioJar) -or
        (Get-FileHash $bridgeJar).Hash -ne (Get-FileHash $studioJar).Hash)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $studioJar) | Out-Null
    Copy-Item -Path $bridgeJar -Destination $studioJar -Force
}
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }
$env:PYTHONPATH = Join-Path $repo 'src'
Write-Host "Studio data: $env:COMMANDER_LAB_STUDIO_DATA"

# Check prerequisites (Issue #1172)
$javaCmd = Get-Command java -ErrorAction SilentlyContinue
if (-not $javaCmd -and -not $env:JAVA_HOME) {
    Write-Warning "Java wurde nicht gefunden. Fuer 'Neue Partie' und 'Simulieren' wird Java 17 oder neuer benoetigt (z.B. Eclipse Temurin 17)."
} else {
    try {
        $verOutput = (& java -version 2>&1 | Select-Object -First 1)
        if ($verOutput -match 'version "([0-9]+)') {
            $verNum = [int]$matches[1]
            if ($verNum -lt 17) {
                Write-Warning "Gefundenes Java hat Version $verNum. Fuer 'Neue Partie' und 'Simulieren' wird Java 17 oder neuer benoetigt."
            }
        }
    } catch {}
}
if (-not (Test-Path $studioJar) -and -not (Test-Path $bridgeJar)) {
    Write-Warning "Die Engine-Datei fehlt noch: $studioJar`nFuer Simulationen: Lege xmage-engine-bridge.jar dort ab oder baue sie im Ordner engine-bridge."
}

& $python -m commander_lab.studio serve --open @args
