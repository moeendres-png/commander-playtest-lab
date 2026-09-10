# RQ-A1 — Argentum RNG / Replay (plus Snapshot / Restore)

Classification: `CODE_DERIVED` (static trace; no statistical or round-trip runtime verification in RQ-A1).

## 1. Deterministic state transition — YES (architecture)

Immutable `GameState` + pure `ActionProcessor.process`. Identical inputs → identical outputs by construction (modulo the `AbilityId` counter caveat in §5). "Pure reducer" alone is not claimed as replay proof (see §4).

## 2. Controlled Rules RNG — YES (mechanism)

- Owner: `GameState.rng: GameRng` (`GameState.kt:366`).
- Abstraction: `GameRng(state: Long)` — SplitMix64, pure/immutable/serializable, `nextLong/nextInt/nextBoolean/nextDouble/shuffle/pick/split` each returning `(value, nextRng)` (`mtg-sdk/.../model/GameRng.kt:23-100`).
- Threading: `GameState.nextRandom(draw)` (`GameState.kt:1210`); callers must thread the returned state onward (documented like `tick`).
- Seed source: `GameConfig.seed: Long?` (`core/GameInitializer.kt:91`); `null` → `System.nanoTime()` at the single sanctioned boundary (`:161`); resolved seed always recorded (`InitializationResult.seed`, `:106`).
- Streams: `split()` sub-streams; routing IDs (`r<N>`) and entity IDs (`e<N>`) are independent state-threaded counters (not RNG draws), so rules randomness never contends with identity allocation.
- Consumers (traced): turn order, library shuffles, mulligan/hand-smoothing, coin flips (`CoinFlipService.kt:119`), random discard/costs (`CostPaymentService.kt:590`, `CostHandler.kt:770`, `MulliganHandler.kt:124`).
- AI randomness: simulation/rollout policies consume their own randomness outside the game RNG (harness-side; production-reachable only as *choices among legal options*, never as rules outcomes). No unseeded harness randomness in rules paths found.
- Out of scope (pre-game product): booster/cube construction uses `kotlin.random.Random` (`limited/BoosterGenerator.kt`, `limited/CubeDealer.kt`) — not in-game randomness.

## 3. Reproducible game re-execution — MECHANISM PRESENT, fidelity UNKNOWN

- `CompactReplay(version, gameId, players, startedAt/endedAt, setup: ReplaySetup, actions: List<GameAction>, yields, engineVersion, pinnedCards, checkpoints, truncated)` (`game-server/.../replay/CompactReplay.kt:28`).
- Design: whole game = setup + ordered inputs; state-threaded `e…` IDs make re-simulation reproducible; `ReplaySetup` mirrors `GameConfig` + recorded seed; `ReplayReconstructor` re-folds through `ActionProcessor` and re-runs `SpectatorStateBuilder`/diff (`data-contracts.md:637-644`).
- Honesty machinery (notable): replays **pin card definitions** + checkpoints + archived frames *because cards-as-data can rewrite re-simulation* (`architecture-principles.md:393-398`); `ReplayFidelity EXACT/UNVERIFIED/DIVERGED`; `MAX_RECORDED_ACTIONS = 25_000`, checkpoint every 20; live log is a `CopyOnWriteArrayList` appended under the session lock; only canonical engine actions recorded; Redis session blob explicitly carries no replay data.
- Not executed here: no replay round-trip, no fidelity verdict. `EXACT` is a claim until a round-trip test says otherwise.

## 4. Semantic Replay suitability — PROMISING, NOT PROVEN

Seed-only replay sufficiency analysis (the four conditions):

1. Deterministic transition — yes by construction (§1).
2. Controlled Rules RNG — yes (§2); seed recorded at init.
3. Stable consumption ordering — designed (state-threaded counters; single-lock session append; `triggersAlreadyProcessed` guards), not stress-verified here.
4. Complete input capture — designed (canonical actions + yields + `SubmitDecision` responses + pinned cards + checkpoints), not round-trip-verified here.

