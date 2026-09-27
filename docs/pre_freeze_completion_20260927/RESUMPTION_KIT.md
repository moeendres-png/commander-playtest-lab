# Resumption kit — pre-Freeze completion campaign

Date: 2026-09-27
Purpose: everything a launcher-authorized session needs to resume at full speed with zero
re-derivation. Every command below is byte-verified against the actual tool CLIs in this session.

---

## 0. Where the campaign stands

| Item | State |
|---|---|
| WSR23 branch head to publish | `f5390fb1…` on `wsr23/project-integration-hygiene-20260927` |
| `validated_head` | `f5390fb1…` — 1638 passed / 5 skipped / 0 failed, clean tree, lock-faithful venv |
| Bootstrap gate | `BOOTSTRAP_PASS` |
| State validation | `STATE_OK`, schema 2.0 |
| `safe_push` dry-run | rejects at **gate 6 only**; gates 1–5 and 7–9 pass |
| Working tree | clean |
| Campaign deliverables | 4 committed documents, see §5 |

## 1. Launch command (the one thing that must change)

Run from `/home/moeen/code/wsr23-project-integration-hygiene`. `--workstream` is **mandatory and
load-bearing**: the bootstrap gate compares it to the state file's `ownership` field, and omitting it
is precisely what produced the original `LAUNCH_REFUSED`.

```bash
python3 tools/foundry/launcher.py launch \
  --profile cpl \
  --worktree /home/moeen/code/wsr23-project-integration-hygiene \
  --workstream wsr23-project-integration-hygiene-20260927 \
  --branch wsr23/project-integration-hygiene-20260927 \
  --audit-base-sha bbbb6b9c3e9297265c2a488c9ae72a72c0ff3719 \
  --state /home/moeen/code/wsr23-project-integration-hygiene/docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml \
  --canonical-root /home/moeen/code/commander-playtest-lab \
  --execution-profile space-bunny \
  --effort high \
  --mode writer \
  --ui-mode tui \
  --install-hook
```

Verified against `launcher.py launch --help`; every flag above exists. `--allow-same-cwd-pids` is
**not** needed in the relaunched session, because the launcher itself will be the same-CWD holder.

`--install-hook` installs the branch-scoped pre-push hook so a direct `git push` on this branch is
refused and only the hardened safe-push can publish. Recommended.

## 2. Verify the writer lock is genuinely held (do not assume it)

The campaign's Phase A explicitly requires proving the lock, because the original failure was a
missing lock wearing the costume of a push-policy problem.

```bash
python3 tools/foundry/writer_lock.py check \
  --worktree /home/moeen/code/wsr23-project-integration-hygiene --fail-if-held
```

Expect `held: true` with a holder PID that is an **ancestor** of the pushing process. If `held` is
`false`, the lock was not acquired and the push must not be attempted.

Then confirm the launcher context actually arrived — its absence is what proved the original
launcher never ran:

```bash
python3 tools/foundry/safe_push.py \
  --worktree . \
  --expected-branch wsr23/project-integration-hygiene-20260927 \
  --state docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml \
  --expected-slug moeendres-png/commander-playtest-lab \
  --dry-run
```

## 3. Publish, then open the PR

```bash
# real push (identical to the dry run, minus --dry-run)
python3 tools/foundry/safe_push.py \
  --worktree . \
  --expected-branch wsr23/project-integration-hygiene-20260927 \
  --state docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml \
  --expected-slug moeendres-png/commander-playtest-lab
```

Then `gh pr create` against `main`. Inspect exact-head CI, adjudicate current-main drift (main is
`8d2aacd5…`; only `docs/**` paths are involved, so drift impact should be nil), and merge when the
campaign gates pass. Re-read post-merge `main` HEAD/TREE — do not assume them.

## 4. Ordered continuation after the WSR23 merge

Do not stop at the merge. Serial, dependency-ordered:

1. **Re-lock main.** Fresh `git fetch`; record the new HEAD/TREE. Note that local `main` in
   `/home/moeen/code/commander-playtest-lab` is **stale** (`586914ea`, behind `8d2aacd5`); never cut
   a branch from it. Do not fast-forward it without permission — that needs `git merge`.
