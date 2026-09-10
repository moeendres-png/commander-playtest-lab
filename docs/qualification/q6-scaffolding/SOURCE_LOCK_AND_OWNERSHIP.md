# Source Lock and Parallel-Ownership Proof (Task 2A)

## Source lock (all freshly verified 2026-09-10 before writing)

| Input | Expected | Verified |
| --- | --- | --- |
| `origin/main` | `c162871b...` | `c162871ba416c338d37f83a44fbd5b054e79ca0e` via `git ls-remote origin main` |
| `origin/main` tree | `b75a51d3...` | `b75a51d3326f502f33f0af2ce5d897ac89d60cc5` via `rev-parse HEAD^{tree}` |
| D1–D7 reconciliation branch | `6e6ac21f...` | `6e6ac21f268fd32ecb04872f0c80a020695f01b7` via ls-remote |
| D2 `research/xmage-corpus-reuse-20260910` | `bf2c4711...` / tree `e43b566f...` | HEAD and `HEAD^{tree}` match in place |
| D3 `research/d3-q6-import-automation-20260910` (moeendres-png/mage) | `a766f900...` / tree `6c429f68...` | branch, HEAD, tree match in `/home/moeen/code/mage-d3q6` |
| Forge corpus pin | `8c7e9afb...` | object present; 14 fixture scripts fetched via `git show <pin>:<path>` |

D3 result consumed as `BUILD_CLEAN_ROOM_EQUIVALENT`, evidence SYNTHETIC,
behavior credit ZERO. No local-only provenance claim repeated.

## Parallel-ownership proof (WS50)

- Worktree inventory: 20+ project worktrees listed; this workstream owns
  exactly `/home/moeen/code/q6-scaffolding-pipeline-20260910` on branch
  `qualification/q6-scaffolding-pipeline-20260910` (sole writer: this
  session's OpenCode process; verified via `/proc/<pid>/cwd` audit —
  PIDs in the D1–D7 and WS50 worktrees belong to other sessions).
- WS50 worktree `/home/moeen/code/ws50-forge-decision-sequence-slice`
  (branch `ws50/forge-decision-sequence-slice-20260910`) inspected
  read-only before every checkpoint commit (`git status --short`).
- OWNERSHIP_EXCLUSION set (never written by this task): all Forge
  runtime/provider/bootstrap paths; native Decision transport; native
  option binding; live decision sequences; attacker/blocker/payment/mode/
  target callbacks; principal-scoped Forge observations; Forge semantic
  frame journal/replay; Forge live-game construction; WS48-derived
  runtime/harness/provider surfaces; `qualification/providers/forge/**`;
  Forge/XMage Java bridge/provider code; `vendor/**`; WS47 canonical
  books/denominator; coverage truth files; production simulator code;
  `tools/foundry/cluster_failures.py` (imported read-only).
- This task's mutation surface: `tools/q6_scaffolding/**`,
  `tests/q6_scaffolding/**`,
  `docs/qualification/q6-scaffolding/**`, `.foundry/WORKSTREAM_STATE.yaml`.
  Zero overlap with WS50 paths (WS50's untracked checkpoint evidence
  under `candidate-qualification/ws50-forge-decision-sequence/` untouched).
- No integration adapter on WS50 surfaces was required: the boundary is
  specified (`tools/q6_scaffolding/integration.py` +
  `WS50_INTEGRATION_BOUNDARY.md`) with no WS50-side implementation.
  No `DEPENDENCY_ON_WS50` edit blockers remain.
