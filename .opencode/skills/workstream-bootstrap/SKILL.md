---
name: workstream-bootstrap
description: Establish repository, worktree, branch, source lock, objective, scope, ownership, and state file for a new Foundry workstream.
---

# Workstream Bootstrap

Use this when starting a new bounded workstream on `moeendres-png/commander-playtest-lab`.

## Procedure

1. Resolve the repository root and confirm it is `commander-playtest-lab` (remote check).
2. Fetch current refs. Resolve `origin/main` to an exact SHA and tree. Record both.
3. Inspect worktrees (`git worktree list`), local branches, and uncommitted state.
4. Confirm no other active workstream owns the intended mutation surface. If ownership
   is unclear, stop and ask before creating anything.
5. Create one dedicated worktree and branch: `one workstream ↔ one branch ↔ one worktree`.
   Never reuse another workstream's branch. Never work on `main` directly.
6. Write the Source Lock into the new state file: repository, worktree path, branch,
   audit-base SHA and tree, current HEAD. Do not silently rebase onto a moving source
   after work begins; if the base moves, record the delta explicitly.
7. Record objective, in-scope and out-of-scope surfaces, ownership, dependencies, hard
   gates, forbidden shortcuts, stop conditions, `TECHNICAL_DECISION_AUTHORITY`
   (default `AUTONOMOUS_WITHIN_CONTRACT`), explicit `AUTHORITY_GATES`, and the
   Exact Next Action in `.foundry/WORKSTREAM_STATE.yaml`. See
   `docs/foundry-execution/WORKSTREAM_CONTRACT_TEMPLATE.md` for the full field list.
8. End with a Source Lock summary. Missing facts stay `UNKNOWN`, never assumed.

## Rules

- Prefer the deterministic helper `tools/foundry/source_lock.py` for step 2 and 6.
- Fail closed on ownership conflicts or dirty-tree surprises.
