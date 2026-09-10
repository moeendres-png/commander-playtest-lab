#!/usr/bin/env bash
set -euo pipefail
[[ -n "${ENGINE_START_COMMAND:-}" ]] || { echo "ENGINE_START_COMMAND is required" >&2; exit 64; }
# WS-A1D provenance gate: when the image carries a build-time provenance record
# and the pin authority manifest is mounted, refuse to serve a stale or
# cross-wired engine. Grandfathered/foreign images without a record, or
# containers without a mounted manifest, proceed; the bridge handshake still
# enforces provider identity and protocol version at runtime.
PROVENANCE_PATH="${CONTAINER_PROVENANCE_PATH:-/opt/engine-provenance.json}"
PIN_MANIFEST_PATH="${PIN_MANIFEST_PATH:-/workspace/config/rules_engines.json}"
GATE_SCRIPT="${CONTAINER_GATE_SCRIPT:-/workspace/scripts/verify_container_provenance.py}"
if [[ -f "$PROVENANCE_PATH" && -f "$PIN_MANIFEST_PATH" ]]; then
  if ! command -v python3 >/dev/null; then
    echo "WARNING: python3 is unavailable; image provenance cannot be verified" >&2
  else
    CONTAINER_PROVENANCE_PATH="$PROVENANCE_PATH" PIN_MANIFEST_PATH="$PIN_MANIFEST_PATH" \
      python3 "$GATE_SCRIPT" || exit "$?"
  fi
fi
exec bash -lc "$ENGINE_START_COMMAND"
