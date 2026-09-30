# Project health, CI and test-quality ledger (2026-09-30)

This is the single ledger for this campaign. Author: Claude Opus 5.5, under the user's autonomous project-health authorization. It continues [`docs/ci_efficiency_20260930`](../ci_efficiency_20260930/README.md), which covers build deduplication and the scope jobs (#374, #386).

- **Source lock at start:** Lab `main` `5e2fbc94`. Live XMage pin `9375f35a` (`config/rules_engines.json`).
- **Evidence classes:** `DIRECTLY_VERIFIED` means observed in a local or CI run. `CODE_DERIVED` means read from source.

## Inventory (fresh, 2026-09-30)

- **Workflows:** 21 on `main`.
  - Every third-party action is pinned to a commit SHA.
  - Every workflow declares its token permissions (at the top level, or per job for `opencode.yml`).
  - No step interpolates untrusted event text into a shell.
  - The only `pull_request_target` workflow (`repository-tree-integrity`) checks out the base commit and reads the candidate only as data.
- **PR CI cost per workflow, mean of recent runs (minutes):**

  | Workflow | Minutes |
  |---|---|
  | PB-03 runtime | 10.7 |
  | CI (`quality` + `security`) | 7.5 |
  | H4 | 7.3 |
  | Conformance | 5.5 |
  | Meta qualification | 4.7 |
  | External integration | 3.8 |
  | Everything else | ≤ 1.4 |

  The build deduplication in #374 has already removed the largest repeated work.
- **Python suite:** 2.5k tests, about 6.8 min serially locally. The slowest single test takes 27 s (`test_mulligan_lab` tool surface); the top 30 together take 3 min.
- **Skips:** 18 markers. Each is platform-bound (FIFO, Windows junctions, bwrap, bash), needs an external engine, or is a repin-event guard superseded by a later repin (explicit successor named). None is unexplained.
- **Active lanes (do not modify their surfaces):**
  - `maintenance/test-signal-integrity` (#399 merged; state `COMPLETE`; `tests/conftest.py`, fuzz, telemetry, `.foundry` state);
  - PB-03 engine artifact identity (#395);
  - restoration (#397, F-38);
  - repin/candidate lanes.

## Findings

| ID | Category | Severity | Problem | Action | Validation | State |
|---|---|---|---|---|---|---|
| H-01 | SECURITY | high | The repository is public, and `opencode.yml` started a paid agent run holding `OPENCODE_API_KEY` and an OIDC token for any comment containing `/oc`, with the comment text as its prompt. | The job also requires `OWNER`/`MEMBER`/`COLLABORATOR` `author_association`. New `tests/unit/test_workflow_security.py` pins this for every comment-triggered job, plus the four inventory invariants above. | 110 checks pass. Negative control: without the gate the `opencode.yml` case fails. | PR |
| H-02 | DEVELOPER-EXPERIENCE / TEST-FLAKINESS | high (every agent session) | 110 Foundry tests failed in every hosted agent sandbox and passed in CI. git also reads configuration injected through the environment (`GIT_CONFIG_COUNT`/`KEY_n`/`VALUE_n`, `GIT_CONFIG_PARAMETERS`); the sandbox sets a `url.insteadOf` rewrite there, and `safe_push` correctly refuses it. Sessions kept reporting "110 environmental failures". | New `tests/foundry/conftest.py` removes environment-injected git configuration for the Foundry tests. Product code unchanged (the refusal is correct). | `tests/foundry`: 110 failed → 667 passed, 3 skipped. | PR |
| H-03 | EVIDENCE-INTEGRITY | medium | `technical_truth` reported `j_p6_merged_baseline_is_ancestor = False` in a shallow clone, where the history is merely missing. That is an unproven negative presented as a fact. | `_is_ancestor` returns `None` (UNKNOWN) when git says "not an ancestor" and the repository is shallow. Full history still proves True or False. | New hermetic test: full history gives True and False, shallow gives None. Without the fix it fails. | PR |
| H-04 | GITHUB-HYGIENE / EVIDENCE-INTEGRITY | high | #398 was merged on green checks while the repository owner's blocking review (09:49Z, head `9944d875`) was unread. The review was correct: the leaver's stale target/payment frame was still answered after it left. | The owner's follow-up (`4f18a04e`..`864571f0`) propagates XMage's native `signalPlayerConcede(true)` and retires the stale target/payment frame without a pilot response. A parallel withdrawal approach from this lane was dropped in favor of the owner's. **Rule for this lane: before merging, read the PR's reviews and comments on the exact head, not only its checks.** | See the F-39 doc; validated with the owner's commits on this branch. | PR |
| H-05 | GITHUB-HYGIENE | medium | Open issues described defects that are already fixed in the live pin and on `main`: #295 (mulligan default, fixed by #300), #327 (F-20 initiative on leave) and #328 (F-21 APNAP), both fixed in every pin since `f79e4168`. | Each closed as completed, with a comment naming the fixing commit(s) and the enabled Lab tests. #192 (needs operator approval for deletion) and #255 (Coordinator tracker) left open deliberately; #389 stays open until the F-39 follow-up merges. The earlier hygiene ledger's `NO_ACTION` on old draft PRs (unique unmerged commits) is kept. | Engine code read at `9375f35a`; tests enabled on `main`; full bridge suite 824/0 on `9375f35a`. | DONE |

## Deferred

| ID | Reason | Note |
|---|---|---|
| D-01 | owner action | Required checks in the `CPL - Canonical Main Protection` ruleset: see `ci_efficiency_20260930` recommendation 1. Still open. |
| D-02 | owner action | Disable 181 dead workflow registrations (`DEAD_WORKFLOW_REGISTRATIONS.json`). Still open. |
| D-03 | owned elsewhere | PB-03 runtime (largest PR cost, 10.7 min) belongs to the active PB-03 lane (#395). |
