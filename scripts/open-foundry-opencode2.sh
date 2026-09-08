#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$ROOT" ]]; then
  echo "ERROR: run this launcher from a Commander Playtest Lab Git worktree." >&2
  exit 2
fi

if [[ ! -f "$ROOT/AGENTS.md" || ! -f "$ROOT/opencode.jsonc" ]]; then
  echo "ERROR: project OpenCode policy/config is missing from $ROOT." >&2
  exit 4
fi

if ! command -v opencode2 >/dev/null 2>&1; then
  echo "ERROR: OpenCode V2 (opencode2) is required by this project policy." >&2
  echo "Install using the current official OpenCode V2 instructions, then rerun." >&2
  exit 5
fi

case "$ROOT" in
  /mnt/*)
    echo "WARNING: project worktree is on a Windows-mounted path: $ROOT" >&2
    echo "Project files may be used normally, but Muse must not inspect unrelated personal host directories." >&2
    echo "For the strongest privacy boundary, prefer a project-only WSL/container worktree." >&2
    echo >&2
    ;;
esac

cd "$ROOT"

echo "Commander Simulation Foundry"
echo "worktree: $ROOT"
echo "agent:    foundry-implementer"
echo "model:    Muse Spark 1.3 Contributor Free"
echo "effort:   high (xhigh only when the live model catalog exposes it)"
echo "privacy:  project data/tools allowed; unrelated personal data and raw-secret disclosure forbidden"
echo "sharing:  disabled"
echo

exec opencode2 --standalone "$ROOT"
