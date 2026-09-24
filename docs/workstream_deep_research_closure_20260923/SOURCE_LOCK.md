# DR-CLOSURE-01 — Fresh Source Lock (Phase 0)

Workstream: `DR-CLOSURE-01 — Deep Research Findings Implementation & Qualification Closure`
Branch: `dr-closure-01-deep-research-20260924`
Worktree: `/home/moeen/code/ws-dr-closure-20260924`
Execution date (UTC): 2026-09-24
Instruction reference date: 20260923 (directory name preserved verbatim per assignment).

## 1. Fresh source lock (wins over all research-time baselines)

- HEAD SHA: `2231ff4bdd30753a127133e51a0d3657c668532d`
- TREE SHA: `f759ed34d35fdf76ebbb04814edf4a470f960e27`
- Subject: `Merge PR #239: real-deck 4P technical smoke lane`
- Tracking: `origin/main` (fetched 2026-09-24; `git fetch origin main` advanced
  `ca7fd4a4..2231ff4b`, HEAD == `origin/main`, clean tree, `git status --short` empty)
- Local branch created from `origin/main`; no rebase; no `main` mutation.

## 2. Drift vs research-time baseline (detection only, not authority)

Expected research baseline:

- Commander Lab `main = 81f688d3fd06c8edf53a289c5206dbaeef9d1fee`
- Commander Lab tree = `abd782f7ba1316d797e6044812d60386008da639`

Observed fresh source:

- `main = 2231ff4bdd30753a127133e51a0d3657c668532d` (AHEAD of research baseline)
- Tree = `f759ed34d35fdf76ebbb04814edf4a470f960e27` (differs, as expected)

Drift adjudication:

- `81f688d3` is present in fresh history (`git log` shows `81f688d3 Merge PR #240`
  as ancestor of `2231ff4b`). Delta = PR #239 merge + 6 follow-up commits
  (`6d7c60da`, `f6516961`, `bed5b9ad`, `37df8dc1`, `8d1f7824`, `61f58be5`).
- No source-lock violation. Fresh source wins; research baselines retained only
  for drift detection.

## 3. Engine / dependency pins (fresh)

- `engine-bridge/pom.xml`: `xmage.version = 1.4.61` (`org.mage:mage`,
  `mage-deck-constructed`, `mage-game-commanderfreeforall`).
- FULL107 identity binding (`docs/workstream_full107_definition_20260921/
  FULL107_IDENTITY_BINDING.json`):
  - `primary_engine.commit = db134b9737e951367d65ef5806ad986319cc73ab`
    (matches research qualification-engine pin — NO DRIFT)
  - `primary_engine.maven = 1.4.61`, `protocol = 2.0.0`, `provider = xmage`
  - `secondary_engine.provider = forge`,
    `commit = a37a865a53280dd8ad6fad3384d69611e8c5a42f`
  - `production_provider = null`, `provider_decision = NO_PROVIDER_READY`
- Architecture authority (fresh, unchanged):
  - `ARCHITECTURE_FREEZE = NOT CLAIMED`
  - `PRODUCTION_PROVIDER = NOT SELECTED`

## 4. FULL107 census (fresh, matches research-time census exactly)

Source: `docs/workstream_full107_definition_20260921/FULL107_MAPPING.json`
(`sha256:6a7fd26416dd3a94d74cf88aad8b0cbc82cba8ea88e07d7ad884be38a4c18eb1`):

```text
DIRECT = 7
SUPPORTING = 13
UNKNOWN = 57
NOT_RUN_BLOCKED = 30
TOTAL = 107
```

DIRECT (7): `CARD_02`, `WS05-CMD-TAX-2`, `WS05-CMD-TAX-4`,
`WS05-CMD-PARTNER-TAX`, `WS05-CMD-PARTNER-ZONE`, `WS05-CMD-MULL-2`,
`WS05-CMD-MULL-4`.

SUPPORTING (13): `PLAYER_COUNT_2P/3P/4P/5P`, `PILOT_PRIORITY`,
`PILOT_TARGET`, `PILOT_CHOOSE_OBJECT`, `PILOT_TARGET_AMOUNT`,
`PILOT_MULLIGAN`, `PILOT_CHOOSE_USE`, `PILOT_MANA_PAYMENT`,
`PILOT_DECLARE_ATTACKER`, `PILOT_DECLARE_BLOCKER`.

UNKNOWN (57): 8 pilot decision families, 7 fallback negatives, 20 hidden
(`HIDDEN_01..19` + sentinel), 5 replay tapes, 17 micro-mechanisms.

NOT_RUN_BLOCKED (30): 15 `WS05-MP-*` + 15 `WS05-CMD-*`, all with reason
`starting_state_injection_supported=false (contract-locked)`.

## 5. Manifest digests (fresh)

```text
6a7fd26416dd3a94d74cf88aad8b0cbc82cba8ea88e07d7ad884be38a4c18eb1  FULL107_MAPPING.json
85d7864f3fd984e1c12d5b0dc0bf0881c0cf6e1b3116f401f22dedaacc5abde9  FULL107_IDENTITY_BINDING.json
6c41450ff56894260935d2eb24da52d3d04a67e6ce751834bcbdd244bef69db6  engine-bridge/pom.xml
```

