# WS91 — D1 Current-Main Integration: Final Report

## Objective

Re-integrate only the durable D1 hardening (explicit workstream-specific
Foundry state semantics, `ROOT_STATE_SEMANTICS`) onto current canonical main
`4f69aa36` without importing stale pre-WS88/WS90 pin state and without losing
qualified WS78 token-economy tooling. No merge/rebase/cherry-pick of the old
D1 branch; semantic path/hunk integration only.

## Source locks

- `CURRENT_MAIN_BASE = 4f69aa36405957a97f538ea55145740bf127ec34`
  (tree `7335e0b6b23f88001afead676d45e36697be753c`).
- `D1_VALIDATED_SOURCE = 8d0f68494b54be9405f6372543cc721788cbdd88`
  (terminal `cf7b21c` differs only by a state-only seal; no extra credit).
- `D1_TECHNICAL_AUTHORITY = 8d0f6849`. `D1_SOURCE_LOCK = PASS`.

## Method

1. XHIGH read-first three-way adjudication (foundry-adjudicator, read-only):
   every D1 path classified (`D1_PATH_CLASSIFICATION = PASS`, persisted in
   `PATH_CLASSIFICATION.json` before edits). No `AUTHORITY_GATE`.
2. Semantic integration: 5 tooling/test files land byte-identical to D1;
   3 files (`launcher.py`, `foundry-implementer.md`,
   `RETENTION_AND_LIFECYCLE_POLICY.md`) land as current-main + D1 unions;
   `config/rules_engines.json` discarded wholesale (superseded);
   D1 regression battery rebased to current pins/wording/paths.
3. Root migration: historical bytes archived byte-identically
   (`6cf09d17...`), operational root file removed, schema kept.
4. Focused validation → broad `tests/foundry` → evidence seal → safe_push.

## Changes (working-tree surface)

- `tools/foundry/{bootstrap,launcher,worktree_inventory}.py`: explicit `--state`
  required, `WORKTREE=STATE` map authority, fail-closed maps, no fallbacks.
- `.opencode/{agents,skills}` (7 files) + `AGENTS.md` + 5 docs: explicit-state
  wording; mirror-safe remote gates; fork-pointer supersession record.
- `docs/RETENTION_AND_LIFECYCLE_POLICY.md`: D1 wording hunks + merged H4
  addendum (WS88 resolution preserved alongside).
- `tests/foundry/*` (3 files): D1 regression locks, byte-identical to D1.
- `tests/unit/test_ws_arclose_d1_authority_drift.py` (new): rebased battery
  (10 tests) — current `cfc36f` pin, WS88 manifest wording, WS91 archive path.
- `.foundry/WORKSTREAM_STATE.yaml`: removed (archived under
  `research/architecture-closure/ws91-d1-current-main-integration/`).
- Unchanged: `config/rules_engines.json` (`6471495e`), all of
  `qualification/ws79*`, `ws88*`, `ws90*`, manifests, WS78 files/pins,
  provider selection (`false`/`null`), protocol (`2.0.0`).

## Preservation verdicts

- `WS78_TOKEN_ECONOMY_PRESERVED = PASS` (5 files byte-identical, 2 unioned,
  battery 22 green).
- `WS88_PRESERVED = PASS`, `WS90_PRESERVED = PASS` (boundary paths untouched;
  pin `cfc36f` intact; behavior credit 0).
- `CURRENT_XMAGE_PIN_PRESERVED = PASS`.
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Tests / evidence

See `VALIDATION.json`. Focused batteries green on the integration tree;
`pytest -q tests/foundry` → 242 passed, 1 skipped (pre-existing telemetry
skip, unrelated). Ruff lint + format clean. All 10 negative controls PASS
(unit + live CLI probes). `CONFIG_RULES_ENGINES_BLOB_CHANGED = 0`.
`RULES_BEHAVIOR_CHANGE = 0`. `ENGINE_PIN_CHANGE = 0`.
`BEHAVIOR_CREDIT_CHANGE = 0`.

## Remaining

- Coordinator owns PR/merge (`NEW_PR_CREATED = NO`).
- `validated_head` is set in `VALIDATION.json` after final validation runs on
  the exact technical commit; the follow-up evidence commit is state-only and
  carries no separate validation credit.

## Verdict

`WS91_D1_CURRENT_MAIN_INTEGRATION = PASS` (pending remote persistence).
Exact next action: commit the semantic integration, run final validation on
that commit, seal `validated_head`, then canonical `safe_push` (dry-run then
push) to `ws91/d1-current-main-integration-20260913`.
