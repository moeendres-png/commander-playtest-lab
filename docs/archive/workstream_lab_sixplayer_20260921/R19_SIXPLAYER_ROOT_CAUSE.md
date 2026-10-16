# R19 Root Cause — Lab XMage Six-Player Parity

Verdict: `CONTRACT_GAP` (2–5 bound was policy, never an engine limit);
no engine/rules defects found.

## Fail-before (DIRECTLY_VERIFIED)

- Bridge gate rejected 6 (`INVALID_PLAYER_COUNT: expected 2 to 5`).
- Engine path (`CommanderFreeForAll` + `setNumPlayers`) carries no
  count cap; 6P native lifecycle green through the real entrypoint
  immediately after widening (6× 40 life/7 cards, paused turn 1).

## Production changes (minimal, mirrored R16)

- Java `XmageGameManager` gate 5→6 + message; `XmageFullGameSession`
  MIN/MAX 5→6 + contract comment.
- Python `FutureXmageScenario` (count/seat le 5→6), pilot binding seat,
  smoke-result count, `XmageFullGameRunner` MIN/MAX + docstring,
  policy pilot-count bound, batch-case validator.
- Conformance script: SMOKE/SUPPORTED +6, seed 20260828, target 55
  (live-calibrated, not estimated).
- `XmageProvider` (B4 bounded surface) deliberately UNCHANGED:
  stale-conservative max_players=5 stays fail-closed-safe.

## Test changes (contract evolution, rationale cited)

- Java `invalidGameParametersFailClosed`: (1,6)→(1,7).
- New `XmageSixPlayerGateTest` (6P lifecycle + 7P fail-closed, zero games).
- `test_xmage_variable_player.py`: lanes/(2..6)/six-seven rejections.
- `test_ws223_cardinality_regression.py`: constants/lane-targets/
  setup-coverage/seeds (2..6), fail-closed probe → 7P, six→seven
  model/binding/runner guards.

## Pass-after (DIRECTLY_VERIFIED)

- Bridge 155/155; python 761 (+19 parked/env residual, proven
  pre-existing or workflow wiring); ruff clean (below).
- Live 6P bounded smoke PASS (55 decisions, mulligan+priority+target+
  choice, seed preserved, clean shutdown).
- Live 6P full gate PASS (7284 decisions, 8 classes, natural terminal
  winner seat 2, semantic replay MATCH, raw mismatch by design).

## Verdict

Lab 2–6P SUPPORTED (bounded evidence above) | 7P+ FAIL_CLOSED |
2–5P intact (retention green) | FULL107 NOT_RUN |
ARCHITECTURE_FREEZE NOT_CLAIMED | PRODUCTION_PROVIDER NOT_SELECTED.
