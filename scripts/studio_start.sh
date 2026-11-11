#!/usr/bin/env bash
# Starts the Commander Studio deck builder on this machine.
# The Studio data folder is outside the repository; default: ~/.local/share/commander-studio.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COMMANDER_LAB_STUDIO_DATA="${COMMANDER_LAB_STUDIO_DATA:-${HOME}/.local/share/commander-studio}"
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="python3"
fi
export PYTHONPATH="${REPO_ROOT}/src"
echo "Studio data: ${COMMANDER_LAB_STUDIO_DATA}"
exec "${PYTHON_BIN}" -m commander_lab.studio serve "$@"
