# WS215 INPUT_AUTHORITY_MATRIX

Source lock: Lab `592f23c9` (tree `33e8cef4`, branch
`ws215/xmage-variable-player-multicardinality-20260915`); production XMage
`db134b9737` (tree `4c7cae47`); WS214 `c044d40f6` TEST-ONLY.
`ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.

Terminal WS213 inputs preserved (invalidated only by fresh impacted evidence):

| # | Input | Authority / location | Standing entering WS215 |
|---|-------|----------------------|-------------------------|
| 1 | `RULES_SEED_BINDING = PASS`, `REQUIRE_EXPLICIT_SEED=true`, truthful per-run `seed_supported` | WS213 `RULES_SEED_BINDING.md`/`.json`; `XmageFullGameSession` ctor (`setRulesSeed`+`setRequireExplicitSeed`); WS212 `GameImpl` | Preserved; must hold for every player count |
| 2 | `WS204_GENERIC_ACTION_BATTERY = 105/105` | WS213 `GENERIC_ACTION_REGRESSION.md`; `mvn verify` engine-bridge | Preserved unless bridge projection changes behavior (WS215 does not touch projection) |
| 3 | D1–D5 PASS, `D5_TWIN_EQUALITY = PASS` | WS213 `D1_D5.md`, `D5_ADJUDICATION.md` | Preserved; D5 twin method reused per-count |
| 4 | `E02_COMBAT = PASS (runtime mechanism)` | WS213 `COMBAT_E02.md`; WS206 trample path | Mechanism retained; multiplayer defender binding re-exercised at 4P/5P |
| 5 | `G04_CONCESSION = PASS (runtime mechanism)` | WS213 `CONCESSION_G04.md`; WS211 `Game.canConcede`/`concede` | Mechanism retained; exercised in 3P/5P, not only 4P |
| 6 | `HIDDEN_INFORMATION = PASS` | WS213 `HIDDEN_INFORMATION.md` (8709 rows/0 violations) | Impact-adjudicated against N principals; re-proven per count |
| 7 | `WS207_SETUP_CONSUMPTION = PASS` | WS213 `WS207_SETUP_CONSUMPTION.md` | Retained; setups are 4P-scoped inputs, untouched by cardinality change |
| 8 | `I01_AUTHORITY_STATUS = ADJUDICATED_NO_GATE` | WS213 `I01_AUTHORITY_ADJUDICATION.md` | Retained; fixture untouched |
| 9 | `PLAYER_COUNT_4P = PASS`; 2P/3P/5P `NOT_SUPPORTED` (fail-closed `FULL_GAME_REQUIRES_EXACTLY_FOUR_PLAYERS`) | WS213 `PLAYER_COUNT_IMPACT.md`; `XmageFullGamePlayerCountTest` 3/3 | 4P must be freshly regressed; 2P/3P/5P gates replaced by WS215 contract |
| 10 | `SEMANTIC_REPLAY_STATUS = PARTIAL` | WS213 `SEMANTIC_REPLAY_IMPACT.md` | Impact-adjudicated only; no Replay v1 in WS215 |
| 11 | `BEHAVIOR_CREDIT_CHANGE (WS213) = +1` (H01-NO_HUMILITY) | WS213 `BEHAVIOR_CREDIT_LEDGER.md` | `GLOBAL_BEHAVIOR_CREDIT_CHANGE (WS215) = 0`; no behavior promotion |
| 12 | `FULL107 = NOT_RUN` | WS213 `VALIDATION.md` | Not claimed by WS215 |
| 13 | Common Fixture Manifest denominator | `qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json`, sha256 `e7f34ea4…ca3bd4`, **135 fixtures**: player_count 4, multiplayer_commander 36, actual_card 29, hidden_information 20, pilot_boundary 17, micro_rules 17, pilot_boundary_negative 7, replay_rng 5 | WS215 scope = 40 (4 player_count + 36 multiplayer_commander); remaining 95 impact-adjudicated |
| 14 | `CommanderFreeForAll` N-player construction | Reference root `Mage.Server.Plugins/…/CommanderFreeForAll.java` (`setNumPlayers`), `GameCommanderImpl` (`startingPlayerSkipsDraw=true` default, overridden `false` in FreeForAll `init`), London mulligan `getMulligan(1)` | Engine owns N-player semantics; Lab only passes count through |
| 15 | Non-full-game lane precedent | `XmageGameManager.java:198` (`INVALID_PLAYER_COUNT: expected 2 to 5 players`), `XmageProvider:62` (`max_players=5`) | Style precedent only; full-game lane keeps its own contract |
| 16 | WS214 harness authority | `c044d40f6` TEST-ONLY | Not consumed by production paths; WS215 probes do not use TestPlayer |

Machine companion: `INPUT_AUTHORITY_MATRIX.json`.
