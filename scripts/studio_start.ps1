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
# Preflight for games (the deck builder also works without the engine): say clearly what
# is missing instead of letting the first game start fail inside the engine process.
$javaExe = $null
if (Get-Command java -ErrorAction SilentlyContinue) { $javaExe = 'java' }
elseif ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME 'bin\java.exe'))) { $javaExe = Join-Path $env:JAVA_HOME 'bin\java.exe' }
if (-not $javaExe) {
    Write-Host 'WARNUNG: Java nicht gefunden. Fuer Partien wird Java 17 oder neuer benoetigt (Deckbau geht ohne Engine).'
} else {
    try {
        $versionLine = (& $javaExe -version 2>&1 | Select-Object -First 1) -join ' '
        if ($versionLine -match 'version "(\d+)(?:\.(\d+))?') {
            $major = [int]$Matches[1]
            if ($major -eq 1 -and $Matches[2]) { $major = [int]$Matches[2] }
            if ($major -lt 17) {
                Write-Host "WARNUNG: Java $major gefunden. Fuer Partien wird Java 17 oder neuer benoetigt (Deckbau geht ohne Engine)."
            }
        }
    } catch { }
}
if (-not (Test-Path $studioJar)) {
    Write-Host "WARNUNG: Engine-Datei fehlt: $studioJar (Deckbau geht ohne, Partien erst nach Bereitstellung der Engine-Datei)."
}
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }
$env:PYTHONPATH = Join-Path $repo 'src'
Write-Host "Studio data: $env:COMMANDER_LAB_STUDIO_DATA"
& $python -m commander_lab.studio serve --open @args
