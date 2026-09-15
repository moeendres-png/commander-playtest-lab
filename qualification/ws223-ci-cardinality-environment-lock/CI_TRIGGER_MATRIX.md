# WS223 CI Trigger Matrix

Heavy JVM lane = `xmage-full-game-conformance.yml`. Light lane = `ci.yml`
(full pytest on every push/PR).

| Changed surface | Heavy lane? | Light lane? | Rationale |
|---|---|---|---|
| `engine-bridge/**` | YES | YES | bridge behavior is cardinality-relevant |
| `src/.../engine/rules/full_game.py` | YES | YES | runner + policy + shared semantic transcript |
| `src/.../engine/rules/full_game_batch.py` | YES | YES | batch cardinality validation |
| `src/commander_lab/agents/**` | YES | YES | pilot policy per seat |
| `src/commander_lab/models/pilots.py` | YES | YES | pilot config/binding shape |
| `src/commander_lab/candidates/models.py` | YES | YES | scenario cardinality constraints |
| `tests/unit/test_xmage_full_game.py` | YES | YES | full-game guards |
| `tests/unit/test_xmage_variable_player.py` | YES | YES | WS220 gap closed (was missing) |
| `tests/unit/test_ws223_cardinality_regression.py` | YES | YES | this workstream's gates |
| `scripts/run_external_full_game_conformance.py` | YES | YES | lane driver |
| `scripts/generate_full_game_contract_artifacts.py` | YES | YES | contract artifacts |
| `scripts/write_environment_receipt.py` | YES | YES | lane receipt |
| `requirements/lock.txt` | YES | YES | env identity input |
| `src/commander_lab/semantic_replay/**` | NO | YES | WS218 adjudication: replay-only, no engine interaction |
| `tests/unit/test_semantic_replay_tape.py` | NO | YES | same |
| docs-only changes | NO | YES (pytest unaffected paths still run cheaply) | never launch JVM for prose |

PR and push path filters are kept identical over the production set so a
merge to `main` cannot bypass what a PR proved.
