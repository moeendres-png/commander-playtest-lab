# External rules-engine setup

## Status of this repository

Current provider truth is `NO_PROVIDER_READY`. Later J-P3 real executions retained PARTIAL evidence for both XMage and Forge, but no production bridge/provider passed the required legal-action/action-submission/replay gate. Phase 8.5 prepared an earlier runtime path and remains historical provenance only.

## Pinned providers

| Candidate role | Provider | Current evidence pin (authority) | License | Current status |
|---|---|---|---|---|
| Provider candidate | XMage | `primary_engine` in `config/rules_engines.json` (compatibility-fork pin) | MIT | `PARTIAL` |
| Provider candidate | Forge | `secondary_engine` in `config/rules_engines.json` | GPL-3.0 | `PARTIAL` |

Do not copy commits out of the manifest into this table: the manifest is the sole
pin authority (see its `authority_note`). Superseded pins — the J-P3
`xmage_1.4.60V3` line and the Phase-8.5 `forge-2.0.13` line — remain provenance
only in `docs/J_P3_PROVIDER_DECISION.json`, the Phase-8.5 artifacts, and
`historical_phase85` in the manifest.

Neither provider is production-selected. `docs/J_P3_PROVIDER_DECISION.json` is the
historical decision record; `config/rules_engines.json` is the current
machine-readable truth (`provider_decision: NO_PROVIDER_READY`,
`current_runtime.provider_selected: false`).

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

The supported container path resolves engine identity from
`config/rules_engines.json` (the sole pin authority) at build time. Never copy
a commit SHA into a Docker command: run the wrapper, which derives the
canonical provider repository, commit and bridge protocol version and exports
them for `docker-compose.engine.yml` build-arg interpolation:

```bash
export ENGINE_START_COMMAND='java -jar /workspace/vendor/engine-binaries/xmage/bridge.jar'
./scripts/docker_build_engine.sh xmage build
./scripts/docker_build_engine.sh xmage up
# Forge: ./scripts/docker_build_engine.sh forge build
```

A plain `docker compose -f docker-compose.engine.yml --profile xmage build`
without the wrapper fails closed (the required build variables are unset)
instead of materializing a stale engine. The Dockerfiles declare their build
args without defaults and re-validate repository shape, full 40-hex commit and
provider match at materialization time, then record what was built in
`/opt/engine-provenance.json`. At container start the entrypoint compares that
record against the mounted manifest and refuses to serve a stale or
cross-wired image.

Inspect what an image actually materialized (provenance is also printed during
`docker build`):

```bash
docker run --rm <image> cat /opt/engine-provenance.json
```

A failed external start never silently falls back; the bridge handshake still
enforces provider identity and bridge protocol version at runtime (see Start,
status and stop).

Historical note: Docker was not available in the Phase-8.5 build container, so
the Phase-8.5 Dockerfiles were prepared but not executed there. WS-A1D
re-pinned the container path to manifest authority; whether an image was
actually materialized during WS-A1D is recorded in the workstream handoff, not
here. No container build output is Rules behavior evidence.

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