## 6. Ownership — PR #239 / PR #240 (mandatory check)

- PR #239 (`XMage: add real-deck 4P technical smoke lane`,
  `cpl/real-4p-technical-smoke-20260923`): state = **MERGED**
  (`mergedAt 2026-09-23T23:22:37Z`). Changed files (7) now part of `main`:
  `.github/workflows/xmage-real-4p-smoke.yml`,
  `engine-bridge/.../XmageDeckImporter.java`,
  `engine-bridge/.../XmageDeckImporterTest.java`,
  `scripts/run_real_4p_full_game_smoke.py`,
  `src/commander_lab/engine/rules/project.py`,
  `tests/unit/test_real_4p_full_game_smoke.py`,
  `tests/unit/test_rules_project_loader.py`.
  Disposition: **no FOREIGN_ACTIVE_OWNERSHIP** — merged surface is now shared
  `main`; do not duplicate; reuse as-is; impact-adjudicate on change.
- PR #240 (`Campaign 1: real-deck 4P terminal E2E gate`,
  `opencode/real-deck-e2e-gate-20260923`): state = **MERGED**. Do-not-redo
  surface (§16) stands; verify-before-touch applies.
- Only open PR with nearby surface: #206
  (`WS241-safe-push-effective-target-identity-fix-204`,
  `ws241/safe-push-effective-target-20260916`, OPEN since 2026-09-19).
  Surface (safe-push effective-target identity) does not overlap this
  campaign's restoration/qualification/differential/regression surfaces.
  No ownership collision. Remaining opens are stale DRAFTs (WS-34..49,
  ops/chore), none owning this campaign's mutation surface.

## 7. Recent merged lineage (fresh `origin/main`)

`2231ff4b` (PR #239) on top of `81f688d3` (PR #240), on top of #237 (reuse-first
gate), #236/#235 (CARD_02 promotion), #234/#233 (START-2 blocker record),
#232/#231 (CARD_02 execution), #230/#229 (evidence gate), #228 (frontier
checkpoint), #227–#220 (partner/tax promotions + procedure executor).
No post-research workstream implements Phase 1–7 of this campaign; the
`cpl/full107-*-20260922` branches are the merged predecessors, not competitors.

## 8. Duplicate-detection census (per research recommendation)

| Recommendation | Class | Reason |
|---|---|---|
| EC-XMAGE-STATE-01 (native restoration) | NEW_WORK_REQUIRED | v1 exists; blocked-fixture matrix + safe extensions still open |
| EC-XMAGE-CHOICE-02 (bounded candidate domain) | NEW_WORK_REQUIRED | generic invariant + actual-card regression not yet present |
| EC-MANABREW-DIFF-03 (first-divergence method) | ACTIVE_WORK_EXISTS (partial) | `Phase6DifferentialAdapter` + `semantic_replay/divergence.py` + `tests/differential/test_phase6_differential.py` exist; provider-neutral comparator hardening + real replay-pair run still required |
| EC-ARGENTUM-API-04 (observation/option/schema/digest contract) | NEW_WORK_REQUIRED (audit-first) | audit current redactor/projection/digest vs 4 patterns; implement only gaps |
| EC-PHASE-BUGS-05 (predictive regressions) | NEW_WORK_REQUIRED | no `EXTERNAL_RISK_SIGNAL` namespace yet |
| EC-FORGETS-ANTI-06 (auto-pass masking) | RESEARCH_ONLY (negative contract) | must remain REJECTED_BY_RULES_AUTHORITY; only a negative regression permitted |
| PRED-RESTORE-01 | NEW_WORK_REQUIRED | restore→transition→derived-state regression missing |
| PRED-CANCEL-02 | ALREADY_IMPLEMENTED (verify) | PR #240 cancel/fizzle handling; verify before touch |
| PRED-PARSER-03 | NEW_WORK_REQUIRED | subject/controller/count semantic-loss regression missing |
| PRED-ZONE-04 | NEW_WORK_REQUIRED | wrong-object / alternative-destination regressions missing |
| PRED-REPL-05 | NEW_WORK_REQUIRED | replacement-timing regression missing |
| PRED-HIDDEN-06 | NEW_WORK_REQUIRED | honeycard adversarial coverage exists partially (`XmageFullGameHiddenInformationTest` + canary tests); per-fixture UNKNOWN closure still open |
| PRED-AUTH-07 | NEW_WORK_REQUIRED | pilot-masking negative contract regression missing |
| Process isolation (Phase 7) | ALREADY_IMPLEMENTED (verify) | PR #240 10-game batch + `full_game_batch.py` + `process_manager.py`; audit-first, no edit without proven gap |

## 9. Worktree / branch / state ownership

- One isolated worktree, one dedicated branch, one explicit state file
  (`docs/workstream_deep_research_closure_20260923/STATE.md`).
- No `main` mutation; no push/merge/rebase; local commits only after validated
  milestones.
- Candidate/reference repos (`mage`, `forge`, upstream, Manabrew, Argentum,
  Phase) are read-only in this workstream.
