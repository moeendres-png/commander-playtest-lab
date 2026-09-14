# WS208 → XMage Engine Successor Specification

Status: FINAL. Root-cause layer isolated as XMAGE_ENGINE_SIDE with 32 fresh-JVM
layered traces across 8 constructions (DIRECTLY_VERIFIED) plus engine-bytecode
call-chain analysis (CODE_DERIVED). No bridge production change made or needed.
`GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0`.

## 1. Observed defect (Lab-side, engine-caused)

Same-seed, same-deck, same-policy fresh-JVM runs produce different priority
offer SETs (±1 duplicate basic-land `PlayLandAbility`) and, in H01, a missing
`Clone — Cast Clone` offer. WS205 classified causality UNKNOWN; WS208 isolates
it to **layer A: underlying XMage game state differs before enumeration**
(hidden library order → different opening hands/draws → different
`getPlayable` SETS). Bridge projection is membership-transparent
(native-SET diff offsets == projected-SET diff offsets, 10/10 in H01×6);
no bridge mutation is made or needed.

## 2. Exact engine call chain (pinned engine `cfc36f44`, mage-1.4.61.jar)

1. `XmageFullGameSession.<init>` calls `RandomUtil.setSeed(seed)` — seeds ONLY
   the process-global `mage.util.Random` (`RandomUtil.random`).
2. `new CommanderFreeForAll(...)` → `GameImpl.<init>` executes:
   ```java
   UUID uuid = UUID.randomUUID();            // SecureRandom — fresh per JVM
   rulesSeed = uuid.getMostSignificantBits() ^ uuid.getLeastSignificantBits();
   rulesRandom = new GameRandom(rulesSeed);  // per-game Rules RNG
   rulesSeedExplicit = false;
   ```
3. `XmageFullGameSession.start` → engine thread `game.start(startingPlayerId)`
   → `GameImpl.init(UUID)` → unless `gameOptions.skipInitShuffling`, for each
   player: `player.shuffleLibrary(null, game)` → `PlayerImpl.shuffleLibrary`:
   `library.shuffle(game.getRulesRandom())` → `Collections.shuffle(list, rulesRandom)`.
4. Opening-hand draws + all later draws come from these differently-ordered
   libraries. Hands differ from the first draw (WS208 offset 2) in 6/6 fresh
   JVMs despite identical pre-start library order and identical `RandomUtil`
   probe streams (P1/P2 identical across JVMs).
5. `XmageFullGamePlayer.priority()` enumerates `getPlayable(game, false)` —
   faithful to the (diverged) state: each basic land in hand contributes one
   `PlayLandAbility`, so a 1-card hand difference surfaces as exactly ±1
   `activated_ability` in the offer SET. Selections stay identical
   (twin-following), terminals mostly coincide.

`GameImpl.setRulesSeed(long)` exists and reseeds `rulesRandom`, but the Lab
bridge never calls it (zero references in `engine-bridge/src/main/java`).

## 3. Smallest reproducer (no Lab pilot needed)

1. Fresh JVM; `RandomUtil.setSeed(S)`; construct two `CommanderFreeForAll`
   games with identical decks; `game.start(seat)` both; compare
   `player.getLibrary().getCardList()` name order (or opening hands).
   Expected: differ (rulesSeed from `UUID.randomUUID`).
2. Stronger: `gameA.setRulesSeed(S)` + `gameB.setRulesSeed(S)` before start →
   expect identical library order (proves the seed path is sufficient and the
   default seeding is the defect).

## 4. Source classes / methods (engine)

- `mage.game.GameImpl.<init>` — `rulesSeed`/`rulesRandom` initialization.
- `mage.game.GameImpl.init(UUID)` — init-time `shuffleLibrary` loop.
- `mage.players.PlayerImpl.shuffleLibrary` — uses `getRulesRandom()`.
- `mage.players.Library.shuffle(Random)` / `shuffle()` (no-arg uses
  `RandomUtil` — NOT the path taken at game start).
- `mage.util.GameRandom` / `mage.util.RandomUtil` — dual-RNG design;
  `RandomUtil.setSeed` does not reach `rulesRandom`.
