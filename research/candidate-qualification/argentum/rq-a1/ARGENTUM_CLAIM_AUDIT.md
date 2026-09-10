# RQ-A1 — Argentum Claim Audit

All claims re-derived from the exact source lock (`3f46367`). README/docs statements are claims until tied to source or runtime evidence. Verdicts: `CONFIRMED` (source- or runtime-backed), `DOWNGRADED` (partially true, narrower than claimed), `REJECTED` (contradicted), `UNKNOWN` (not determinable in this pass).

## Determinism / purity claims

| # | Claim (provenance) | Verdict | Basis |
|---|---|---|---|
| C1 | Deterministic engine (`README.md:19-23,209-210`) | CONFIRMED as architecture (`CODE_DERIVED`); runtime determinism `UNKNOWN` here | `GameState` immutable data class + `ActionProcessor.process(state, action)` pure boundary (`GameState.kt:36-40`, `ActionProcessor.kt:34-35,74`); state-threaded `GameRng`, `newEntity`, `newRoutingId`. No runtime byte-identity check executed in RQ-A1. |
| C2 | Immutable/pure transitions (`architecture-principles.md:321-355,383-391`) | CONFIRMED (`CODE_DERIVED`) | Copy-on-write throughout (`withEntity`, `addToZone`, `pushToStack`, `tick`); error paths return entry state (`ActionProcessor.kt:94-95`). |
| C3 | Standalone rules-engine library, no server deps (`README.md:209-210`) | CONFIRMED (`CODE_DERIVED`) | `rules-engine/build.gradle.kts` deps: only `:mtg-sdk` + kotlinx (datetime/serialization/coroutines). No Spring/server dep. |
| C4 | `legalActions` authoritative enumeration (`data-contracts.md:7-8`, `README.md:244-251`) | CONFIRMED (`CODE_DERIVED`) | `LegalActionEnumerator.enumerate(state, playerId, mode)` + ~22 `ActionEnumerator`s (`LegalActionEnumerator.kt:31-64`); `LegalAction` wraps template `GameAction` + targeting/cost/combat metadata (`LegalAction.kt:14`). |
| C5 | Gym `reset/step/observe/legalActions` (`README.md:244-251`, `gym/README.md`) | CONFIRMED (`CODE_DERIVED`) | `GameEnvironment.reset/step/legalActions/fork/restore`, `GameGymEnv.observe/step/submitDecision`, `MultiEnvService` batch ops; `TrainingObservation` contract + `SchemaHash.CURRENT`. |
| C6 | Server/player observation masking (`data-contracts.md`, `Visibility.kt` KDoc) | CONFIRMED as mechanism (`CODE_DERIVED`); no-leak property `UNKNOWN` | Single engine `Visibility` authority shared by client projection, AI determinization, Gym observations; per-viewer `ClientStateTransformer`; `DecisionEnricher`; `ClientEventTransformer`. No live-traffic leak test in RQ-A1. |

## Multiplayer / format claims

| # | Claim (provenance) | Verdict | Basis |
|---|---|---|---|
| C7 | 2–6-player free-for-all (`README.md:131-140`, CR 806) | DOWNGRADED | FFA 2–4 players evidenced in engine tests (`MultiplayerSmokeTest`, `CommanderPodTest`, `LeaveTheGameTest`, `AttackModeTest`); code imposes no max (`players.size >= 2` only). **No 5- or 6-seat runtime test found**; "six-player FFA" rests on a `Format.Commander` KDoc comment only. Lobby adds `TOURNAMENT/FREE_FOR_ALL/TWO_HEADED_GIANT/TEAM_VS_TEAM` modes (config surface, not engine proof). |
| C8 | Commander support (`Format.Commander`, lobby presets) | DOWNGRADED (in-engine core present; variants absent) | In-engine Commander is real: `Format.Commander` (21-damage default, 40 life), `GameInitializer` single-commander setup → `Zone.COMMAND`, `CommanderComponent` + tax (`CostCalculator.calculateCommanderTax`), 903.9a choice SBA (`CommanderZoneChoiceCheck`), per-commander damage loss (`CommanderDamageLossCheck`), `CommanderPodTest` (4-seat). BUT: partner/background/companion absent (explicit "Phase 4" comments; validator "not yet supported"); in-engine color-identity/singleton enforcement absent (validator-only); Brawl/Pod presets use non-canonical deck sizes (60) — lobby convenience, not rules evidence. |
| C9 | Stack / priority / mana-payment / combat / SBAs / triggers / replacement / layers / copy / control (`README.md:212-220`, `RULES.md`) | CONFIRMED as presence (`CODE_DERIVED`); correctness `UNKNOWN` (no Rules adjudication) | Each has implementation + engine tests (see Rules Maturity file, 23-row table). Explicit fail-closed gaps quoted (battle/loyalty excess damage, PayOrSuffer reveal/variable payments, ChainSpell cost types, split-half behold/kicker/convoke, improvise+{X}, opponent-permanent nonstandard costs). `RULES.md` is evidence-based by its own stated policy (DSL primitive + wired path + card/scenario), but RQ-A1 did not re-verify each bullet. |

## Decision-seam claims

