# RQ-X1 — Rules RNG (CODE_DERIVED, core cites DIRECTLY_VERIFIED)

Pin: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`.

SHORT ANSWER: Rules randomness comes from ONE JVM-global `java.util.Random`
shared with AI, setup, UI, and tests — plus at least three independent
unseeded sources. There is no per-game stream, no seed authority, no
serialization of RNG state, and affirmative evidence of consumption
instability. `SEED_SUPPORTED = FALSE` (provider statement) is CONFIRMED as an
engine fact at this pin: external seed control adequate for Semantic Replay
does not exist. (Global `RandomUtil.setSeed` exists but is test-only manual
global state — DIRECTLY_VERIFIED — and cannot qualify as seed support.)

## 1. Source inventory (abridged; full table in sealed record)

Central utility `Mage/src/main/java/mage/util/RandomUtil.java` (DIRECTLY_VERIFIED,
body quoted in `XMAGE_SOURCE_LOCK.md` provenance):

- `private static final Random random = new Random()` — single JVM-global static.
- `getRandom()` exposes the same instance; `setSeed(long)` mutates global state.
- `nextInt/nextBoolean/nextDouble` delegate to global; `randomFromCollection`
  walks **collection iteration order**.

Rules-RNG consumers (all via the global): `Library.shuffle()` Fisher-Yates
(`Library.java:37-47`); `flipCoinResult/flipCoins` (`PlayerImpl:3130-3186`,
extra flips on `FlipCount>1`, replacement rerolls); `rollDieResult/rollDice`
(`PlayerImpl:3225-3524`: Clam-I-Am rerolls, Big-Idea extra rolls,
`ignoreLowest`, `DieRolledEvent/DiceRolledEvent`); `shuffleLibrary`
(`PlayerImpl:1937-1944`); random discard (`:850-918` via
`CardsImpl.getRandom:80-92` which streams to `Collectors.toSet()` — HashSet
order); `seekCard` (`:3047`); ordering-prompt sampling (`:1067,1159,1210`);
`isRandom` targets (`TargetImpl:480-498`, e.g. Grip of Chaos); random modes
(`Modes:400-402`); card "at random" effects (dozens in `Mage.Sets`, e.g.
Capricious Efreet, Chaos Defiler, Vial Smasher, Ghastly Conscription);
`UndercityDungeon:153`, `Plane:321` (planar pick), `MomirEmblem:92`; init
shuffle (`GameImpl:1314-1317` unless `skipInitShuffling`).

AI consumers on the SAME stream: `ComputerPlayer:212,1019,1044` (X values,
land/deck build); `ComputerPlayer6:682` tie-break; `SimulatedPlayerMCTS`
~20 sites; `MCTSNode:115,270,278`; `ComputerPlayerMCTS:310,317`
(`getLibrary().shuffle()` inside simulation — AI playouts perturb the Rules
stream they fork from).

Independent unseeded sources (DIRECTLY_VERIFIED classes of finding):

- No-arg `Collections.shuffle()` — 16 repo hits; only `Rotater:35` and
  `MatchImpl:226` pass `getRandom()`. Rules-reaching no-arg sites include
  `PlayerImpl:1061,1204` (put top/bottom random order) and card effects
  (`GhastlyConscription:78`, `VialSmasher:133`, `JalumGrifter:111`, …).
  No-arg shuffle uses a per-call JDK `Random`: INVISIBLE to `setSeed`.
- `new SecureRandom()` per call (`JumpstartPoolGenerator:94-96`).
- Display/auth streams: per-UUID `new Random(lsb)` token image
  (`TokenRepository:423`, with comment "do not use global random here (it can
  break it with same seed)" — the codebase KNOWS the global stream is
  fragile); `SecureRandom` auth tokens/salts (`MageServerImpl:52`,
  `AuthorizedUserRepository:33`); `UUID.randomUUID` identity entropy (83 hits,
  not Rules RNG but per-run unique, defeating snapshot equality).
- Zero-hit verified: `Math.random(` (none), `ThreadLocalRandom` (none),
  `new Random(` only `RandomUtil:14` + `TokenRepository:423`.

Starting-player randomness: NO die roll. Random only in
`pickChoosingPlayer` fallback (`GameImpl:1565-1578`) + `MatchImpl:225-227`
seat shuffle; the real path is a human `choose()`.

Setup/non-paper: `SmoothedLondonMulligan:30,53-54` (`nextBoolean/nextDouble`
hand smoothing); draft/tournament/pairing/booster randomness — all global.

## 2. Verdicts

| Question | Verdict | Basis |
|---|---|---|
| Centralized? | NO | dominant global + no-arg shuffles + per-call SecureRandom + per-UUID Random + UUID entropy |
| Seedable? | PARTIAL-GLOBAL ONLY | `setSeed` exists (DIRECTLY_VERIFIED) but only tests call it (`RandomTest`, `LoadTest`); no-arg/SecureRandom ignore it by construction; no per-game seed API; `seed` grep in `Mage/src/main/java` hits only `RandomUtil` + one comment |
| Injectable per-game? | NO | `GameOptions:19-96` has no seed field; `GameImpl` copy (`:191-257`) and `GameState` copy (`:139-191`) carry no RNG; no `ThreadLocal`, no constructor param |
| Per-game stream? | NO | `static final`, shared across concurrent games on one server |
| Call-order stable? | NO (affirmative instability) | `randomFromCollection` iteration-order dependence (`CardsImpl` HashSet); variable consumption (rerolls, extra rolls, replacement events, smoothing, sim-vs-real branch divergence, AI interleaving) |
| Serialized? | NO | `static` ⇒ never in game serialization (`GameController:1004-1008` writes game+states only); `savedStates` fields are `transient`; `readObject:3626` re-inits; no seed/position stored |
| Reset per game? | NO | `GameImpl.init/start:1079-1380` never calls `setSeed`; `setSeed` is manual global reset affecting ALL concurrent games |
| Version-pinned + consumption-stable? | NO | no algorithm pin, no seed log, no consumption log, no canonical decision encoding |

## 3. Project-requirements gap

Project requires: all Rules randomness originates in the Rules Core with
explicit seed authority; no unseeded/harness-side randomness in
production-reachable paths; deterministic semantic replay from recorded seeds
+ authoritative Decision Options.

XMage at this pin: randomness originates in a SHARED GLOBAL (Rules Core +
AI + setup + UI on one stream); seed authority is absent (manual global
`setSeed` only); unseeded sources are production-reachable
(`PlayerImpl:1061,1204` ordering shuffles; card-effect no-arg shuffles);
consumption is order-unstable. An external pilot can NEITHER set a per-game
seed NOR reconstruct the consumed sequence from a seed. Closing this gap
without engine changes is impossible — RNG control is on the MUST-prove list
for any runtime mirror (see `XMAGE_RUNTIME_MIRROR_SPEC.md`, experiment R-1…
R-5), and any "seed support" claim would require engine modification
(forbidden in RQ-X1, and a Rules-authority-boundary change requiring Sol High
authority in any case).

## 4. Smallest runtime experiment if source alone is insufficient (DESIGNED, NOT RUN)

Single-JVM, single-threaded, fixed decks, `skipInitShuffling=false`,
London (not Smoothed) mulligan, no AI; `TestPlayer` with non-random choices
scripted, coin/die unscripted (falls through to `RandomUtil`):

- R-A (core-stream seed control): `setSeed(123)` → record init-shuffle order
  + `flipCoinResult` + `rollDieResult(6)` + `getRandom` on fixed pile +
  `seekCard`; repeat on fresh `Game` same seed. Equal ⇒ core stream isolated.
- R-B (unseeded source): same seed; `putCardsOnBottomOfLibrary(cards,false)` /
  `putCardsOnTopOfLibrary(cards,false)` (hits no-arg shuffle) + one no-arg-
  shuffle card effect; compare across identical seeds. Predicted UNEQUAL ⇒
  not centralized/seedable. DECISIVE for centralization.
- R-C (cross-contamination): `setSeed(123)` + one booster-gen / AI-deck-build
  / MCTS playout step interleaved, then R-A sequence; divergence ⇒ AI/setup
  shares the Rules stream; no per-game stream. DECISIVE for isolation.
- R-D (snapshot ≠ reexecution): `bookmarkState()` before
  `rollDice+shuffleLibrary`; `restoreState`; re-apply same decisions + seed
  reset; compare. Predicted divergence (RNG position not in snapshot) ⇒ no
  deterministic reexecution. DECI
...[truncated 583 chars]