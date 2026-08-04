# External rules-engine setup

## Status of this repository

Phase 8.5 prepares a versioned external runtime path. The current build container
could not download or build XMage/Forge because Maven, Gradle and Docker were
absent and DNS resolution failed for GitHub and Maven Central. No external result
is stored as validated.

## Pinned providers

| Role | Provider | Release | Commit | License |
|---|---|---|---|---|
| Primary tactical oracle | XMage | `xmage_1.4.60V3` | `06d166b098ad36b277edef01116472203d5a047e` | MIT |
| Differential fallback | Forge | `forge-2.0.13` | `852066bf4f761b302ed17cb011999d8a8fe08ad6` | GPL-3.0 |

XMage is primary because its project-specific test tooling is a better fit for
small stack, trigger and combat fixtures. Forge remains a separate-process
fallback and differential oracle.

## Prerequisites

- Git
- a JDK; JDK 21 is the common supported development baseline
- Maven 3.9.16 or the repository Maven wrapper
- Python 3.12+
- network access to GitHub and Maven Central for a source build
- optional Docker/Compose for the container path
- enough disk space for engine source, Maven dependencies and build products

## Local source build

Linux:

```bash
cp .env.example .env
export ENGINE_PROVIDER=xmage
./scripts/bootstrap_engine_linux.sh
```

macOS:

```bash
export ENGINE_PROVIDER=xmage
./scripts/bootstrap_engine_macos.sh
```

Windows PowerShell:

```powershell
$env:ENGINE_PROVIDER="xmage"
.\scripts\bootstrap_engine_windows.ps1
```

The bootstrap is idempotent, verifies the pinned Git commit and uses a project
Maven wrapper when present. If Maven is absent, the Unix bootstrap downloads
Maven 3.9.16 locally and verifies the official SHA-512 sidecar before extraction.

## External bridge requirement

Building the upstream engine does not by itself create the Commander Lab JSONL
bridge. Configure a provider-specific bridge command that binds the upstream
engine to `schemas/engine_adapter_protocol.schema.json`:

```bash
export ENGINE_START_COMMAND='java -jar /path/to/commander-lab-xmage-bridge.jar'
export ENGINE_PROVIDER=xmage
export ENGINE_MODE=external
./scripts/verify_engine.sh
```

The bridge is healthy only after an external capability handshake. Merely
starting XMage, Forge, a mock, or the Tactical Oracle is insufficient.

## Docker

```bash
ENGINE_START_COMMAND='java -jar /workspace/vendor/engine-binaries/xmage/bridge.jar' \
  docker compose -f docker-compose.engine.yml --profile xmage up --build
```

Docker was not available in the Phase-8.5 build container, so these Dockerfiles
are prepared but not executed there.

## Offline mode

Already downloaded inputs may be supplied through:

```bash
export ENGINE_SOURCE_PATH=/absolute/path/to/pinned/source
export ENGINE_BINARY_PATH=/absolute/path/to/verified/binaries
```

or placed below `vendor/engine-source/<provider>` and
`vendor/engine-binaries/<provider>`. Presence does not imply verification; run
`./scripts/verify_engine.sh`.

## Start, status and stop

```bash
./scripts/start_engine.sh        # foreground supervisor
commander-lab engine-status
./scripts/stop_engine.sh
./scripts/collect_engine_logs.sh
```

A failed external start never silently falls back. Tactical fallback requires an
explicit separate configuration and cannot produce external validation.
