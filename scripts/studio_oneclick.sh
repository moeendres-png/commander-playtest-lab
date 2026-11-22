#!/usr/bin/env bash
# One-click setup and start of the Commander Studio (Linux/WSL).
# Thin wrapper: find Python 3.12+, then run the tested Python logic
#   python -m commander_lab.studio.oneclick
# Arguments are passed through, e.g. --nur-pruefen, --ja, --ohne-start, --port 8766.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3 "${REPO_ROOT}/.venv/bin/python"; do
    if command -v "${candidate}" >/dev/null 2>&1 \
        && "${candidate}" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
        PYTHON_BIN="${candidate}"
        break
    fi
done
if [[ -z "${PYTHON_BIN}" ]]; then
    echo "Das fehlt noch: Python 3.12 oder neuer (z. B. Paket python3.12)."
    exit 1
fi
export PYTHONPATH="${REPO_ROOT}/src"
export PYTHONUTF8=1
if [[ -z "${COMMANDER_LAB_STUDIO_DATA:-}" && -z "${COMMANDER_LAB_OWNER_DATA:-}" ]]; then
    export COMMANDER_LAB_STUDIO_DATA="${HOME}/.local/share/commander-studio"
fi
cd "${REPO_ROOT}"
exec "${PYTHON_BIN}" -m commander_lab.studio.oneclick "$@"