Verdict: Argentum's replay design is *input-journal + pinned-definitions + checkpoints*, which is the correct shape for Semantic Replay, and its deterministic-routing-ID design (`withDecisionId` rebinding for historical IDs) shows the failure modes were considered. But "deterministic architecture = Semantic Replay" is forbidden reasoning: suitability stays `UNKNOWN` until a seed+input round-trip demonstration exists. That demonstration is small, well-defined work (reconstruct N games from `CompactReplay`, compare digests) and is recommended as the first runtime discriminator inside qualification — not as a pre-qualification gate.

## 5. Known hazard: `AbilityId` process-global counter

`AbilityId.generate()` uses a process-global `AtomicLong` (`mtg-sdk/.../scripting/AbilityId.kt:15`), acknowledged in `architecture-principles.md:422`. Live entity IDs are state-threaded, but generated ability IDs may differ across processes for the same game history. Consequences: (a) no legality impact (abilities ride on enumerated payloads); (b) any byte-identity or content-addressed replay comparison must normalize or avoid raw generated `AbilityId` strings. Must be addressed (normalize in digest, or thread the counter into state) before claiming byte-identical replay.

## 6. Snapshot / restore characteristics

| Facility | Exists? | Detail |
|---|---|---|
| Immutable state value | YES | `GameState` data class; `copy()` is the clone mechanism |
| Clone/copy API | Trivially (`copy()`) | No dedicated `clone()`; structural copies are idiomatic |
| Serialization | YES | kotlinx-serialization + `LegacyGameStateSerializer` migration; full polymorphic registry (`core/Serialization.kt`) |
| Server persistence | OPTIONAL | Redis blob behind `cache.redis.enabled` (default off); replay data excluded |
| Snapshot API (generic engine) | NO | "Snapshot" in-engine = LKI `EntitySnapshot`, not save/restore |
| Opaque native restore | NO | No restore-from-handle API at engine layer |
| Action-journal reconstruction | YES (server) | `ReplayReconstructor` re-fold |
| Gym snapshot slots | YES (in-process) | `SnapshotCodec` O(1) reference slots; byte-blob variant reserved, absent |
| Undo | YES (server, engine-computed policy) | Retained `GameState` reference + `UndoPolicyComputer`; epoch rotation invalidates abandoned branch |

No WS51 decision is made here: these are candidate facts for later restore-design comparison, not a restore verdict.

## 7. Headless / batch suitability — YES (mechanism)

- `gym` module is transport-agnostic Kotlin (no server, no browser): `GameEnvironment` single-env + `MultiEnvService` pooled multi-env with `stepBatch` parallel stepping (`EnvWorkerPool`), `fork`/`snapshot`/`restore`/`dispose`, deckbuild env variant.
- `GameSimulator.simulate` + `resolveToQuietState` auto-pass/trivial-decision folding for search/rollouts.
- `gym-server` HTTP mapping for out-of-process batch runners; `gym-trainer` self-play/search harnesses.
- `e2e-scenarios` and `manual-scenarios` show scenario-driven boards are a practiced pattern (scenario API → session → assertions).
- Resource bounds: `GameLimits.kt` safety clamps (not player-count limits); replay action cap; checkpoint cadence. Throughput numbers not measured here.

## 8. Maintenance topology (observed, facts only)

- Era-split corpus bounds compile units (`:mtg-sets` aggregator re-exports; `MtgSetCatalog` classpath scan = no compile dep from catalog to eras).
- Per-era `tests` children keep card PRs to one directory; engine tests stay in `:rules-engine`.
- `verifyGeneratedCards` gate (emit → isolated compile → gameplay-tree diff vs golden) + snapshot goldens + `CardLinter` load-time rejection + `check-card-counts`/`check-backlog-implementations` scripts = layered corpus hygiene.
- Stale-doc risk is real: `docs/engine-server-interface.md` is outdated at the lock (field-level drift). Doc-freshness process not assessed.
