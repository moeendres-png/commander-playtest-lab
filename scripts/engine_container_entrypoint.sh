#!/usr/bin/env bash
set -euo pipefail
[[ -n "${ENGINE_START_COMMAND:-}" ]] || { echo "ENGINE_START_COMMAND is required" >&2; exit 64; }
# WS-A1D provenance gate (fail closed): the supported container path must prove
# image identity against the sole pin authority before the engine may start.
# The gate runs UNCONDITIONALLY: a missing gate implementation, missing Python,
# missing provenance record, missing manifest, or any contradiction stops
# startup non-zero. There is no grandfathered/foreign-image exception here;
# legacy containers need a separately authorized compatibility path.
PROVENANCE_PATH="${CONTAINER_PROVENANCE_PATH:-/opt/engine-provenance.json}"
PIN_MANIFEST_PATH="${PIN_MANIFEST_PATH:-/workspace/config/rules_engines.json}"
GATE_SCRIPT="${CONTAINER_GATE_SCRIPT:-/workspace/scripts/verify_container_provenance.py}"
PYTHON3_BIN="${PYTHON3_BIN:-python3}"
[[ -f "$GATE_SCRIPT" ]] || { echo "ERROR: provenance gate implementation is missing: $GATE_SCRIPT" >&2; exit 3; }
command -v "$PYTHON3_BIN" >/dev/null || { echo "ERROR: python3 is unavailable; image provenance cannot be verified" >&2; exit 3; }
CONTAINER_PROVENANCE_PATH="$PROVENANCE_PATH" PIN_MANIFEST_PATH="$PIN_MANIFEST_PATH" \
  "$PYTHON3_BIN" "$GATE_SCRIPT" --provider "${ENGINE_PROVIDER:-}" || exit "$?"
exec bash -lc "$ENGINE_START_COMMAND"
