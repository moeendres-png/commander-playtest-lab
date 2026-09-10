# RQ-A1 — Argentum Architecture

Trace of the actual source architecture at lock `3f46367`. All paths relative to `/tmp/rq-argentum-src`. Classification: `CODE_DERIVED` unless noted.

## 1. Module topology

```
argentum-engine (Gradle multi-project, Kotlin 2.4.0, JDK 21, Spring Boot 4.1.0 server)
├── mtg-sdk          # card-definition language: pure serializable data bags, no behavior, no engine refs
├── rules-engine     # deterministic Rules Core: GameState + ActionProcessor + enumerators + handlers
├── mtg-sets         # card corpus: :core + 9 era modules (1993-1999 … 2026), each with :tests child
├── ai               # heuristic + LLM consumers of enumerated legal actions (NOT a legality source)
├── gym              # transport-agnostic RL/MCTS env: GameEnvironment, GameGymEnv, MultiEnvService
├── gym-server       # HTTP mapping over MultiEnvService
├── gym-trainer      # self-play / search
├── game-server      # Spring WebSocket sessions, lobbies, decks, replay store, coverage
├── mtg-search       # card search service
├── oracle-assay     # first-party Oracle-text parser → mtg-sdk types (parser, NOT a loader)
├── mtgish-tooling   # incumbent oracle-IR analysis/generation tooling (NOT a runtime dep)
├── e2e-scenarios    # Playwright specs driving real server + real web client
├── manual-scenarios # 1,177 dev-scenario JSON boards
└── web-client       # browser UI (renders server truth)
```

`rules-engine` depends only on `:mtg-sdk` + kotlinx (datetime, serialization-json, coroutines-core). The Rules Core is a genuine standalone library: no Spring, no server, no AI dependency. (`DIRECTLY_VERIFIED` from `rules-engine/build.gradle.kts`.)

## 2. Canonical game-state representation

- Type: `rules-engine/.../state/GameState.kt:45` — `data class GameState`, header: *"Immutable snapshot of the entire game state. All game operations are pure functions: (GameState, Action) -> (GameState, Events)"* (`:36-40`).
- Model: entity-component hybrid. `entities: Map<EntityId, ComponentContainer>`, `zones: Map<ZoneKey, List<EntityId>>`, `stack: List<EntityId>`, `continuationStack: List<ContinuationFrame>`, floating effects, delayed triggers, granted abilities, `rng: GameRng`, `nextEntityId`, `nextRoutingId`, `objectIdentities`, `yieldsByPlayer`, turn/phase/step/priority (`activePlayerId`, `priorityPlayerId`, `apnapOrder`, `turnOrder`, `teams`, `attackMode`), `commanderDamage`, timestamps. (`GameState.kt:45-418`.)
- Mutation discipline: copy-on-write everywhere — `withEntity` (`:452`), `withoutEntity` (`:458`), `addToZone` (`:548`), `insertIntoZone` (`:573`), `reorderZone` (`:635`), `removeFromZone`/`moveToZone` (`:644/:675`), `pushToStack` (`:1045`), `tick` (`:1201`). No persistent-collection library; stdlib immutable `Map`/`List` copies.
- Derived view: `projectedState: ProjectedState by lazy` (`:425`) — Rule 613 projection, evaluated once per instance, not serialized.

## 3. Transition model

- Entry: `ActionProcessor.process(state: GameState, action: GameAction): ProcessedAction` (`core/ActionProcessor.kt:74`); class is *"stateless — a pure function"* (`:34-35`).
- Output: `ProcessedAction(result: ExecutionResult, undoPolicy: UndoCheckpointAction)` (`:23`); `ExecutionResult(state, events: List<GameEvent>, error: String?, pendingDecision: PendingDecision?, ...)` (`core/ExecutionResult.kt:22`).
- Pipeline: `validateBasics` (game-over, known player, `:113-125`) → `ActionHandlerRegistry.validate/execute` (`KClass` dispatch, `handlers/actions/ActionHandlerRegistry.kt:46-60`) → `UndoPolicyComputer` (`ActionProcessor.kt:102-106`).
- Atomicity: top-level errors return the entry state with only the message; intermediate states/events discarded (`:94-95`).
- Pause: `ExecutionResult.propagatePause` carries the state's single authoritative suspension; never allocates a second question (`ExecutionResult.kt:66`).

## 4. Legal-action producer (authoritative)

