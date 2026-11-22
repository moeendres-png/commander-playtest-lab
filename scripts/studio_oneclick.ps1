# One-click setup and start of the Commander Studio (Windows).
# Thin wrapper: find Python 3.12+, then run the tested Python logic
#   python -m commander_lab.studio.oneclick
# which checks Java, updates the repository (only a clean main), prepares .venv,
# provides the verified engine JAR, runs doctor, imports first data and starts the Studio.
# This file stays ASCII-only (Windows PowerShell 5.1 reads BOM-less files as ANSI);
# the German messages come from the Python module.
# Arguments are passed through, e.g. -- --nur-pruefen, --ja, --ohne-start, --port 8766.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

function Test-Python([string[]]$command) {
    try {
        $exe = $command[0]
        $rest = @()
        if ($command.Length -gt 1) { $rest = $command[1..($command.Length - 1)] }
        $out = & $exe @rest -c 'import sys; print(1 if sys.version_info >= (3, 12) else 0)' 2>$null
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq '1')
    } catch {
        return $false
    }
}

$python = $null
$candidates = @(@('py', '-3'), @('python'), @((Join-Path $repo '.venv\Scripts\python.exe')))
foreach ($candidate in $candidates) {
    if (Get-Command $candidate[0] -ErrorAction SilentlyContinue) {
        if (Test-Python $candidate) { $python = $candidate; break }
    }
}

if (-not $python) {
    Write-Host 'Das fehlt noch: Python 3.12 oder neuer.'
    Write-Host 'Befehl zum Installieren: winget install --id Python.Python.3.12 -e'
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $answer = Read-Host 'Soll ich Python jetzt installieren? (J/N)'
        if ($answer -match '^(j|ja|y|yes)$') {
            & winget install --id Python.Python.3.12 -e
            Write-Host 'Bitte dieses Fenster schliessen und "Studio starten" noch einmal oeffnen.'
        }
    }
    exit 1
}

$env:PYTHONPATH = Join-Path $repo 'src'
$env:PYTHONUTF8 = '1'
if (-not $env:COMMANDER_LAB_STUDIO_DATA -and -not $env:COMMANDER_LAB_OWNER_DATA) {
    $env:COMMANDER_LAB_STUDIO_DATA = Join-Path $env:LOCALAPPDATA 'CommanderStudio'
}

$exe = $python[0]
$rest = @()
if ($python.Length -gt 1) { $rest = $python[1..($python.Length - 1)] }
Push-Location $repo
try {
    & $exe @rest -m commander_lab.studio.oneclick @args
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $code
