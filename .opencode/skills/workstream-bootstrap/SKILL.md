---
name: workstream-bootstrap
description: Establish repository, worktree, branch, source lock, objective, scope, ownership, and state file for a new Foundry workstream.
---

# Workstream Bootstrap

Use this when starting a new bounded workstream on `moeendres-png/commander-playtest-lab`.
This skill is hardened against the observed wrong-checkout failure: never infer
canonical-remote state from an unrelated local clone.

## First-stage identity gate (mandatory, in order, fail closed)

1. Canonical slug: expected repository is exactly
   `moeendres-png/commander-playtest-lab`. Do not accept a bare
   `commander-playtest-lab` fragment as proof of identity.
2. Current remote identity: run
   `git config --get remote.origin.url` in the candidate checkout and record
   the full URL. It must contain the canonical slug. On mismatch stop with
   `WRONG_LOCAL_REPOSITORY` — do not continue to ref checks in this checkout.
3. Canonical helper: prefer `tools/foundry/source_lock.py` for all identity
   checks below. It emits `WRONG_LOCAL_REPOSITORY` vs
   `REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE` as distinct reasons.
4. Fresh fetch where appropriate: `git fetch origin` (read-only, allowed for
   implementer/adjudicator) before resolving `origin/main` or a requested
   branch. Do not skip fetch and then claim a ref is absent.
5. Expected branch/head: resolve `origin/main` to exact SHA and tree
   (`git rev-parse origin/main^{commit}`, `git rev-parse origin/main^{tree}`).
   For a requested branch, resolve it against the canonical remote
   (`git ls-remote origin <branch>`) only after step 2 passes. Absence here
   is `REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE`, never
   `WRONG_LOCAL_REPOSITORY`.
6. Worktree inventory: run `tools/foundry/worktree_inventory.py` and record
    every worktree path, branch, HEAD, clean/dirty, and ownership.
    Ownership authority is explicit, never discovered: the launcher
    auto-declares its own worktree/state pair and the operator declares any
    sibling pair via repeatable `--worktree-state WORKTREE=STATE` (recorded
    in `launch-context.json` as `worktree_states`). The realizable
    standalone invocation carrying ownership evidence is:
    `python3 tools/foundry/worktree_inventory.py --workdir <repo>
    --worktree-state <WT>=<STATE> [--worktree-state ...]`
    A worktree with no declared state location reports `UNKNOWN`. Never
    guess a state file, never scan historical state files, never treat a
    historical snapshot as live ownership.
    There is no implicit active repository-root state. There is no conventional-path fallback.
7. Existing branch owner: for the intended branch, determine the owning
    worktree's `ownership` from the explicit state map when declared, else
    `UNKNOWN`. Fail closed: if another workstream's explicit state owns the
    mutation surface, stop; if the intended branch is checked out in another
    worktree at all, stop (duplicate writer, regardless of ownership); if
    ownership is `UNKNOWN` and the branch is free here, proceed with a fresh
    explicit state path (downstream push gates still refuse without
    validation credit).
8. Dirty state: run `git status --porcelain` in the candidate worktree.
   Any output is a dirty-tree surprise: stop and resolve before creating
   state.
9. No duplicate writer: reject if the same branch is already checked out in
    another worktree, with any `ownership` (declared or `UNKNOWN`) or a
    clean/dirty live tree. Live-writer exclusion stays with the writer lock;
    ownership conflicts in explicit state fail closed at the bootstrap gate.
    One workstream ↔ one branch ↔ one worktree. Never reuse another
    workstream's branch. Never work on `main` directly.

Distinguish `WRONG_LOCAL_REPOSITORY` (local remote identity is not the
canonical slug) from `REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE` (local
remote is canonical and fresh-fetched, but the requested ref is absent from
`origin`). Never infer the second from the first.

## Procedure (after the gate passes)

1. The repository root, remote identity, `origin/main` SHA/tree, worktree
   inventory, ownership, and dirty state are already frozen by the gate
   above. Do not re-derive them from a different checkout.
2. Confirm no other active workstream owns the intended mutation surface. If ownership
   is unclear, stop and ask before creating anything.
3. Create one dedicated worktree and branch: `one workstream ↔ one branch ↔ one worktree`.
   Never reuse another workstream's branch. Never work on `main` directly.
   Do not use one governance checkout to write across independent worktrees.
4. Write the Source Lock into the new state file: repository
   (`moeendres-png/commander-playtest-lab`), worktree path, branch,
   audit-base SHA and tree, current HEAD. Do not silently rebase onto a moving source
   after work begins; if the base moves, record the delta explicitly.
5. Record objective, in-scope and out-of-scope surfaces, ownership, dependencies, hard
   gates, forbidden shortcuts, stop conditions, `TECHNICAL_DECISION_AUTHORITY`
   (default `AUTONOMOUS_WITHIN_CONTRACT`), explicit `AUTHORITY_GATES`, and the
   Exact Next Action in the new explicit state file. See
   `docs/foundry-execution/WORKSTREAM_CONTRACT_TEMPLATE.md` for the full field list.
6. End with a Source Lock summary. Missing facts stay `UNKNOWN`, never assumed.

## Rules

- Prefer the deterministic helpers `tools/foundry/source_lock.py` (identity
  gate) and `tools/foundry/worktree_inventory.py` (inventory/owner/duplicate
  writer) for every bootstrap. Do not hand-roll remote/branch checks.
- Fail closed on ownership conflicts, dirty-tree surprises, or any
  `WRONG_LOCAL_REPOSITORY` / `REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE`.
- Never infer canonical-remote absence from an unrelated clone.
