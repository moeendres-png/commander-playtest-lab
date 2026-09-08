#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$ROOT" ]]; then
  echo "ERROR: run this launcher from a Commander Playtest Lab Git worktree." >&2
  exit 2
fi

case "$ROOT" in
  /mnt/*)
    echo "ERROR: refusing to start training-eligible Muse from a Windows-mounted worktree: $ROOT" >&2
    echo "Use a project-local WSL/Linux worktree (for example ~/code/...) or an isolated container." >&2
    exit 3
    ;;
esac

if [[ ! -f "$ROOT/AGENTS.md" || ! -f "$ROOT/opencode.jsonc" ]]; then
  echo "ERROR: project OpenCode policy/config is missing from $ROOT." >&2
  exit 4
fi

if ! command -v opencode2 >/dev/null 2>&1; then
  echo "ERROR: OpenCode V2 (opencode2) is required by this project policy." >&2
  echo "Install using the current official OpenCode V2 instructions, then rerun." >&2
  exit 5
fi

cd "$ROOT"

echo "Commander Simulation Foundry"
echo "worktree: $ROOT"
echo "agent:    foundry-implementer"
echo "model:    Muse Spark 1.3 Contributor Free"
echo "effort:   high (xhigh only when the live model catalog exposes it)"
echo "privacy:  external directories denied; session sharing disabled"
echo

exec opencode2 --standalone "$ROOT"
