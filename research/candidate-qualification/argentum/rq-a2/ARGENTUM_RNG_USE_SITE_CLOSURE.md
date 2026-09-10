# RQ-A2 — RNG Use-Site Closure (U15b)

Question: does discoverable Rule-relevant randomness actually route through `GameRng`,
or do production Rules paths bypass it?

Evidence split (per adjudication): tested-path seed/RNG reproduction is `DIRECTLY_VERIFIED`
(U19/U22 runtime: recorded seed == config seed; seed+1 rejected at frame 0; G3's 9 coin
flips identical across folds); the exhaustive no-bypass closure below is `CODE_DERIVED`
(grep at the lock), not runtime proof for every consumer.

## RULES_RNG — everything in-game routes through state-threaded `GameRng`

Single entry: `GameState.nextRandom` (`GameState.kt:1210`); seed authority `GameConfig.seed`
(`GameInitializer.kt:91,161-162`, null → `System.nanoTime()` at the one sanctioned boundary,
always recorded in `InitializationResult.seed`). Consumers (all via `nextRandom`):

- `GameInitializer` (turn order, library shuffles, mulligan/hand-smoothing draws)
- `MulliganHandler`, `CoinFlipService` (`nextBoolean`), `CostPaymentService`/`CostHandler`
  (random discard/costs, shuffle), `StackResolver` (shuffle), `ZoneTransitionService`,
  `CascadeExecutor` (bottom-randomize), `ReselectTargetRandomlyExecutor` (Grip of Chaos),
  `SelectFromCollectionExecutor`, `MoveCollectionExecutor`, `ShuffleLibraryExecutor`,
  `PayOrSufferExecutor`, `CreateRandomCreatureTokenWithManaValueExecutor` (Momir-style picks)

No competing source in any rules path: zero `kotlin.random` / `java.util.Random` /
`SecureRandom` / `Math.random` / bare `.shuffled()` / `.random()` in `rules-engine/src/main`
outside the pre-game `limited/` package (verified by grep).

## NON_RULES_RNG (pre-game product, not in-game)

- `limited/BoosterGenerator.kt`, `limited/CubeDealer.kt` (`kotlin.random.Random`):
  booster/cube construction. Lobby seeds cube dealing with `System.nanoTime()`
  (`TournamentLobby.kt:477`). Outside game start; never touches `GameState.rng`.

## AUTH (non-game, correct usage)

- `SecureRandom` in `MagicLinkService` / `AuthTokenService` (login tokens). Not game randomness.

## AI_RNG (choice among legal options, never Rules outcomes)

- `ai` deck generators (explicit `random` params — pool/deckbuilding tooling).
- `gym/ActionSelector.kt` (`java.util.Random`): action SELECTION for rollouts/training.
  Never feeds `GameState.rng`; never decides a Rules-random outcome.

## TEST_RNG (harness-side, recorded as inputs where it matters)

- `ScenarioTestBase` per-build entropy seeding (scenario variety).
- `ReplayDivergenceReproTest` fuzzer `kotlin.random` (choice randomness; responses recorded).
- RQ-A2 drivers: deterministic policies (no RNG); fixed seeds.

## Pilot/model randomness

Not counted as Rules RNG (none present in credited paths).

## Verdict

Closure holds: a clean `GameRng` class AND no production Rules-path bypass. Starting-player
"randomness" is the seeded turn-order shuffle (U12: config-selected or seed-drawn, recorded).
