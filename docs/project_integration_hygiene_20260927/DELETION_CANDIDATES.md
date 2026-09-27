# WSR23 — Deletion Candidates

**Nothing was deleted.** §17 forbids deleting local worktrees, branches, evidence, artifacts or
historical documentation without separate explicit authorization. This file is the candidate list
that such an authorization would act on. Every row states the exact evidence that makes the
candidate *eligible*, so the decision stays with the Coordinator.

`git worktree remove`, `git branch -d/-D`, `git stash drop`, `git remote prune` and file deletion
were **not** run anywhere in this workspace.

## Tier 1 — local branch refs already contained in their default branch (zero unpublished content)

Each of these local refs points at a commit that `git merge-base --is-ancestor` proves is already
an ancestor of its repository's default branch. Deleting the ref would remove no content and no
evidence whatsoever. Measured: `commits_patch_UNIQUE = 0`, `commits_ahead_by_ancestry = 0`.

| # | Repository | Branch | Local SHA | Worktree |
|---|---|---|---|---|
| 1 | `commander-playtest-lab` | `coord/legacy-recovery-preflight-20260916-aebcfda3` | `aebcfda37` | `coord-legacy-recovery-preflight-aebcfda3` |
| 2 | `commander-playtest-lab` | `cpl/full107-execution-first-20260923` | `ca7fd4a4d` | `ws-c4-full107-execution-first-20260923` |
| 3 | `commander-playtest-lab` | `pr-173-head` | `aa772f9f0` | — |
| 4 | `commander-playtest-lab` | `ws-arclose/d1-p1p2-current-main-20260913` | `6baa24d46` | `ws-arclose-d1-p1p2` |
| 5 | `commander-playtest-lab` | `ws-opencode/opencode-1.18.32-qualification-20260924` | `2231ff4bd` | `ws-opencode-11832-qualification` |
| 6 | `forge` | `review/csn-r4-forge-s2s3-audit-20260917` | `9a1e3fe94` | `ws-csn-r4-forge-s2s3-audit` |
| 7 | `forge` | `review/csn-r5-forge205-runtime-20260917` | `1f1393021` | `ws-csn-r5-forge205-runtime-20260917` |

Caveat: each of rows 1–5 also has a registered worktree. Deleting a *branch ref* that a worktree
has checked out is refused by Git, so these are really **worktree** candidates (§11 of
`AGENTS.md` requires explicit approval for worktree deletion too).

## Tier 2 — worktrees that are clean, fully merged, and owned by a terminal workstream

Roughly 150 of the 173 Lab worktrees are clean, terminal, and have no process, lock, or
`ACTIVE`/`WAITING` state. They are individually enumerated with branch, HEAD, tree, commit date
and cleanliness in `WORKTREE_INVENTORY.json`. WSR23 deliberately did **not** collapse this into a
short hand-picked list, because a short list invites deletion of something that was not audited.
The safe use of that file is: filter on `clean == true` **and** `repo`/`head` cross-checked
against `UNPUBLISHED_BRANCHES.json` to exclude any branch carrying unique unpublished content.

The highest-value exclusions (these are **not** deletion candidates despite looking stale):

- `ws-rg-closure-20260925` — sole carrier of RG-07/RG-08 evidence. See `PUBLICATION_CANDIDATES.json`.
- `ws50-forge-decision-sequence-slice` — 51 untracked evidence paths, no owner.
- `xmage-ws49-baseline` — 7 unowned tracked modifications to Mage engine sources.
- `ws-csn-job08…job11` — ~12 000 untracked paths each, unpublished.

## Tier 3 — untracked residue with no identified owner

| Path | Content | Note |
|---|---|---|
| `commander-playtest-lab/Datenpaket_19_09/` | 1 untracked directory in the `main` worktree | On `main` itself. Unattributed. **Preserved.** |
| `commander-playtest-lab-muse-ws49/vendor/engine-source/` | untracked engine sources | Already hard-denied in `opencode.json` `external_directory` for other paths. **Preserved.** |
| `ws-physical-pool-20260919/docs/workstream_adjudication_20260920/` | untracked adjudication docs | Unpublished, unattributed. **Preserved.** |
| `ws-arclose-d1-p1p2/research/architecture-closure/ws-arclose-d1-p1p2-current-main/` | untracked | **Preserved.** |
| `mage-ws33/D4_PHASE_RS_REALITY_REPORT.md` | untracked report on a detached HEAD | **Preserved.** |
| `mage-ws33-ws33c-promo/research/greenfield-qualification/…/staging/` | untracked staging | **Preserved.** |
| `ws50-forge-decision-sequence-slice/candidate-qualification/ws50-forge-decision-sequence/` | 51 untracked paths | **Preserved.** |
| 4× `ws59/ws63/ws67/ws76` (forge) | untracked `.foundry/metrics.jsonl` | Telemetry residue. **Preserved.** |
| `commander-ws48/javac.20260910_012314.args` | stray javac argfile | **Preserved.** |

## Tier 4 — the shared repository stash (NOT a candidate; flagged so it is never lost)

`commander-playtest-lab` holds exactly one stash, shared across all its worktrees:

- `stash@{0}` = `9429face9a7401585dcc91e2649cd43fc169529f`
- message: `On muse/ws48-forge-v1.0.5-heavy-support: muse-ws48-wip`
- dated 2026-09-09, parent `895eca21` (that branch's tip)
- 3 paths, 112 insertions / 25 deletions:
  `candidate-qualification/ws48-forge-v1.0.5/behavior_driver.py` (+16),
  `candidate-qualification/ws48-forge-v1.0.5/behavior_postconditions.py` (+79/−25),
  `scripts/ws48_v105_behavior_surface.py` (+42)

**This is the only place in the workspace holding WS-48 in-progress work.** It is
`DIRTY_UNKNOWN_OWNER` by the project's own definition (no ownership field anywhere resolves it).
It must not be dropped, and it must not be applied into any other branch. If the WS-48 lineage is
ever abandoned, this stash should be promoted to a durable artifact first — that is a Coordinator
decision, not a hygiene cleanup.

## Tier 5 — duplicate clone

`/home/moeen/code/forge-candidate-h4f` is a second independent clone of
`moeendres-png/forge`, not a registered worktree of `/home/moeen/code/forge`. No WSR23 action.
Recorded so a future audit does not mistake it for a worktree of the Forge repo.

## Recommended Coordinator action

1. Authorize **Tier 1** deletion (7 branch refs) — provably content-free.
2. Decide **Tier 4** (the WS-48 stash) before any bulk worktree cleanup, because bulk cleanup is
   exactly the operation that loses stashes.
3. Treat **Tier 2** as a generated review from `WORKTREE_INVENTORY.json`, not as a pre-approved
   delete list.
