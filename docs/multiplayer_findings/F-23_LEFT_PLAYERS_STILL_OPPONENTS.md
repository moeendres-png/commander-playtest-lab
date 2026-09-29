# F-23: players who left the game this turn still count as opponents

**Status: REMEDIATION_CANDIDATE — Mage PR #26 / Lab successor repin. Tracker: #335.** Found by the multiplayer discovery lane (Claude Opus 5.5) on 2026-09-29.


## Classification
- `RULES_CORE_DEFECT` in the XMage engine: generic opponent queries.
- **Multiplayer only.** In 2P, a player leaving ends the game.

## Source lock
- Lab main: `b31f144b5e1ae2d5e3203a2f1cc87797806cb736`.
- XMage pin: `b19596980f2734496ea1896504253e1bdd2756dd` (not moved).
- The rule: a player who has left the game is no longer in the game, so they are no longer an opponent.
  - The CR number and verbatim text were not re-read, so both are UNKNOWN. Egress is blocked.
  - XMage's own javadoc on `Game.getOpponents` says it "will return dead players until end of turn" and cites 800.4k. That rule covers effects lasting until end of turn. It does not cover opponent counts or opponent comparisons.

## Defect
`Game.getOpponents(playerId)` defaults to `excludeLeavedPlayers = false`. Every count or comparison built on it therefore includes a player who left earlier in the same turn, until ranges of influence are recalculated at the next turn.

Proven consumers, native, 4P at the pin, each with a green control case:
- `OpponentsCount` ("draw a card for each opponent you have"), card Inspired Sphinx.
  - After one opponent concedes, A still draws 3 instead of 2.
  - After two opponents concede, A still draws 3 instead of 1.
  - Proven at 4P and 5P.
- `OpponentHasMoreLifeCondition`, card Beza, the Bounding Spring.
  - C has 60 life and concedes. A (40) still gains 4 life, although every opponent still in the game has 40.

About 25 other conditions and counts in `Mage/src/main/java/mage/abilities/{condition,dynamicvalue}/common` use the same default. Examples: `OpponentControlsMoreCondition`, `CorruptedCondition`, `LifeCompareCondition`, `TwoOrMoreOpponentsCondition`, `OpponentsPoisonCountersCount`.

Card-local count sites:
- IllusionistsGambit
- ManifoldInsights
- MoggAssassin
- MausoleumTurnkey
- TasigurTheGoldenFang
- KarplusanMinotaur
- ViashinoBey
- CuombajjWitches
- AraumiOfTheDeadTide
- RainbowVale
- TributeAbility

## Evidence
Mage fork branches:
- `claude/mp-discovery-20260929`: `OpponentLifeAfterLeaveProbe4PTest`.
- `claude/f23-opponents-count-left-players-20260929`:
  - donor fix for `OpponentsCount` only, which passes `excludeLeavedPlayers = true`;
  - `OpponentsCountAfterLeave{4,5}PTest`;
  - red 4/6 at the pin, green 6/6 with the fix;
  - full `Mage.Tests`: 6937 run, 0 failures.

## Ownership
The root is the default semantics of `Game.getOpponents`, which lives in `Game.java`. That file belongs to the XMage candidate-integration/repin lane, where F-21 also changes `getOpponents`.

This lane therefore does **not** change `Game.java`. The class is handed to that owner with two options:
1. Change the default semantics, which needs an 800.4k impact review.
2. Or fix each consumer.

The `OpponentsCount` branch is donor evidence.

## Random-opponent consumers (code inspection only, not proven at runtime)
These pick "an opponent at random" from `getOpponents(controller)`, which does not exclude players who left. A departed player can therefore be chosen, which also shifts the Rules-RNG index mapping:
- `IndoraptorThePerfectHybrid`
- `TheRuinousPowers`

By contrast, `VialSmasherTheFierce` filters out `hasLeft()`/`hasLost()` and `MaddeningHex` passes `excludeLeavedPlayers = true`, both correctly.

A runtime proof needs a seeded Rules-RNG harness that forces the departed index.


## 2026-09-29 successor remediation
- Candidate engine: `fcfde9dad30fa56e60d5f5bc40ddce6ecd68019c` (Mage PR #26).
- Commander Lab repin workstream: `xmage-f22-f23-successor-repin-20260929`.
- Runtime status remains UNKNOWN until exact-candidate and Lab CI complete; this note does not itself close F-23.
