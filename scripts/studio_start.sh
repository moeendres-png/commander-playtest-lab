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

# Check prerequisites (Issue #1172)
JAVA_BIN="${JAVA_HOME:-}/bin/java"
if [[ ! -x "${JAVA_BIN}" ]]; then
    JAVA_BIN="$(command -v java 2>/dev/null || true)"
fi
if [[ -z "${JAVA_BIN}" ]]; then
    echo "[HINWEIS] Java wurde nicht gefunden. Für 'Neue Partie' und 'Simulieren' wird Java 17 oder neuer benötigt."
    echo "          Installiere Java 17+ (z.B. Eclipse Temurin 17) oder setze JAVA_HOME."
else
    JAVA_VER="$("${JAVA_BIN}" -version 2>&1 | head -n 1 | sed -E 's/.*version "([0-9]+).*/\1/')"
    if [[ "${JAVA_VER}" =~ ^[0-9]+$ ]] && [[ "${JAVA_VER}" -lt 17 ]]; then
        echo "[HINWEIS] Gefundenes Java hat Version ${JAVA_VER}. Für 'Neue Partie' und 'Simulieren' wird Java 17 oder neuer benötigt."
    fi
fi

if [[ ! -f "${STUDIO_JAR}" ]] && [[ ! -f "${BRIDGE_JAR}" ]]; then
    echo "[HINWEIS] Die Engine-Datei fehlt noch: ${STUDIO_JAR}"
    echo "          Für Simulationen: Baue die Bridge (mvn -B verify im Ordner engine-bridge)"
    echo "          oder lege die bereitgestellte xmage-engine-bridge.jar unter ${STUDIO_JAR} ab."
fi

exec "${PYTHON_BIN}" -m commander_lab.studio serve "$@"
