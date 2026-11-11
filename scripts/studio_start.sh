#!/usr/bin/env bash
# Starts the Commander Studio deck builder on this machine.
# The Studio data folder is outside the repository; default: ~/.local/share/commander-studio.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COMMANDER_LAB_STUDIO_DATA="${COMMANDER_LAB_STUDIO_DATA:-${HOME}/.local/share/commander-studio}"
BRIDGE_JAR="${REPO_ROOT}/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar"
STUDIO_JAR="${COMMANDER_LAB_STUDIO_DATA}/engine/xmage-engine-bridge.jar"
# Re-stage whenever the built bridge differs from the staged copy: a stale copy carries an
# older engine commit and the full-game runner then refuses every game (commit mismatch).
if [[ -f "${BRIDGE_JAR}" ]] && ! cmp -s "${BRIDGE_JAR}" "${STUDIO_JAR}" 2>/dev/null; then
    mkdir -p "$(dirname "${STUDIO_JAR}")"
    cp -f "${BRIDGE_JAR}" "${STUDIO_JAR}"
fi
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="python3"
fi
export PYTHONPATH="${REPO_ROOT}/src"
echo "Studio data: ${COMMANDER_LAB_STUDIO_DATA}"
exec "${PYTHON_BIN}" -m commander_lab.studio serve "$@"
