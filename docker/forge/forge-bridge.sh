#!/usr/bin/env bash
# Forge Protocol-2 bridge launcher (image-side, H4F bounded surface).
#
# Derives the Rules-Core engine identity from the image provenance record
# (/opt/engine-provenance.json "commit") and launches the real
# forge.bridge.BridgeMain over a deterministic build-time classpath.
# No GUI defaults, no AI pilot, no health stub: stdout is the Protocol-2.0.0
# JSONL stream, diagnostics go to stderr.
set -euo pipefail
PROVENANCE_PATH="${ENGINE_PROVENANCE_PATH:-/opt/engine-provenance.json}"
test -f "$PROVENANCE_PATH" || { echo "forge-bridge: provenance record missing: $PROVENANCE_PATH" >&2; exit 3; }
RULES_COMMIT="$(python3 -c 'import json,os,sys; print(json.load(open(os.environ.get("ENGINE_PROVENANCE_PATH", "/opt/engine-provenance.json")))["commit"])')"
case "$RULES_COMMIT" in
  *[!0-9a-f]* | "") echo "forge-bridge: provenance commit is not 40-hex" >&2; exit 3;;
esac
if [ "${#RULES_COMMIT}" -ne 40 ]; then echo "forge-bridge: provenance commit is not 40-hex" >&2; exit 3; fi
export FORGE_ENGINE_SHA="$RULES_COMMIT"
export FORGE_ASSETS_DIR="${FORGE_ASSETS_DIR:-/opt/engine-source/forge-gui}"
CP_FILE="${FORGE_BRIDGE_CP:-/opt/forge-bridge/cp.txt}"
MODULE_CLASSES="/opt/engine-source/forge-protocol2-bridge/target/classes"
test -f "$CP_FILE" || { echo "forge-bridge: bridge classpath manifest missing: $CP_FILE" >&2; exit 3; }
test -d "$MODULE_CLASSES" || { echo "forge-bridge: bridge module classes missing: $MODULE_CLASSES" >&2; exit 3; }
exec java -Djava.awt.headless=true -cp "${MODULE_CLASSES}:$(cat "$CP_FILE")" forge.bridge.BridgeMain