2. **WSR22 successor integration.** Follow `WSR22_IMPACT_ADJUDICATION.md` §5 exactly. Cut from fresh
   `origin/main`; transplant whole files from `208341c6…`; adopt the 2026-09-25 receipt; **regenerate**
   `qualification/SHA256SUMS` and `WS17_SHA256SUMS`; update the affected assertions; run only the four
   mechanical items. Never transplant a manifest.
3. **Mark PR #269 superseded** only after step 2 proves every WSR22 evidence family is on `main` with
   provenance intact.
4. **PB-09** (Coordinator disposition: leave as an evidence-integrity blocker). Decide which Forge
   bridge identity is the candidate — repin to `ef958ee9`, or re-run Forge evidence at `4753bb7c` —
   and make the bridge report a **build-derived** commit instead of `env:FORGE_ENGINE_SHA`. Do not
   edit `ef958ee9` into a provenance field to match a pin.
5. **PB-03** per `PB03_ROOT_CAUSE_AND_REMEDIATION.md`. Replace the fixture-id prefix hardcode with
   per-row dimension admission against the bridge's published `dimensionsPayload()`. **Never** flip
   `starting_state_injection_supported`. Keep the denominator at 107. Rerun only impacted rows.
6. **PB-06, PB-07, PB-08** by decision value.
7. **AF00–AF11** recompute, then regenerate `PRE_FREEZE_COMPARISON_PACKAGE.md`.

## 5. Durable deliverables already committed

| Path | Content |
|---|---|
| `docs/project_integration_hygiene_20260927/STATE_OWNERSHIP_REPAIR.md` | Phase A: fail-before, four-source layer diagnosis, both repairs, validation |
| `docs/project_integration_hygiene_20260927/PUBLICATIONS.md` | corrected publication diagnosis + the gate-by-gate push table |
| `docs/pre_freeze_completion_20260927/CAMPAIGN_STATE.md` | Phase B re-lock ledger + authority gate |
| `docs/pre_freeze_completion_20260927/WSR22_IMPACT_ADJUDICATION.md` | Phase C: the 5 divergent paths, Rules-authority resolution, successor spec |
| `docs/pre_freeze_completion_20260927/PB03_ROOT_CAUSE_AND_REMEDIATION.md` | Phase D: root cause, correct layer, forbidden fixes, row projection |
| `docs/pre_freeze_completion_20260927/PRE_FREEZE_COMPARISON_PACKAGE.md` | Phases F/G/H: denominator-complete accounting, AF standing, PB-09, freeze readiness |

The WSR23 state file at `docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml` carries
`validated_head`, the full test list, and an `exact_next_action` that restates this ordering.

## 6. Environment note

The lock-faithful validation venv is `/tmp/opencode/cpl-venv` (CPython 3.12.14, built with
`pip install --require-hashes -r requirements/lock.txt` then
`pip install --no-deps --no-build-isolation -e .`, matching the CI quality job). The ambient system
interpreter **cannot** run the suite: it lacks `typer`, `httpx2` and `pytest-asyncio`. That is a
pre-existing environment boundary, not a repository defect.

## 7. Things a later session must not do

- Do not acquire the Foundry writer lock from a non-launcher process. It satisfies gate 6 and is
  exactly the bypass the gate exists to prevent.
- Do not flip `starting_state_injection_supported` to unblock PB-03. Two tests correctly assert it
  stays `false`.
- Do not reduce the FULL107 denominator. `denominator_decreased_to_bypass_blocker` must stay `false`.
- Do not transplant a generated manifest; regenerate it from the integrated tree.
- Do not edit `ef958ee9` into a provenance field to make it match a pin.
- Do not expand the Meta-Qualification v1 mutation catalogue without a demonstrated fault seam the
  existing eight domains would miss.
- Do not read Forge's 79 PASS versus XMage's 30 PASS as capability ranking. Only **25 of 107** rows
  are `SAME_SEMANTICS`, and PB-09 gives a mechanical candidate-side cause for the gap.
