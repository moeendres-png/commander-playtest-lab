$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Provider = if ($env:ENGINE_PROVIDER) { $env:ENGINE_PROVIDER } else { "xmage" }
if ($Provider -eq "xmage") {
  $Repo = if ($env:COMMANDER_LAB_XMAGE_REPOSITORY) { $env:COMMANDER_LAB_XMAGE_REPOSITORY } else { "https://github.com/moeendres-png/mage.git" }
  $Commit = if ($env:COMMANDER_LAB_XMAGE_COMMIT) { $env:COMMANDER_LAB_XMAGE_COMMIT } else { "77d7646da6958fdf8125ee7c8f4aabd130d21d4c" }
} elseif ($Provider -eq "forge") {
  $Repo = "https://github.com/Card-Forge/forge.git"
  $Commit = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
} else { throw "ENGINE_PROVIDER must be xmage or forge" }
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