- Follow-on audit: every other `getRulesRandom()` consumer
  (coin/dice/random-discard/random-target paths) inherits the same
  same-seed nondeterminism; `getRulesRandomCalls()` can quantify consumption.

## 5. Observed differing native sets (Lab evidence, 32 fresh JVMs)

Twin-mode layered traces (exact WS205 primary-stream following, budget 500):

| construction | seed | reps | stopped | native-SET ⟺ proj-SET | first offer div | selections differ |
|---|---|---|---|---|---|---|
| H01-HUMILITY_FIRST | 9113 | 6 | 6× twin_diverged@410 | 10/10 same offsets | 80 | 0 |
| D06 | 9106 | 4 | 4× budget | 4/4 same offsets | 47 | 0 |
| I01 | 9114 | 4 | 4× budget | 4/4 same offsets | 14 | 0 |
| A03 | 9101 | 4 | 4× budget | 124/124 same offsets | 47 | 0 |
| E02 | 9108 | 4 | 4× budget | 12/12 same offsets | 80 | 0 |
| B01 | 9103 | 4 | 4× budget | 28/28 same offsets | 14 | 0 |
| A04 (TRUE ctrl) | 9102 | 3 | 3× budget | 3/3 same offsets | 14 | 0 |
| F01 (TRUE ctrl) | 9109 | 3 | 3× budget | 0 (full agreement) | — | 0 |

Universals: `RandomUtil` probes P1/P2 identical in all runs; libraries differ
from offset 1 in all runs; hands differ from first draw in all runs; ZERO
offsets anywhere with equal hidden state but different native offers (native
enumeration faithful); ZERO selection diffs (deterministic pilot); bridge
projection membership-transparent in all 8 (native-SET diff offsets ==
projected-SET diff offsets exactly).

- H01: Clone never drawn/offered in any of 6 reps (vs cast at primary offset
  411); all reps stop `twin_diverged` at 410 — the explicit missing cast offer
  is draw-dependence, not enumeration loss.
- F01 3/3 full agreement despite differing libraries: WS205 TRUE verdicts are
  probabilistic coincidence (offers can coincide while hidden states differ),
  not determinism proof. TRUE controls do not establish correctness of other
  counts/runs.

## 6. Equal/different pre-enumeration state fingerprints

- Pre-start libraries: IDENTICAL (name order + size) across JVMs.
- `RandomUtil` reference-shuffle probes P1/P2: IDENTICAL across JVMs.
- Offset-1 (post-start, pre-draw) libraries: DIFFER in all heterogeneous decks.
- Conclusion: divergence enters exactly at game-start shuffling via
  `rulesRandom`, before any decision is enumerated.

## 7. Suspected nondeterministic source

`GameImpl` default `rulesSeed` from `UUID.randomUUID()` (unseeded
`SecureRandom`), consumed by `GameRandom` for all Rules shuffles/randomness.
`RandomUtil.setSeed` (the only seed the Lab bridge sets) does not propagate.

## 8. Required engine tests (successor workstream)

- Same-seed twin game construction yields identical library order/opening
  hands across fresh JVMs (fresh-process test, not in-JVM double-run, since
  `RandomUtil` is process-global).
- `setRulesSeed` propagation: explicit seed ⇒ identical `rulesRandom` streams.
- Consumption accounting: `getRulesRandomCalls()` equal across twins.
- Regression: London-mulligan, in-game shuffle effects (fetchlands/tutors),
  coin/dice paths under explicit seed.
- Soak: N-fresh-JVM offer-SET equality for the six WS205 FALSE constructions.

## 9. Lab repin / requalification burden

- Engine change ⇒ new engine pin ⇒ WS204 generic-action battery (88 tests),
  D1–D5 gates, WS205 twin matrix, and Full107 scope must be requalified from
  the new pin; historical PASSes survive only after impact adjudication.
- Lab-side: evaluate calling `setRulesSeed(seed)` (or per-game derived seed)
  from `XmageFullGameSession` after repin — NO such call in WS208 (engine-side
  outcome forbids masking; seed-authority semantics belong to the Rules Core
  and the engine successor, not to a bridge workaround).
- `GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0`. `D5_TWIN_EQUALITY` stays UNKNOWN until
  re-proven on the new pin.
