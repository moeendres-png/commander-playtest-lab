# WS215 CARDINALITY_IMPACT_MAP

Every hard-coded 4P assumption (verified in source at audit base `592f23c9`;
paths absolute from repo root). Each row names the single systemic fix.
There is exactly one Rules semantics: the production session refactored
directly (no parallel 2P/3P/5P implementations, no compat divergence).

## Java production (`engine-bridge/src/main`)

| # | Location | Assumption | Fix |
|---|----------|------------|-----|
| J1 | `xmage/XmageFullGameSession.java:39` | `PLAYER_COUNT = 4` constant | `MIN_PLAYERS=2`, `MAX_PLAYERS=5`, per-session `playerCount` |
| J2 | `XmageFullGameSession.java:66-70` | `deckHandles.size() != 4` → `FULL_GAME_REQUIRES_EXACTLY_FOUR_PLAYERS` | Range check 2..5 → `FULL_GAME_INVALID_PLAYER_COUNT` before deck resolution |
| J3 | `XmageFullGameSession.java:72` | `startingPlayerSeat` range `>= PLAYER_COUNT` | Range against `playerCount` |
| J4 | `XmageFullGameSession.java:87,109,128-146` | Deck loop, `setNumPlayers(4)`, registration loop, `expected 4` setup check | All driven by `playerCount` |
| J5 | `XmageFullGameSession.java:531` | `operational_pod_size = PLAYER_COUNT` (static 4) | Per-game `playerCount` |
| J6 | `xmage/XmageFullGameJsonlBridge.java:158-165` | `deckHandles.size() != PLAYER_COUNT` → `invalid_player_count` ("exactly four") | 2..5 range; message names supported range |
| J7 | `XmageFullGameJsonlBridge.java:190` | `player_count = PLAYER_COUNT` (static) | Session `playerCount()` accessor |
| J8 | `XmageFullGameJsonlBridge.java:449,501,520` | `max_players=4`, lane/started `operational_pod_size=4`, note "exactly four-player" | `min_players=2`, `max_players=5`; lane/started carry min/max (singular pod-size key retired at lane scope; per-game truth stays in `statusPayload.player_count`/`operational_pod_size`); notes updated |

Untouched by design: `XmageFullGameDecisionController` (actor binding is
principal-UUID based, count-free), `XmageFullGameActionProjection`
(decision-scoped, count-free), `XmageFullGameStateRedactor` (seat is computed
from live game order, count-free), concede offer/submit (exact-principal,
count-free), seed binding block (count-free).

## Python production (`src/`)

| # | Location | Assumption | Fix |
|---|----------|------------|-----|
| P1 | `commander_lab/engine/rules/full_game.py:52-53` | `FullGamePilotBinding.seat: ge=1, le=4` | `le=5` (exact coverage enforced per-run, not in the binding alone) |
| P2 | `full_game.py:308-316` | Policy requires exactly 4 pilots, seats `{1,2,3,4}`, mulligan map 1..4 | Accept N in 2..5; seats `== set(1..N)`; dynamic mulligan map; store N |
| P3 | `full_game.py:778-865` `_pilot_state` | `pod_size=4`, `opponents_to_act_before_next_turn=3` | `pod_size=N`, opponents-to-act `=N-1` |
| P4 | `full_game.py:1107,1132-1139,1180-1193` | Runner docstring + fixed 4-tuples; `seed % 4`; `player_count != 4` creation check | Variadic tuples; `seed % N`; `player_count == N` |
| P5 | `full_game.py:1256-1305` `_validate_inputs` | `player_count != 4`, 4 distinct decks, seats 1..4 | N-consistency: scenario/decks/pilots lengths, distinct decks, seats 1..N, `scenario.seat <= N`, opponent ids length N-1 |
| P6 | `full_game.py:1307-1337` `_validate_handshake` | `lane operational_pod_size == 4` | Lane `min_players/max_players` bound the scenario count; per-game `player_count == N` still enforced at creation |
| P7 | `full_game.py:1368-1415` `_build_result` | `len(outcomes) != 4` rejected | `len(outcomes) == scenario.player_count` |
| P8 | `full_game.py:1228-1254` `run_replay_gate` | Fixed 4-tuples | Variadic (delegates to `run`) |
| P9 | `commander_lab/engine/rules/full_game_batch.py:39-52` | Fixed 4-tuples; batch cases require exactly 4 | Variadic + N-coverage validation |
| P10 | `commander_lab/candidates/models.py:219-232` | `FutureXmageScenario.player_count: Literal[4]`, `opponent_deck_ids: 3-tuple`, `seat le=4` | `player_count: 2..5`; `opponent_deck_ids: len == N-1`; `seat: 1..N` |
| P11 | `scripts/generate_full_game_contract_artifacts.py:50` | Invariant `operational_pod_size: 4` | `min_players/max_players` + `operational_pod_sizes: [2,3,4,5]` |
| P12 | `commander_lab/models/tooling.py:767` | `DeckDecisionPrepareInput.seat_position le=4` | Out of scope (deck-decision tooling, not full-game orchestration); left unchanged |

Untouched by design: `decide()` dispatch (all 17 decision classes count-free;
seat derived from live `pilot_state.seat`, never arithmetic over 4), combat/
target/mana/numeric sub-policies (count-free), redaction-adjacent `_object_owner`
(zone scan, count-free), RNG derivation `seed:seat:offset:class` (seat is a
value, not a range).

## Tests / scripts (contract locks updated, not weakened)

| # | Location | Change |
|---|----------|--------|
| T1 | `engine-bridge/.../XmageFullGamePlayerCountTest.java` | Rewrite: 0/1/6+ fail closed (`FULL_GAME_INVALID_PLAYER_COUNT`); 2/3/4/5 construct |
| T2 | `engine-bridge/.../XmageFullGameBridgeContractTest.java` | Capabilities min/max; lane min/max; invalid counts (1 and 6 handles) rejected with `invalid_player_count` |
| T3 | `engine-bridge/.../XmageVariablePlayerLifecycleTest.java` (new) | Per-count bounded lifecycle + seed binding + hidden-info structural + 3P/5P concession + multi-defender observation |
| T4 | `tests/unit/test_xmage_full_game.py`, `test_xmage_full_game_decision_matrix.py` | Unchanged (4P cases remain valid under the generalized contract; 4P regression) |
| T5 | `tests/test_candidate_lossless_handoff.py:218` | `test_future_xmage_contract_is_strictly_four_player` → variable-count contract test (this IS the workstream objective, not weakening) |
| T6 | `tests/unit/test_xmage_variable_player.py` (new) | Fail-closed + N-coverage + handshake + result + policy-N unit tests (no JVM) |
| T7 | `scripts/run_external_full_game_conformance.py` | Unchanged 4P smoke (still valid) |

Out of scope (deliberately untouched): optimizer_v2/decision-contract
`operational_pod_size=4` surfaces, census artifacts, B3 lane, workflows other
than full-game conformance assertions.

Machine companion: `CARDINALITY_IMPACT_MAP.json`.
