# External rules-engine setup

## Status of this repository

Current provider truth is `NO_PROVIDER_READY`. Later J-P3 real executions retained PARTIAL evidence for both XMage and Forge, but no production bridge/provider passed the required legal-action/action-submission/replay gate. Phase 8.5 prepared an earlier runtime path and remains historical provenance only.

## Pinned providers

| Candidate role | Provider | Frozen current evidence pin | License | Current status |
|---|---|---|---|---|
| Provider candidate | XMage | `xmage_1.4.60V3 @ 06d166b098ad36b277edef01116472203d5a047e` | MIT | `PARTIAL` |
| Provider candidate | Forge | `forge-2.0.14 @ a37a865a53280dd8ad6fad3384d69611e8c5a42f` | GPL-3.0 | `PARTIAL` |

Neither provider is production-selected. `docs/J_P3_PROVIDER_DECISION.json` is the current decision record; `config/rules_engines.json` mirrors those pins while preserving the older Phase-8.5 Forge pin only as historical provenance.

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
