#!/usr/bin/env bash
# WS-A1D canonical Docker engine build path.
#
# Resolves the provider repository + commit + protocol version from the sole
# pin authority (config/rules_engines.json) via
# scripts/docker_resolve_engine_pin.py, exports them for
# docker-compose.engine.yml build-arg interpolation, then execs
# `docker compose` for the requested provider profile.
#
# Canonical identity is resolved for BOTH known providers before invoking
# `docker compose`, because docker-compose.engine.yml requires build-arg
# interpolation for both services and required-value syntax fails on unset
# variables. `--profile <provider>` still selects the requested service
# operation. Either resolution failure stops the build path (fail closed)
# before Docker is invoked.
#
# Usage:
#   ./scripts/docker_build_engine.sh <xmage|forge> [compose args...]
#
# With no compose args, runs `build`. Examples:
#   ./scripts/docker_build_engine.sh xmage
#   ./scripts/docker_build_engine.sh xmage build --no-cache
#   ./scripts/docker_build_engine.sh forge up --build
#
# PIN_MANIFEST_PATH may override the manifest location (tests, unusual
# layouts). Any authority resolution failure stops the build path (fail
# closed): a stale Dockerfile default can never silently win because the
# Dockerfiles declare their build args without defaults.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROVIDER="${1:-}"
if [[ "$PROVIDER" != "xmage" && "$PROVIDER" != "forge" ]]; then
  echo "usage: $0 <xmage|forge> [compose args...]" >&2
  exit 2
fi
shift
if [[ "$#" -eq 0 ]]; then
  set -- build
fi
command -v docker >/dev/null || { echo "ERROR: docker is not installed" >&2; exit 3; }

MANIFEST_ARGS=()
if [[ -n "${PIN_MANIFEST_PATH:-}" ]]; then
  MANIFEST_ARGS=(--manifest "$PIN_MANIFEST_PATH")
fi
RESOLVED_XMAGE="$(python3 "$ROOT/scripts/docker_resolve_engine_pin.py" --provider xmage "${MANIFEST_ARGS[@]}")" || exit "$?"
RESOLVED_FORGE="$(python3 "$ROOT/scripts/docker_resolve_engine_pin.py" --provider forge "${MANIFEST_ARGS[@]}")" || exit "$?"
while IFS='=' read -r key value; do
  [[ -z "$key" && -z "$value" ]] && continue
  [[ -n "$key" && -n "$value" ]] || { echo "ERROR: malformed authority resolution" >&2; exit 3; }
  export "$key=$value"
done <<< "$RESOLVED_XMAGE"$'\n'"$RESOLVED_FORGE"

exec docker compose -f "$ROOT/docker-compose.engine.yml" --profile "$PROVIDER" "$@"
