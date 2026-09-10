# RQ-A1 — Argentum Identity Contract Audit

WS48/WS50 lesson applied: `Selection → Native Object → Execution` must stay identity-bound. Classification: `CODE_DERIVED` (static trace).

## 1. Game/session binding

- Engine decisions carry **no** game/session ID. Game scoping lives one layer up: `GameSession` (server) holds one `GameState` under one `stateLock`; `MultiEnvService` env-IDs (gym) scope registries per env.
- Implication for a pilot contract: the transport/session envelope must bind game identity; the engine payload alone does not. The server and gym-service envelopes both do this today (`GameSession` instance; `StepRequest.envId`).

## 2. State-revision binding — ABSENT at engine layer

- Negative result (`DIRECTLY_VERIFIED` by grep): no `stateVersion`/`stateHash`/`revision` field on `GameState` consumed as an action precondition. (`timestamp` = effect ordering; `turnNumber` = progress; `nextEntityId`/`nextRoutingId`/`rng` = allocators, not preconditions.)
- What substitutes for revision binding:
  1. **Exact pending-decision ID equality** for all question answers (`SubmitDecisionHandler`, `ContinuationHandler`, live `executeLiveAction` gate). A response is valid only against the *current* top suspension.
  2. **Session `interactionEpoch`** for all live submissions (browser + AI): UUID rotated on undo/new session; every update captures it under lock; obsolete deliveries return `null` and must be discarded without fallback.
  3. **Per-step gym registries**: integer IDs rebuilt every observation; stale IDs → `ResolvedAction.Unknown` → rejection.
- Assessment: revision-scoped safety is achieved *operationally* (single top-suspension + epoch + per-step registries) rather than *structurally* (no revision token inside the payload). For play actions (cast/activate/pass/attackers/blockers), staleness protection is: single-threaded session lock + epoch freshness + engine revalidation of targeting/cost/combat legality at execution. There is no ABA-style hazard observed (an action legal-now is re-checked now), but there is also no cryptographic/structural staleness proof. A pilot integration should keep the epoch/registry discipline and never cache `LegalAction` lists across observations.

## 3. Active-principal binding — NATIVE_EXPLICIT

- Every `GameAction` carries `playerId: EntityId` (`GameAction.kt:18`); every `PendingDecision` carries `playerId`.
- Engine checks: `SubmitDecisionHandler` rejects wrong-player responses; seat auth via `playerId == actionPlayerId || state.actorFor(actionPlayerId) == playerId` (hotseat/Mindslaver routing; `Concede` excluded).
- Per-viewer delivery: actor-scoped pending decision (others get `OpponentDecisionStatus`); `legalActions` only for the acting seat, empty while a decision is pending (mana-payment window narrows to mana abilities).

## 4. Decision-kind binding — NATIVE_EXPLICIT

- Question subtype and response subtype must correspond; `DecisionValidators` enforces per-kind payload rules against the *current* question's option sets. Mismatched kinds fail closed.
- `DecisionContext(sourceId?, sourceName?, phase, triggeringEntityId?, abilityIdentity?, subjectEntityId?, effectHint?)` carries authoritative native context on every question.

## 5. Native object/action binding

