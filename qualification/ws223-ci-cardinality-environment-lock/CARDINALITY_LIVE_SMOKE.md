# WS223 Live Cardinality Evidence (local-equivalent, 2026-09-15)

Runner: isolated locked venv A (`requirements/lock.txt` @
`200159e3…`, `--require-hashes`), bridge built from `engine-bridge/` with
Eclipse Temurin JDK 17 (`/usr/lib/jvm/java-17-openjdk-amd64`), XMage engine
`1.4.61` @ `db134b97…` (WS218/WS215 authority), Isamaru-mirror fixtures.

| Count | Command | Result |
|---|---|---|
| 2P | `--player-count 2 --smoke-decisions 25` | PASS — 25 decisions; mulligan/priority/mana_payment/target/choose_object; seed+count preserved; clean shutdown (`CARDINALITY_2P.json`) |
| 3P | `--player-count 3 --smoke-decisions 25` | PASS — 25 decisions; mulligan/priority/target/choose_object; preserved; clean shutdown (`CARDINALITY_3P.json`) |
| 4P | (default full gate) | PASS — game over, 3105 decisions, winner seat 2, semantic replay match, 8 decision classes, hidden boundary PASS (conformance 3136895 bytes sha256 `6bb294c3…`; `CARDINALITY_4P_REPLAY_GATE.json`) |
| 5P | `--player-count 5 --smoke-decisions 45` | PASS — 45 decisions; mulligan/priority/target/choose_object; preserved; clean shutdown (`CARDINALITY_5P.json`) |
| 5P@25 | `--player-count 5 --smoke-decisions 25` | Correctly FAILS required-class gate (`missing=['priority']`) — live proof the gate is sensitive, calibrating the 45 target |
| 6P | `--player-count 6 --expect-fail-closed` | FAIL_CLOSED, `engine_launched=false`, no JVM (`CARDINALITY_6P_FAIL_CLOSED.json`) |

Raw lane JSONs are CI-run products (uploaded as workflow artifacts, never
committed); the per-count summaries above plus the sealed JSON companions in
this namespace are the durable evidence. The local `artifacts/xmage-full-game/`
run products were removed after sealing to keep the tree at its tracked state.
