$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Provider = if ($env:ENGINE_PROVIDER) { $env:ENGINE_PROVIDER } else { "xmage" }
$RulesCommit = $null
if ($Provider -eq "xmage") {
  # G1: the default pin comes from config/rules_engines.json (sole authority).
  $Python = Get-Command python -ErrorAction SilentlyContinue
  if (-not $Python) { throw "python is required to resolve XMage pin authority" }
  $Resolved = (& $Python.Source (Join-Path $Root "scripts\docker_resolve_engine_pin.py") --provider xmage --format json | Out-String)
  if ($LASTEXITCODE -ne 0) { throw "XMage pin authority resolution failed" }
  $Pin = $Resolved | ConvertFrom-Json
  $Repo = if ($env:COMMANDER_LAB_XMAGE_REPOSITORY) { $env:COMMANDER_LAB_XMAGE_REPOSITORY } else { $Pin.repository }
  $Commit = if ($env:COMMANDER_LAB_XMAGE_COMMIT) { $env:COMMANDER_LAB_XMAGE_COMMIT } else { $Pin.commit }
  $RulesCommit = $Commit
} elseif ($Provider -eq "forge") {
  $Python = Get-Command python -ErrorAction SilentlyContinue
  if (-not $Python) { throw "python is required to resolve Forge pin authority" }
  $Resolved = (& $Python.Source (Join-Path $Root "scripts\docker_resolve_engine_pin.py") --provider forge --format json | Out-String)
  if ($LASTEXITCODE -ne 0) { throw "Forge pin authority resolution failed" }
  $Pin = $Resolved | ConvertFrom-Json
  $Repo = $Pin.bridge_repository
  $Commit = $Pin.bridge_commit
  $RulesCommit = $Pin.commit
} else { throw "ENGINE_PROVIDER must be xmage or forge" }
$Source = if ($env:ENGINE_SOURCE_PATH) { $env:ENGINE_SOURCE_PATH } else { Join-Path $Root "vendor\engine-source\$Provider" }
$Binary = if ($env:ENGINE_BINARY_PATH) { $env:ENGINE_BINARY_PATH } else { Join-Path $Root "vendor\engine-binaries\$Provider" }
Get-Command java -ErrorAction Stop | Out-Null
Get-Command javac -ErrorAction Stop | Out-Null
Get-Command git -ErrorAction Stop | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $Source), $Binary | Out-Null
if (-not (Test-Path (Join-Path $Source ".git"))) {
  git clone $Repo $Source
  if ($LASTEXITCODE -ne 0) { throw "Failed to clone pinned source repository $Repo" }
} else {
  $CurrentRemote = (git -C $Source remote get-url origin).Trim()
  if ($LASTEXITCODE -ne 0) { throw "Unable to read existing source remote" }
  if ($CurrentRemote -ne $Repo) {
    throw "Unexpected source remote: $CurrentRemote (expected $Repo)"
  }
}
git -C $Source fetch --tags --prune
if ($LASTEXITCODE -ne 0) {
  git -C $Source cat-file -e "$Commit^{commit}"
  if ($LASTEXITCODE -ne 0) { throw "Pinned commit $Commit is unavailable after fetch failure" }
}
git -C $Source checkout --detach $Commit
$Observed = (git -C $Source rev-parse HEAD).Trim()
if ($Observed -ne $Commit) { throw "Pinned commit mismatch: $Observed" }
$Dirty = @(git -C $Source status --porcelain)
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect source worktree cleanliness" }
if ($Dirty.Count -ne 0) { throw "Source worktree is dirty; refusing to build unbound engine source" }
if ($Provider -eq "forge") {
  git -C $Source merge-base --is-ancestor $RulesCommit $Commit
  if ($LASTEXITCODE -ne 0) {
    throw "Forge bridge/materialization commit does not descend from current Rules-Core authority $RulesCommit"
  }
  $ForgeDrift = @(git -C $Source diff --name-only $RulesCommit $Commit)
  if ($LASTEXITCODE -ne 0) { throw "Unable to compare Forge Rules-Core and bridge/materialization source" }
  if ($ForgeDrift.Count -eq 0) {
    throw "Forge bridge/materialization commit carries no explicit bridge delta from Rules-Core authority"
  }
  $Unexpected = @($ForgeDrift | Where-Object { -not $_.StartsWith("forge-protocol2-bridge/") })
  if ($Unexpected.Count -ne 0) {
    throw "Forge bridge/materialization source drifts outside the approved bridge surface: $($Unexpected -join ', ')"
  }
}
$Mvnw = Join-Path $Source "mvnw.cmd"
if (Test-Path $Mvnw) { & $Mvnw -DskipTests install }
elseif (Get-Command mvn -ErrorAction SilentlyContinue) { Push-Location $Source; try { mvn -DskipTests install } finally { Pop-Location } }
else { throw "Maven is missing. Install Maven 3.9.16 or use a project-local Maven distribution." }
@{provider=$Provider;commit=$Commit;source_commit=$Commit;rules_core_commit=$RulesCommit;source_path=$Source;bridge_verified=$false} | ConvertTo-Json | Set-Content (Join-Path $Binary "installation-identity.json")
Write-Host "Build completed. Configure ENGINE_START_COMMAND for a conforming JSONL bridge, then run scripts\verify_engine.sh."
