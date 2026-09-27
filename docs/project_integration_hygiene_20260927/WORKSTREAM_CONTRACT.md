# WSR23 — Workstream Contract

**Workstream:** WSR23 — Project integration, hygiene, and publication closure
**Issue:** [#263](https://github.com/moeendres-png/commander-playtest-lab/issues/263)
**Branch:** `wsr23/project-integration-hygiene-20260927`
**Worktree:** `/home/moeen/code/wsr23-project-integration-hygiene`
**Execution:** `opencode-go/space-bunny-free`, native `max` reasoning, effort field `high`

## 1. Source Lock

- Repository `moeendres-png/commander-playtest-lab`; single `origin`.
- Audit base `c5f9418e755a02ffec0e02c34b4a739baf10f5f0`, tree
  `610f93d81e3b7154731d95472be6dcac05057eac`
  ("Merge PR #254: normalize START-2 and AF01 pre-Freeze contracts", 2026-09-27T15:41:06+02:00).
  `origin/wsr23/project-integration-hygiene-20260927` existed at dispatch pointing at exactly
  this commit, and the worktree was created tracking it.
- `git fetch --all --prune` performed once before the audit; three new remote branches were
  observed (`ops/dual-executor-governance-hardening-20260927`,
  `sol/meta-qualification-v1-20260927`, `wsr23/project-integration-hygiene-20260927`).
- Local `main` is 54 commits behind `origin/main` and is a pure fast-forward; WSR23 did not
  move it, and does not modify `main` (§11 of `AGENTS.md`).
- Read-only engines: `moeendres-png/forge`, `moeendres-png/mage`. Read-only references:
  `wingedsheep/argentum-engine`, `NullPriority/quorune`.

## 2. Objective

Inventory the whole `/home/moeen/code` Commander Simulator Next workspace; separate active
from stale work; classify every open PR; adjudicate every local branch whose tip is
unpublished; repair only free, non-overlapping Lab integration/hygiene defects; validate;
publish what is provably publishable; and leave a durable ledger that lets the Coordinator see
exactly what remains.

## 3. In scope

- Read-only inventory of repositories, worktrees, branches, locks, processes, state files,
  PRs, issues, and CI under `/home/moeen/code`.
- Classification of dirty work and unpublished branches, with preservation.
- Repair of free, non-overlapping Lab documentation/integration defects on the WSR23 branch.
- Validation (pytest, ruff, mypy strict, state validation, compile).
- Safe fast-forward publication of the WSR23 branch and opening one WSR23 PR.
- Terminal supersession comments plus closure of the four PRs that satisfy all six §10
  conditions.

## 4. Out of scope

- Any mutation of WSR22, PR #260, PR #261, PR #262, PR #259, issue #255, or another active
  worker's branch or worktree.
- Any XMage or Forge Rules-engine change. Engine defects are recorded, not fixed.
- Provider selection, `PRODUCTION_PROVIDER`, `ARCHITECTURE_FREEZE`, qualification policy,
  evidence promotion, FULL107, WS232 or any requalification matrix.
- Force push, history rewrite, branch deletion, worktree deletion, repository settings,
  protection changes, auto-merge, PR merges, credential inspection.
- Any repository under `/home/moeen/code` that carries no Commander Simulator Next remote.

## 5. Ownership

`TECHNICAL_DECISION_AUTHORITY = AUTONOMOUS_WITHIN_CONTRACT`.
One workstream ↔ one branch ↔ one worktree ↔ one mutation surface. WSR23's mutation surface is
`docs/project_integration_hygiene_20260927/**` plus exactly one existing file,
`docs/foundry-execution/GOVERNANCE_SUPERSESSION.md`.

## 6. Hard gates

- No mutation of any path in the diff of PR #260, #261, #262 or WSR22. Verified path-by-path
  before writing.
- No `git push` outside the project's hardened `tools/foundry/safe_push.py`. No raw `git push`.
- No Rules semantics change, and no second Rules Engine.
- `UNKNOWN != PASS`. No historical PASS is promoted to current PASS.
- Any write permission denial is respected, never wrapped or bypassed.

## 7. Forbidden shortcuts

- Inferring supersession from PR age.
- Using `git rev-parse <rev>:<path>` as an existence probe (it echoes its argument to stdout
  for a missing path). `git cat-file -e` is used instead.
- Assuming the `git cherry` sign convention. It was verified empirically against
  `origin/main~10..origin/main` before any classification depended on it: `+` means no
  patch-equivalent commit exists in the default branch.
- Treating a `CURRENT`/`FINAL`/`LATEST` filename as freshness authority.
- Promoting a delegated audit's conclusion without re-verifying its decisive evidence.

## 8. Evidence requirements

Every classification names a SHA, blob identity, path, PR number, or in-main document.
Absence claims are proven with `ls-tree`/`cat-file`, never assumed.

## 9. Persistence

`docs/project_integration_hygiene_20260927/` plus a schema-2.0 `WORKSTREAM_STATE.yaml`
validated by `tools/foundry/state.py`.

## 10. Stop conditions

Scope COMPLETE; an irreconcilable Source Lock violation; another active owner's mutation
surface; a genuine `AUTHORITY_GATE`; a destructive or external consent requirement; or
proceeding would weaken Rules/Evidence/Privacy invariants.

---

`ARCHITECTURE_FREEZE = NOT CLAIMED`
`PRODUCTION_PROVIDER = NOT SELECTED`