| # | Claim (provenance) | Verdict | Basis |
|---|---|---|---|
| C10 | Clients/AI receive engine-computed options; submit intent; server validates (`data-contracts.md:7-8,16-96`) | CONFIRMED (`CODE_DERIVED`) | `LegalActionEnricher` per acting seat; `SubmitDecisionHandler` (player + decision-ID + payload validation); `ActionHandlerRegistry` validate-then-execute; `GameSession` seat auth + epoch + message-id idempotency. |
| C11 | `docs/engine-server-interface.md` as current contract | REJECTED (stale) | Describes `GameRequest`/`EngineResult`/`choiceIndex` API; current code uses `GameAction`/`ExecutionResult`/`typed DecisionResponse`. High-level shape roughly right; field-level use forbidden. `PlayLand`-face and `alternativeCostType` echo rules inside it still hold in current code. |
| C12 | Stable action IDs for selection | REJECTED as stated; replaced by narrower truth | Engine `GameAction`/`LegalAction` carry **no** action ID. Identity = native payload + pending-decision `r<N>` routing token + session `interactionEpoch`. Gym per-step integer IDs explicitly unstable across steps. See Identity file. |

## RNG / replay / snapshot claims

| # | Claim (provenance) | Verdict | Basis |
|---|---|---|---|
| C13 | RNG injection/control (`GameConfig.seed`, `GameRng`) | CONFIRMED as mechanism (`CODE_DERIVED`) | `GameRng` SplitMix64 single-`Long`, state-threaded (`GameState.rng`, `nextRandom`); `GameInitializer` null-seed→entropy boundary + recorded seed; sub-streams via `split()`. Dice/coin/shuffle/discard/random-startup consume it. Booster/cube construction uses `kotlin.random.Random` (pre-game product, out of scope). RNG statistics / consumption-order stability NOT runtime-verified here. |
| C14 | Replay (`CompactReplay`, `architecture-principles.md:393-398`) | CONFIRMED as mechanism (`CODE_DERIVED`); fidelity `UNKNOWN` | `CompactReplay` = setup + ordered `GameAction` inputs + yields + engineVersion + pinned card JSON + checkpoints + `ReplayFidelity EXACT/UNVERIFIED/DIVERGED`; `ReplayReconstructor` re-folds via `ActionProcessor`. No replay round-trip executed in RQ-A1. Seed-only replay sufficiency: plausible (state-threaded counters reproduce routing IDs; `withDecisionId` rebinds historical IDs) but NOT proven here. |
| C15 | Snapshot/restore | DOWNGRADED | No generic engine snapshot API. What exists: kotlinx-serialization of `GameState` (+ legacy migration), Gym O(1) in-process reference slots (`SnapshotCodec`), server undo = retained `GameState` reference + `UndoPolicyComputer`, optional Redis session blob (replay data explicitly excluded). "Snapshot" in-engine means LKI `EntitySnapshot`. Adequate primitives for a WS51-style restore design, but not a restore feature. |
| C16 | Elimination / standings / rematch (`README.md:131-140`) | CONFIRMED for elimination (`CODE_DERIVED`); standings/rematch not traced | `PlayerLeavesGameProcessor` (CR 800.4a–c/e–h) + `LeaveTheGameTest` + `CommanderPodTest` elimination + `GameEndCheck`. Two documented simplifications (LTB triggers off mass removals; static-ability exile of leaver-controlled objects). |

## Card-coverage claims

| # | Claim (provenance) | Verdict | Basis |
|---|---|---|---|
| C17 | "N implemented cards" / set-completion % (`card-implementation-progress.html`, `scripts/card-status`, server coverage) | DOWNGRADED — "implemented" means *declared*, not *behavior-proven* | "Implemented" = a `val X = card("X"){...}` / `basicLand(...)` declaration discovered by `CardDiscovery` (13,919 distinct names; 13,619 canonical files + 5,157 reprint rows over 18,345 card files). % = declared-names ∩ Scryfall-canonical over booster cards. Behavior proof is separate: ~3,519 mtg-sets scenario test files + 587 engine test files + e2e/manual scenarios. 2,227 files carry the `GENERATED by mtgish` draft header (review + passing scenario test required by house rule). See Real-Card file. |
| C18 | Assay parser output ≈ executable behavior (`docs/oracle-assay.md`) | REJECTED as implication; parser itself CONFIRMED (`CODE_DERIVED`) | Docs explicitly: "deliberately not a runtime loader… a generated card is a draft until a human reviews it and a scenario test passes." Parsing ≠ behavior. |

## Test-corpus claims

| # | Claim (provenance) | Verdict | Basis |
|---|---|---|---|
| C19 | Unit/integration/E2E coverage (`e2e-scenarios`, `manual-scenarios`, era `tests`) | CONFIRMED as presence (`CODE_DERIVED` + test run, see Test Corpus file) | 587 engine test files (incl. 19 multiplayer files, Commander pod/tax/SBA tests), 3,528 era-test files, 85 server, 9+2+5 gym-family, 68 Playwright specs driving real server+client, 1,177 manual scenario JSONs. Green ≠ qualification (recorded per-run, not inherited). |

## Summary counts

- CONFIRMED: 9 (C1–C6 architecture/seam, C13–C14 mechanisms, C16-elimination, C19 presence)
- DOWNGRADED: 4 (C7 players, C8 Commander, C15 snapshot, C17 card counts)
- REJECTED: 3 (C11 stale doc, C12 action IDs, C18 parser≈behavior)
- No claim accepted as `EXTERNALLY_RULE_VALIDATED`; none promoted to Qualification PASS.
