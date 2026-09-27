# Full Project Execution Authority — 2026-09-27

## Status

`PROJECT_SCOPED_EXECUTION_AUTHORITY = PREAUTHORIZED`

This document records the latest direct user/Coordinator instruction for Commander
Simulator Next: the selected OpenCode executor, including Space Bunny MAX, may carry a
technically valid project campaign end-to-end without stopping for routine Git/GitHub
approval gates.

## Pre-authorized project operations

Within the active campaign/workstream and after verifying current Source Truth and
ownership, the executor may autonomously:

- create/switch branches and create/remove worktrees;
- edit source/tests/docs/configuration and make commits;
- push owned branches;
- create, update, comment on, close, and merge pull requests;
- create/update/close project issues;
- use mutating GitHub API operations required for repository-scoped project work;
- merge/rebase/cherry-pick integration branches;
- rerun/fix CI and qualification;
- delete proven-superseded campaign branches/worktrees after unique-content preservation;
- continue across successive pre-Freeze workstreams without asking for routine approval.

Foundry launcher, writer-lock, and `safe_push.py` remain useful verification tools but
are not mandatory authority gates when they conflict with this current direct
authorization. A worker must not fabricate a lock or claim a wrapper PASS it did not
obtain.

## Still binding

- Rules Core remains sole Rules authority.
- `UNKNOWN != PASS`; `PARTIAL != FULL`; `NOT_RUN != PASS`.
- Hidden information, Rules RNG, semantic replay, source-lock and actual-card evidence
  invariants remain unchanged.
- One active writer per overlapping mutation surface; use isolated worktrees when needed.
- Do not mutate `main`/`master` directly; integrate through reviewed campaign branches
  and exact-head PR evidence.
- Preserve immutable evidence/provenance branches and unique unintegrated work.
- Raw secrets/credentials must not be exposed or committed.
- Remote repository creation/deletion, account/org security changes, paid services,
  Production Provider selection, and Architecture Freeze remain reserved.
- `ARCHITECTURE_FREEZE = NOT CLAIMED`.
- `PRODUCTION_PROVIDER = NOT SELECTED`.

## Execution intent

The execution loop is:

inspect → implement → test → diagnose → repair → requalify → push → PR → CI → merge →
re-lock → continue

until the assigned campaign is complete or a genuine Rules/architecture/Source-Truth
authority gate remains.
