#!/bin/bash
# Cloud sessions start in a fresh container with no project environment.
# Build the same environment CI's quality job uses (hash-pinned lock, then the
# project editable without dependencies) in a venv outside the repository, and
# put it first on PATH. Idempotent: an existing venv for the same lock is reused.
set -euo pipefail

repo="${CLAUDE_PROJECT_DIR:?}"

# A fresh session starts from the generated handoff index instead of a compacted
# conversation. It may be stale; regenerating is one command.
if [ -f "${repo}/docs/claude/state/HANDOFF.md" ]; then
  echo "Handoff index: ${repo}/docs/claude/state/HANDOFF.md (regenerate: python3 scripts/claude_handoff.py). Read it before the lane issues."
fi

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi
venv="${HOME}/.cache/commander-lab-venv"
stamp="${venv}/.lock-sha256"
lock_sha="$(sha256sum "${repo}/requirements/lock.txt" | cut -d' ' -f1)"

if [ ! -x "${venv}/bin/python" ] || [ "$(cat "${stamp}" 2>/dev/null)" != "${lock_sha}" ]; then
  rm -rf "${venv}"
  python3.12 -m venv "${venv}"
  "${venv}/bin/python" -m pip install -q --upgrade pip
  "${venv}/bin/python" -m pip install -q --require-hashes -r "${repo}/requirements/lock.txt"
  echo "${lock_sha}" > "${stamp}"
fi
# Editable install of the checkout itself (cheap; repeated so it tracks this repo).
"${venv}/bin/python" -m pip install -q --no-deps --no-build-isolation -e "${repo}"
# The editable build leaves src/*.egg-info, which PB-03 trigger-completeness
# tests then count as an unlisted input. It is not needed at runtime.
rm -rf "${repo}"/src/*.egg-info

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"${venv}\""
    echo "export PATH=\"${venv}/bin:\${PATH}\""
  } >> "${CLAUDE_ENV_FILE}"
fi
echo "commander-lab venv ready: ${venv} (in a git worktree, run tests with PYTHONPATH=\$PWD/src)"