- Coordinator: `LegalActionEnumerator.enumerate(state, playerId, mode = FULL): List<LegalAction>` (`legalactions/LegalActionEnumerator.kt:64`), fanning out to ~22 `ActionEnumerator`s (pass, play-land, 6+ cast variants incl. morph/sneak/emerge/web-slinging/cycling/plot/foretell/suspend/cast-from-zone, mana abilities, turn-face-up, unlock-room, activated, crew, saddle, graveyard/hand zone abilities, command-zone abilities) plus a short-circuiting `CombatEnumerator` on declaration steps (`:31-53,82-84`).
- `LegalAction(action: GameAction, actionType: String, description: String, affordable = true, …)` (`legalactions/LegalAction.kt:14`) — a template native action plus ~30 metadata fields (valid targets, target requirements, attacker/blocker candidate lists, mana-cost strings, X bounds, convoke/delve/improvise/waterbend/harmonize payloads, modal enumeration). Unaffordable actions included but flagged (`:62`).
- `EnumerationMode.FULL` vs `ACTIONS_ONLY` (skips auto-tap preview for simulation/MCTS).
- Server DTO is a separate enrichment: `LegalActionEnricher.enrich(...) → List<LegalActionInfo>` (`view/LegalActionEnricher.kt:30`).

## 5. Action submission path

- Same `ActionProcessor.process` boundary for everything: play actions, `SubmitDecision(playerId, response)`, Gym steps, server ingress.
- Decision validation (`handlers/actions/decision/SubmitDecisionHandler.kt:31-44`): pending exists → acting player owns it → exact `pending.id == response.decisionId` → `DecisionValidators.validate` (per-kind membership/range/permutation checks, `DecisionValidators.kt:63`).
- Resume (`handlers/ContinuationHandler.kt:78-90`): re-check suspension ID, pop, dispatch `AnswerContinuation` via resumer registry.
- Server ingress (`game-server/.../session/GameSession.kt:885`): one `synchronized(stateLock)` funnel — seat auth (`actorFor` hotseat/Mindslaver routing, `:895`), `messageId` idempotency (`:900-905`), `process` (`:920`), undo-policy application (`:928`), replay append on accept only (`:931`). Live transports add epoch freshness (`executeLiveAction`, `:864-867`); browser epoch-prefixed IDs decoded in `executeClientAction` (`:816`); AI raw IDs in `executeAiAction` (`:849`).

## 6. Decision-request representation

- Engine: `PendingDecision(id, playerId, prompt, context)` sealed interface, ~19 question types (`ChooseTargets`, `SelectCards`, `YesNo`, `BatchYesNo`, `ChooseMode`, `ChooseColor`, `ChooseNumber`, `Distribute`, `OrderObjects`, `SplitPiles`, `ChooseOption`, `ChooseReplacement`, `BudgetModal`, `AssignDamage`, `SearchLibrary`, `ReorderLibrary`, `SelectManaSources`, `CombatResolution`) + ~16 typed `DecisionResponse` subtypes (`core/PendingDecision.kt`, `core/CombatResolution.kt:137`).
- Suspension: `Suspension(question, answer)` on `GameState.continuationStack` (`core/Suspension.kt:9`); `pendingDecision` derives from the top frame (`GameState.kt:1272`); overwrite refused (`:1279-1281`); allocation via `suspendForDecision` with `require(decision.id == id)` (`Suspension.kt:22`).
- Wire: browser gets epoch-prefixed opaque IDs + enriched options; in-process AI gets raw engine IDs; Gym folds simple decisions into the per-step integer ID space and routes complex ones via `submitDecision` (`requiresStructuredResponse`).

## 7. Event representation

- `GameEvent` sealed interface — *"trusted engine events, not player-safe transport objects… must project them through ClientEventTransformer"* (`core/GameEvent.kt:16-23`). Examples: `ZoneChangeEvent` (with LKI `EntitySnapshot` + `ObjectRef`s), `LifeChangedEvent`, `DamageDealtEvent`, `SpellCastEvent`, `AbilityActivated/TriggeredEvent`, `DecisionRequested/SubmittedEvent` (`:1703-1715`); full registration in `core/Serialization.kt:55-167`.
- Emission discipline (`architecture-principles.md:669-757`): one typed event per observable mutation (mutation+event in one atom); `TriggerDetector.detectTriggers(state, events)` consumes the batch.
- Transport: `ClientEventTransformer.transform(events, playerId)` per viewer; per-player persistent logs (noisy tap/untap/mana filtered).

## 8. Observation paths

