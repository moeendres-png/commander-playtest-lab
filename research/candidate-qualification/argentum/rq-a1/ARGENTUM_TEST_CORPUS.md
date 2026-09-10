# RQ-A1 — Argentum Test Corpus

Inventory at lock `3f46367` (counts by `find … -name "*.kt" | wc -l`, i.e. file counts, not case counts) plus the RQ-A1 execution record. A green suite is not Full-Rules qualification; each run below records exactly what it establishes.

## 1. Inventory

| Suite | Files | Content |
|---|---|---|
| `rules-engine/src/test` | **587** (586 `*Test.kt`) | Engine behavior: `core/event/handlers/hidden/hygiene/legalactions/limited/loader/mana/mechanics/{combat,layers,mana,sba,stack}/multiplayer/predicates/registry/scenarios/state/targeting/triggers/view`; harness `testFixtures` (`ScenarioTestBase`, `GameTestDriver`, `TestCards`); `test/resources/suspension-traces/` + `legacy-suspensions/` JSON |
| `rules-engine` multiplayer subset | **19** | `AgateBladeAssassinMultiplayerTest`, `AttackModeTest`, `CommanderPodTest`, `DefendingPlayerAttackRestrictionTest`, `LeaveTheGameTest`, `MultiDefenderCombatTest`, `MultiplayerMulliganTest`, `MultiplayerSmokeTest`, `OpponentDeciderChoiceTest`, `ReplacementTeamAwarenessTest`, `TeamVsTeamTest`, `ThoughtStalkerWarlockConditionTest`, `TwoHeadedGiant{Combat,SecondHeadTurn,Setup,SharedLife,SharedTurn,TeamLoss,TeamPriority}Test` |
| `rules-engine` Commander subset | **8+** | `core/CommanderSetupTest`, `mana/CommanderTaxTest`, `mechanics/sba/{CommanderDamageLossCheckTest,CommanderZoneChoiceCheckTest}`, `event/CommandZoneTriggerDetectionTest`, `handlers/effects/{CommanderZoneRedirectTest,CommanderZoneMarkerStripTest}`, `multiplayer/CommanderPodTest`, `scenarios/LiminalHoldCommanderTest` |
| `mtg-sets/<era>/tests` | **3,528** (≈3,519 scenario classes + 9 `ProjectConfig`) | Per-card/per-mechanic scenario tests, era-split (242/159/430/188/349/403/716/591/450) |
| `mtg-sets/src/test` | **28** classes + ~195 snapshot JSONs | Catalog/discovery/snapshot/lint/facade whole-corpus gates |
| `game-server/src/test` | **85** | `session`(14) `lobby`(9) `replay`(7) `deck`(6) `scenarios`(5) `ai`(5) `auth`(4) `tournament`(3) `scenario`(3) `persistence`(3) + `GameMaskingTest`, `GameFlowTest`, `FreeForAllLobbyTest`, `QuickGameLobbyCommanderAiTest`, coverage tests |
| `gym` / `gym-server` / `gym-trainer` | 9 / 2 / 5 | Contract/visibility/projected-state observations, env step loops, deckbuild env, multi-env pool, HTTP controller, self-play + MCTS/search resolvers |
| `e2e-scenarios/tests` | 70 files / **68** specs | Playwright driving **real engine games through real server + real web client** (scenario API → two browser contexts → clicks/assertions); `general/` (15: ai-match, combat, damage-floaters, draft/sealed, gift, paused-spell, trample…) + per-set dirs |
| `manual-scenarios` | **1,177** JSON | Same `ScenarioRequest` shape for dev-scenario endpoints/UI reproduction (`bugs/` 14, `cards/a…z/` bulk, `mechanics/`, `sets/`, `ui/`) |

No `unit/` vs `integration/` split in `rules-engine/src/test`; division is by package. Commander/multiplayer card-level scenario files: none found (engine-level coverage only).

## 2. RQ-A1 execution record (existing tests, exact lock, read-only)

Strategy: start narrow (highest probative value per minute: Commander pod + multiplayer core), broaden only as needed. Full-suite runs were deliberately not attempted (tens of thousands of tests across 9 era modules; cold Gradle cache).

### Run RQ-A1-T1 — `:rules-engine` multiplayer + Commander tests

- Command: `./gradlew :rules-engine:test --tests "com.wingedsheep.engine.multiplayer.*" --tests "com.wingedsheep.engine.core.CommanderSetupTest" --tests "com.wingedsheep.engine.mana.CommanderTaxTest" --console=plain` (working dir `/tmp/rq-argentum-src`, Gradle 9.6.1, JDK 21.0.12, cold cache; 9m18s, 44 tasks)
- Source lock: Argentum `3f46367` / tree `2adf51c` (verified clean before and after; only gitignored `build/` products created)
- Result: **BUILD SUCCESSFUL — 21 test classes, 149 tests, 0 failures, 0 errors, 0 skipped** (JUnit XML under `rules-engine/build/test-results/test/`, counted in-session)
- Establishes (`DIRECTLY_VERIFIED`, narrow): multiplayer turn/combat/elimination/team-priority/Commander-setup/tax paths execute green at the lock in this environment — runtime-exercised presence, not rules-validated, not coverage beyond the exercised cases

### Run RQ-A1-T2 — `:rules-engine` SBA + trigger-detection + combat/legend/simultaneity scenarios

- Command: `./gradlew :rules-engine:test --tests "com.wingedsheep.engine.mechanics.sba.*" --tests "com.wingedsheep.engine.event.*" --tests "com.wingedsheep.engine.scenarios.CombatDamageAssignmentTest" --tests "com.wingedsheep.engine.scenarios.LegendRuleTest" --tests "com.wingedsheep.engine.scenarios.LethalDamageSbaSimultaneityTest" --console=plain` (warm cache; 35s)
- Source lock: unchanged (`3f46367`; tree verified clean after run)
- Result: **BUILD SUCCESSFUL — 15 test classes, 105 tests, 0 failures, 0 errors, 0 skipped** (JUnit XML; note: Gradle rewrites `test-results/test` per run, so T1's 149 and T2's 105 were counted separately in-session, not cumulatively from disk)
- Establishes (`DIRECTLY_VERIFIED`, narrow): SBA checks (incl. Commander damage-loss/zone-choice, battle protector, phantom copies), trigger detection/resolution, combat damage assignment, legend rule, lethal-damage simultaneity execute green at the lock — runtime-exercised presence, not rules-validated
- Combined RQ-A1 runtime evidence: **254 tests / 36 classes green, 0 failures** across the two narrow scopes. Full-suite status remains NOT_RUN (see U24).

## 3. Reading the results (rules, fixed before running)

- A green run establishes: the exercised code paths execute at the lock in this environment (runtime-exercised presence). It does NOT establish Rules correctness, official-rules validation, or coverage beyond the exercised cases.
- A red run is diagnostic evidence (failure class recorded; candidate not repaired per hard gates).
- `test count != Rules correctness`; `green tests != Full-Rules qualification`.
