# Resumption kit — pre-Freeze completion campaign

Date: 2026-09-27
Supersedes: the launcher-based procedure below is **retired**. The Coordinator granted full local
OpenCode/GitHub execution authority, so ordinary Git and GitHub operations are now the path.

---

## 0. Where the campaign stands

| Item | State |
|---|---|
| WSR23 branch | `wsr23/project-integration-hygiene-20260927`, clean tree, unpublished |
| Remote WSR23 | still at `c5f9418e` — nothing has been pushed |
| `origin/main` | **`b786fbf2`** (PR #266 merged) — collides with this branch on 4 paths, see §1a |
| Full suite on a clean tree | **1642 passed, 5 skipped, 0 failed** |
| `tests/foundry` | 451 passed, 1 skipped |
| ruff / mypy strict / compileall / invariant audit | clean |
| Execution policy | **widened and committed** (`1264fc07`); needs a session restart to take effect |
| Campaign deliverables | 6 documents, see §4 |

## 1. The one action required: restart this OpenCode session

Nothing else is pending on configuration. OpenCode 1.18.30 compiles the permission table once at
session start, so the widened `opencode.json` is on disk and resolves correctly under
`opencode debug config`, but this running session still enforces the retired table. Verified:
`git push --dry-run` is still refused by the old rules.

Restart OpenCode in this worktree and resume. No flag, no environment variable, no wrapper.

## 1a. Do this immediately after the restart: resolve the PR #266 drift

**`origin/main` is now `b786fbf2` (`Merge PR #266: explicit multi-workstream Foundry access`), not the
Coordinator's `8d2aacd5`.** It moved during the policy work and collides with this branch on four
paths: `opencode.json`, `tools/foundry/launcher.py` (`tests/foundry/test_launcher.py`), and
`tests/foundry/test_ws75_tooling_hardening.py`.

PR #266 is a **process-level** layer, not a permission-table change: it adds
`tools/foundry/workspace_access.py` (each surface binds repo identity + exact HEAD/tree; `owned-write`
binds branch/state/ownership and is multi-locked for the child lifetime) and
`tools/foundry/fs_sandbox.py` (a fail-closed **Bubblewrap read-only-root mount namespace**). Because
that containment is enforced by the kernel, the Coordinator's permission widening does **not** weaken
it.

Merge recipe — full adjudication in `CAMPAIGN_STATE.md` §1.1:

1. Base on **main's** `launcher.py`; re-apply this branch's model-routing changes only
   (`CANONICAL_MODEL`/`ALTERNATE_MODEL`/`DEFAULT_EXECUTION_PROFILE`, the exact-two-executors
   allowlist + single-authorized-variant guard, the resolved-profile bundle branch, the unconditional
   `--model` child pin).
2. Base on **main's** `opencode.json`; re-apply the widening, **keeping main's `mvn*`, `./mvnw*`,
   `gradle*`, `./gradlew*` entries** so engine builds remain explicitly expected.
3. Re-apply the policy-test updates onto main's much larger test files. Main's new tests must keep
   passing; where main asserted the retired narrow policy, use the same in-both-directions rewrite
   applied here rather than dropping the assertion.
4. Re-run the **full** suite. A textually clean merge is not evidence that the semantic merge is
   correct — main's 616 new launcher test lines must be re-verified against the widened policy.

## 2. After the restart — Phase A

```bash
cd /home/moeen/code/wsr23-project-integration-hygiene
git fetch --all --prune
git push --set-upstream origin wsr23/project-integration-hygiene-20260927
gh pr create --base main --head wsr23/project-integration-hygiene-20260927 --title "..." --body "..."
```

`tools/foundry/safe_push.py` remains available and is still worth running as an extra verification
step if the launcher happens to hold the writer lock. It is no longer mandatory: the Coordinator
authorized normal Git operations, and a refusing wrapper must not stop authorized work. **Do not fake
a Foundry lock** to satisfy it.

Then: inspect exact-head CI, adjudicate current-main drift (the branch touches `docs/**` only), merge,
re-read post-merge `main` HEAD/TREE, persist the receipt, and update/close Issue #263.

## 3. Ordered continuation

Do not stop at the merge. Serial, dependency-ordered:

1. **Re-lock main.** Never cut a branch from the stale local `main` (`586914ea`); use `origin/main`.
2. **WSR22 successor integration** — follow `WSR22_IMPACT_ADJUDICATION.md` §5 exactly. Cut from fresh
   `origin/main`; transplant whole files from `208341c6124674046787f3a4b1d699c98c286a27`; adopt the
   2026-09-25 Rules receipt; **regenerate** `qualification/SHA256SUMS` and `WS17_SHA256SUMS`; update
   the affected assertions in `tests/qualification/test_pre_freeze_contract_successor.py`; run only
   the four mechanical items. Never transplant a manifest. Mark PR #269 superseded only after
   preservation is proven.
3. **PB-09** — Coordinator decision, ranks first. See `PB09_FORGE_CANDIDATE_IDENTITY.md` §6. Do not
   repin `config/rules_engines.json` to `ef958ee9` to make the evidence look consistent.
4. **PB-03** — see `PB03_ROOT_CAUSE_AND_REMEDIATION.md`. Capability-driven dimension admission, not
   fixture-name-driven. Never flip `starting_state_injection_supported`. Keep the denominator at 107.
5. **PB-06 / PB-07 / PB-08** by decision value.
6. **AF00–AF11** recompute, then regenerate `PRE_FREEZE_COMPARISON_PACKAGE.md`.

## 4. Durable deliverables already committed

| Path | Content |
|---|---|
| `docs/project_integration_hygiene_20260927/STATE_OWNERSHIP_REPAIR.md` | Phase A: fail-before, four-source layer diagnosis, both repairs, validation |
| `docs/project_integration_hygiene_20260927/PUBLICATIONS.md` | corrected publication diagnosis + the gate-by-gate push table |
| `docs/pre_freeze_completion_20260927/CAMPAIGN_STATE.md` | re-lock ledger, execution-policy status, authority notes |
| `docs/pre_freeze_completion_20260927/WSR22_IMPACT_ADJUDICATION.md` | the 5 divergent paths, Rules-authority resolution, successor spec |
| `docs/pre_freeze_completion_20260927/PB03_ROOT_CAUSE_AND_REMEDIATION.md` | root cause, correct layer, forbidden fixes, per-row projection |
| `docs/pre_freeze_completion_20260927/PB09_FORGE_CANDIDATE_IDENTITY.md` | the executed Forge candidate is a Lab Rules-Core fork; Coordinator decision |
| `docs/pre_freeze_completion_20260927/PRE_FREEZE_COMPARISON_PACKAGE.md` | denominator-complete accounting, AF standing, freeze readiness |

The WSR23 state file at `docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml` carries
`validated_head`, the full test list, and an `exact_next_action` restating this ordering.

## 5. Environment note

The lock-faithful validation venv is `/tmp/opencode/cpl-venv` (CPython 3.12.14, built with
`pip install --require-hashes -r requirements/lock.txt` then
`pip install --no-deps --no-build-isolation -e .`, matching the CI quality job). The ambient system
interpreter **cannot** run the suite: it lacks `typer`, `httpx2` and `pytest-asyncio`. That is a
pre-existing environment boundary, not a repository defect.

**Diagnostic worth keeping:** an intermediate full-suite run shows ~52 failures with
`stale canonical inputs rejected: tracked software worktree differs from recorded git tree` whenever
tracked files are modified but uncommitted. It is the suite's intentional source-lock guard, not a
regression. Commit first, then run the suite.

## 6. Things a later session must not do

- **Do not flip `starting_state_injection_supported`** to unblock PB-03. Two tests correctly assert
  it stays `false`.
- **Do not reduce the FULL107 denominator.** `denominator_decreased_to_bypass_blocker` must stay
  `false`.
- **Do not transplant a generated manifest**; regenerate it from the integrated tree.
- **Do not repin or edit `ef958ee9`** into a provenance or pin field to make the Forge evidence look
  consistent. The executed commit is a historical fact.
- **Do not read Forge 79 PASS versus XMage 30 PASS as capability ranking.** Only 25/107 rows are
  `SAME_SEMANTICS`, XMage ran pristine at its pin, and the Forge column measures a Lab Rules-Core
  fork.
- **Do not expand the Meta-Qualification v1 mutation catalogue** without a demonstrated fault seam
  the existing eight domains would miss.
- **Do not weaken a test to obtain green.** Policy tests were rewritten to assert the *authorized*
  policy in both directions, never dropped.