| Consumer | What it receives | Masking |
|---|---|---|
| Browser | `ClientGameState` via `ClientStateTransformer` (Rule 613 projected, per-viewer) + `clientEvents` + enriched `legalActions` + actor-scoped pending decision + `opponentDecisionStatus` for others | Server-side redaction (`Visibility` per-zone checks + individually revealed cards + opaque library slots + face-down names). Never raw `GameState`. |
| In-process AI | Unmasked authoritative state + `LegalActionInfo` list (same protocol, unmasked seat) | Explicitly unmasked (`README.md:176`, `AiPlayerController`); acceptable as engine-internal consumer, NOT as external pilot evidence. |
| LLM AI | Masked state over the standard protocol | Same as browser. |
| Gym managed/remote | `TrainingObservation` (masked zones, known-subset cards, true sizes, `stateDigest`, per-step `legalActions`) | `ObservationBuilder` delegates to engine `Visibility`; `revealAll=true` debug-only. |
| Gym in-process (`GameEnvironment.StepResult.state`) | **Full `GameState`** | ⚠ Architecture-significant caveat: direct `GameEnvironment` exposes full state; only the managed/remote observation is masked. In-process callers must use `GameGymEnv.observe()`. |

## 9. RNG entry points

- Single abstraction: `GameRng(state: Long)` SplitMix64 (`mtg-sdk/.../model/GameRng.kt:23`), pure/immutable/serializable, `split()` sub-streams.
- Owned by `GameState.rng` (`GameState.kt:366`), threaded via `nextRandom` (`:1210`); identical seeds + actions → byte-identical state (design intent, not runtime-verified here).
- Seeding: `GameConfig.seed: Long? = null` (`core/GameInitializer.kt:91`); null → `System.nanoTime()` at the single sanctioned boundary (`:161`), always recorded in `InitializationResult.seed` (`:106`).
- Consumers: turn order, shuffles, mulligan/hand-smoothing, coin flips, random discard/costs. Out of scope (pre-game): booster/cube construction via `kotlin.random.Random`.

## 10. Replay / snapshot / restore facilities

- No generic engine snapshot/clone API (`copy()` structural copies are the clone mechanism).
- Serialization: `GameState` kotlinx-serializable with legacy migration (`GameStateSerializer`, `LegacyGameStateSerializer`); full polymorphic registry (`core/Serialization.kt`).
- Server `CompactReplay` (input journal, not snapshots): setup + ordered `GameAction`s + yields + engineVersion + pinned card JSON + checkpoints every 20 (cap 25k actions); `ReplayReconstructor` re-folds; `ReplayFidelity EXACT/UNVERIFIED/DIVERGED`.
- Gym: O(1) in-process reference slots (`SnapshotCodec`); byte-blob variant reserved but absent.
- Undo: engine-computed `UndoCheckpointAction` applied to a retained `GameState` reference in the session.

## 11. Server / Gym / AI coupling summary

- `GameSession`: in-memory thin wrapper over `ActionProcessor` (volatile state + session lock + per-client delta cache); Spring WebSocket transport; optional Redis persistence (replay data explicitly excluded from the blob).
- `gym`: transport-agnostic; `GameEnvironment` (single) + `MultiEnvService` (pooled, batch stepping); `gym-server` maps HTTP onto it.
- `ai/`: strict consumer — `GameSimulator.simulate` + `enumerator.enumerate(ACTIONS_ONLY)` → `Strategist/AIPlayer.chooseAction` → submit. Heuristic fallback synthesis (empty combat declarations, trivial decisions) always passes through engine validation. No AI-side legality production.

## 12. Pilot-seam verdict (architecture)

A Commander Simulator pilot can in principle receive only authoritative legal options (`LegalAction` templates + `PendingDecision` questions with engine-enumerated option sets) and submit one selected option (`GameAction` / `SubmitDecision`) without reconstructing legality — **with three carved exceptions**:

1. **Combat declarations are template + candidate-list**: `DeclareAttackers/DeclareBlockers` enumerate empty with `validAttackers/validAttackTargets/validBlockers`; the pilot (or a thin adapter) fills the map from advertised candidates. Engine revalidates. Flagged `ADAPTER_REQUIRED`, not a second legality — the candidate lists are authoritative; the assembly step is mechanical.
2. **X/mode/target completion on cast/activation variants**: the variant choice is native, but X values, mode indices, and target selections complete through validated channels bounded by engine-advertised sets. Mechanical, engine-checked.
3. **In-process Gym full-state exposure**: external pilots must consume `GameGymEnv.observe()` / managed observations, never `GameEnvironment.StepResult.state` directly. Integration contract must pin the masked path.

No production-reachable code path was found in which pilot/server/Gym/AI fabricates legality that the engine then trusts: every submission funnels through `validate → execute`, and decision responses are checked against current option sets. (Static finding, `CODE_DERIVED`; adversarial/negative testing not performed.)