| Primitive | Classification | Detail |
|---|---|---|
| `EntityId` (cards/tokens/players/spells/abilities) | **intrinsic native identity** | `value class EntityId(String)` (`mtg-sdk/.../model/EntityId.kt:15`); live minting state-threaded `e<N>` via `newEntity()` (`GameState.kt:1219`); stable across transitions, persisted, mint-order deterministic from seed+actions. |
| `(EntityId, generation)` / `ObjectRef` | **revision-scoped identity** | `ObjectRef(entityId, generation)` (`state/ObjectRef.kt:8`); `objectIdentities` map + `nextObjectGeneration` on state; generation bumped on real zone changes; `isCurrentObject(ref)` guards "same card, new object" rules. |
| Decision routing token `r<N>` | **revision-scoped identity** (game-local correlation, explicitly not semantic) | `nextRoutingId` persisted; deterministic from snapshot; unique along one timeline; docs forbid interpreting as global/semantic identity. Exact-equality checked at execution. |
| `AbilityId` | **intrinsic native identity with a provenance caveat** | Definition-scoped stable kind identity via `AbilityIdentity(cardDefinitionId, abilityId)` — shared across copies, used for yields/batching. ⚠ Caveat: `AbilityId.generate()` uses a **process-global `AtomicLong`** (`mtg-sdk/.../scripting/AbilityId.kt:15`), not state-threaded (acknowledged in `architecture-principles.md:422`). Deterministic special cases (`classLevelUp(n)`, `intrinsicMana(c)`) exist. Impact: ability IDs may differ across processes/replays for generated IDs — routing/identity for *enumerated* abilities is unaffected (they ride on the enumerated payload), but any future content-addressed replay keying on raw `AbilityId` strings must account for this. Flagged, not disqualifying. |
| `EntityId.generate()` (UUID) | absent from live paths | Exists as helper (`EntityId.kt:23`); live game code uses `newEntity()`. No live-path use found. |
| Gym integer action IDs | **index-based identity** (explicitly unstable) | `ActionRegistry` rebuilt per observation (`:50-64`); contract forbids caching. |
| Mode/option/copy/vote indices | **index-based identity** | Printed-order positions; validated by range + availability at execution. Stable within one question instance only. |
| Targets/cards/sources/distributions | **object-ID-based identity** | `ChosenTarget` variants, `EntityId` lists/maps; membership re-checked at execution. |
| Damage edges | **semantic ID available** | Stable wire id `"$sourceId->$targetId"` echoed back; engine resolves via cached edge (never parses). |
| `DamageEdge` caveat | — | Engine "never parses" the echoed id — trust rests on the cached edge + decision-ID equality, i.e. the response is bound to the question instance, not independently meaningful. Correct design; recorded for precision. |
| GameAction/LegalAction IDs | **absent** | No `actionId`/`requestId` on engine actions. Selection binds by submitting the full native payload (or gym integer handle → registry → native payload within one step). |

## 6. Execution acknowledgement + post-state/event sequence

1. `ProcessedAction(ExecutionResult(state, events, error?, pendingDecision?), undoPolicy)`.
2. Session: seat auth → idempotency → checkpoint invalidation (opponent substantive actions; `PassPriority` preserves) → `process` → on success set state, append replay input, apply undo policy → `Success(state, events)` or `PausedForDecision(state, pendingDecision, events)`.
3. `SubmitDecision` resume: `DecisionSubmittedEvent` first → pop + dispatch → cleanup/untap advances with trigger detection → pre-SBA detection → SBA loop (legend-rule pauses propagate; deferred triggers queue beneath) → post-SBA detection → trigger processing → priority assignment.
4. Broadcast per viewer: masked state + client events + persistent log + legal actions + actor-scoped decision + yields/stops + undo availability + `version` counter + `interactionEpoch`.

## 7. Conceptual stale-action risk — test

Scenario: pilot selects option O from observation at time T, submits after the game moved to T+1.
- **Decisions**: closed. `pending.id` changed (or suspension gone) → exact-equality fails → rejection (engine) or `null` obsolete-delivery (live). Epoch rotation on undo adds a second barrier.
- **Play actions**: no revision token, but submission re-runs full `validate` (targets re-resolved, costs re-checked, combat permissions re-evaluated) under the session lock. Worst case is a *currently-legal action the pilot no longer intends* (e.g. attack declaration after a missed trigger window closed) — standard for intent-based protocols; mitigated by per-observation registries and the prohibition on caching option lists. No evidence of TOCTOU bypass (validation and execution are the same locked call).
- **Gym integer IDs across steps**: closed by registry rebuild + `Unknown` rejection.
- **JSON action ID stability assumption**: correctly absent — there is no JSON action ID to over-trust. Any future pilot-side caching of `LegalAction` payloads across observations would be the risk; contract must forbid it.

## 8. Overall identity verdict

`Selection → Native Object → Execution` is identity-bound for all 38 matrix rows except the two `UNKNOWN`s (starting player, voting — no seam to judge). Binding strengths: native-explicit for game actions and may/concede/commander/mulligan; object-ID-based for selections; exact question-instance binding for all answers; instance-scoped index binding for modes/options/copy; adapter-assembled-but-engine-revalidated for combat declarations. Two caveats carried forward: (a) process-global `AbilityId.generate()` counter (replay-keying hazard, not a legality hazard); (b) in-process Gym full-state exposure (integration must pin the masked observation path).
