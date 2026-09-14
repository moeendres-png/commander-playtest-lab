# WS203 Integration Report — Sealed WS92 D1-D5 onto Current Canonical Main

Status: INTEGRATED + FRESHLY VALIDATED on the integrated head. No behavior credit claimed.

## Changed files (current-main semantic delta)

Production (semantic reacquisition, no Rules logic):

- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameStateRedactor.java`
  - D1: per-player `granted_library` array, populated only inside an entitled window.
  - D2: `ZONE_FULL_LOOK` grant registry (`beginZoneFullLook`/`endZoneFullLook`/`hasZoneFullLook`), keyed by game id, closed in a `finally` block.
  - D3: `publicPermanent(permanent, game)` projects power/toughness/damage/sorted counters plus face-up-gated ability text; `commanderStatusView` projects registry ∪ command-zone union with damage totals and casts-from-command.
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGamePlayer.java`
  - D4: key-mode Choice branch (`choice_key` metadata, `setChoiceByKey`), twin-stable `choiceText` (UUID + GameLog short-id scrub) and `choicePrompt` (engine message or legacy fallback).
  - D5: `stablePermanentOrder` (name, zone-change counter, P/T, tapped, damage; never native UUID) for attacker/blocker declaration order.
  - D2: try/finally look window in `chooseTargetInternal` with `lookOwnerFor` (first library-zone card owner; null otherwise).
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameDecisionController.java`
  - D4: `redactObjectIds` applied to every option label/metadata; twin-stable `object_id='#'` scrub.

Tests (recreated byte-identical against current main):

- `engine-bridge/src/test/java/org/commanderlab/xmage/Ws92D1D2D3ProjectionTest.java` (3 tests)
- `engine-bridge/src/test/java/org/commanderlab/xmage/Ws92D4ChoiceProjectionTest.java` (5 tests)
- `engine-bridge/src/test/java/org/commanderlab/xmage/Ws92DecisionKindCensusTest.java` (1 test, non-scoring census driver)

Evidence namespace (this directory):

- `SOURCE_LOCK.md`, `INTEGRATION_REPORT.md` (this file), `VALIDATION.json`, `DECISION_KIND_CENSUS.json` (fresh machine output from the integrated head).

## Fresh runtime/test evidence (integrated head)

- `mvn -B -ntp -Dtest=Ws92D4ChoiceProjectionTest test`: 5 run, 0 failures.
- `mvn -B -ntp -Dtest=Ws92D1D2D3ProjectionTest test`: 3 run, 0 failures.
- `mvn -B -ntp -Dtest=Ws92DecisionKindCensusTest test`: 1 run, 0 failures; machine artifact `engine-bridge/target/ws92-decision-kind-census.json` preserved here as `DECISION_KIND_CENSUS.json`.
- `mvn -B -ntp verify` (full current engine-bridge suite): 63 run, 0 failures, 0 errors, 0 skipped (54 pre-existing + 9 WS92).
- Fail-closed boundary preserved in the same run: `XmageBridgePlayerFailClosedTest` (5), `XmageFullGameBridgeContractTest` (2), `XmageFullGameInventoryTest` (1), `XmageActionSubmissionTest` (1) — all green; `legal_actions`/`action_submission` remain unsupported (`false`).
- Python: `pytest -q tests/unit/test_ws_a1r_pin_authority.py tests/unit/test_ws_a1d_docker_pin_authority.py tests/unit/test_xmage_full_game.py tests/unit/test_xmage_compatibility_provider.py tests/unit/test_ws_arclose_d1_authority_drift.py`: 75 passed.
- `ruff check engine-bridge tools/foundry tests/unit/test_ws_a1r_pin_authority.py`: All checks passed.
- `FULL107 = NOT_RUN` (out of scope, unchanged).

## Historical claims preserved versus newly validated

- Preserved (provenance, not re-credit): WS92 sealed census shape (37 answered, stop on turn-1 cleanup `choose_object` discard with 8 hand options, 2 observed / 18 not-observed) and WS92 FINAL_REPORT boundary verdict (`BLOCKED_BY_BOUNDARY` on B4-D).
- Newly validated (DIRECTLY_VERIFIED on the integrated head): D1 granted-library empty-outside-window + viewer/owner scoping; D2 window open/close lifecycle; D3 P/T/damage/counters + face-up gating + 8-entry commander status; D4 redaction + key-mode + prompt fallback; D5 content-stable ordering implementation (ordering comparator present and wired; replay equality NOT claimed).
- `D5_TWIN_EQUALITY = UNKNOWN` (unchanged): WS203 obtained no fresh twin runtime comparison; the historical single-game lane leaves equality unproven and it is not promoted.
- `BEHAVIOR_CREDIT_CHANGE = 0`; census remains non-scoring reachability evidence; construction is not treated as behavior.

## Remaining B4-D boundary

- `B4_D_ACTION_SUBMISSION = NOT_IMPLEMENTED`: `legal_actions` and `action_submission` remain unsupported. Fresh integrated-head census reproduces the sealed shape: OBSERVED (reachability only) = `pass`, `hidden-zone selection`; NOT_OBSERVED (18) = `cast`, `targets`, `mana payment`, `activate`, `mana source`, `X`, `replacement ordering`, `trigger ordering`, `modes`, `copy choices`, `search`, `attackers`, `defender per attacker`, `blockers`, `combat damage assignment`, `alternate cost`, `Commander movement`, `concession` — each blocked on the B4-D action-submission pilot. `XMAGE_FIRST_WAVE_EXECUTION_READINESS = BLOCKED_BY_BOUNDARY`.
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`. `RAW_GIT_PUSH_USED = NO`.
