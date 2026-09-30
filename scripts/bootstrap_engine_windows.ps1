$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Provider = if ($env:ENGINE_PROVIDER) { $env:ENGINE_PROVIDER } else { "xmage" }
if ($Provider -ne "xmage" -and $Provider -ne "forge") { throw "ENGINE_PROVIDER must be xmage or forge" }

# Sole current pin authority. Resolve exactly the same manifest fields as the
# supported Docker path; no provider repository/commit literals live here.
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { throw "python is required to resolve config/rules_engines.json" }
$Resolved = (& $Python.Source (Join-Path $Root "scripts\docker_resolve_engine_pin.py") --provider $Provider --format json | Out-String)
if ($LASTEXITCODE -ne 0) { throw "engine pin authority resolution failed for $Provider" }
$Pin = $Resolved | ConvertFrom-Json
$Repo = $Pin.repository
$Commit = $Pin.commit
$Source = if ($env:ENGINE_SOURCE_PATH) { $env:ENGINE_SOURCE_PATH } else { Join-Path $Root "vendor\engine-source\$Provider" }
$Binary = if ($env:ENGINE_BINARY_PATH) { $env:ENGINE_BINARY_PATH } else { Join-Path $Root "vendor\engine-binaries\$Provider" }
Get-Command java -ErrorAction Stop | Out-Null
Get-Command javac -ErrorAction Stop | Out-Null
Get-Command git -ErrorAction Stop | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $Source), $Binary | Out-Null
if (-not (Test-Path (Join-Path $Source ".git"))) { git clone $Repo $Source }
git -C $Source fetch --tags --prune
git -C $Source checkout --detach $Commit
$Observed = (git -C $Source rev-parse HEAD).Trim()
if ($Observed -ne $Commit) { throw "Pinned commit mismatch: $Observed" }
$Mvnw = Join-Path $Source "mvnw.cmd"
if (Test-Path $Mvnw) { & $Mvnw -DskipTests install }
elseif (Get-Command mvn -ErrorAction SilentlyContinue) { Push-Location $Source; try { mvn -DskipTests install } finally { Pop-Location } }
else { throw "Maven is missing. Install Maven 3.9.16 or use a project-local Maven distribution." }
@{provider=$Provider;commit=$Commit;source_path=$Source;bridge_verified=$false} | ConvertTo-Json | Set-Content (Join-Path $Binary "installation-identity.json")
Write-Host "Build completed. Configure ENGINE_START_COMMAND for a conforming JSONL bridge, then run scripts\verify_engine.sh."
