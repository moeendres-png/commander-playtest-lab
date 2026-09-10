# RQ-C2 Rules-RNG Authority Review

Baseline: CR effective 2026-08-07. All Rules randomness originates in
the Rules Core with explicit seed authority. The CSN RNG journal (six
fields per the execution contract) is an ENGINEERING requirement for
deterministic replay; it is NOT a Magic Rules requirement. This review
keeps the two formally separate per scenario.

## F01 Rampant Growth (shuffle)

- Rules: search then shuffle (Rampant Growth Oracle); shuffle =
  randomize so no player knows the order (701.24a). Randomness occurs at
  resolution, performed by the searcher (P0) as part of following
  instructions (608.2c). Domain: P0's library minus found cards
  (701.24b). No reroll/replacement in scenario.
- Engineering: the shuffle MUST be a journaled RNG event (contract);
  the journal records the Rules event, it does not create it.

## J01 Mana Crypt (coin)

- Rules: upkeep trigger; flip a coin (705.1: two-sided object, equal
  likelihood; agreed substitutes allowed); flipper (controller P0)
  calls and wins/loses (705.2); loss path deals 3 damage atomically —
  official ruling 2020-08-07 confirms no actions intervene. Domain:
  {win, loss}. No reroll in scenario.
- Engineering: flip outcome journaled with domain win/loss; both paths
  asserted (37/40). The six-field journal shape is contract, not Rules.

## J02 Delina, Wild Mage (die)

- Rules: attack trigger; roll a d20 (706.1/706.1a: 1–20 equally
  likely); results table bands per Oracle: 1–14 single token, 15–20
  token + may-roll-again (706.3/706.3c; roll-again optional per 603.5
  and the 2021-07-23 official ruling). Scripted 17 lands in 15–20.
  Token copy characteristics per 707.2/111.3 (nonlegendary,
  tapped-attacking, end-of-combat exile). Declining ends recursion
  (nothing further instructs a roll).
- Engineering: the 17 is journaled; token lifecycle (created-then-
  exiled) asserted from Rules events, not from the journal.

## J03 Hymn to Tourach (random selection)

- Rules: "discards two cards at random" — 701.9b explicitly permits
  random (non-chooser) discard. Randomness occurs at resolution;
  performed as part of following the spell's instructions; domain: all
  2-of-4 subsets of P1's fixed 4-card hand, uniformly. No reroll. No
  chooser decision may be offered — offering one would be a Rules
  violation, not a UI choice.
- Engineering: the selected pair is journaled; discarded pair public,
  retained pair private (zones, not journal, determine visibility).

## Explicit separation statement

For each of F01/J01/J02/J03: the Rules event (shuffle/flip/roll/
at-random selection) exists and is fully specified WITHOUT any journal;
the journal exists to make the production implementation deterministic
and replayable (seeds + authoritative Decision Options, per project
replay policy). Qualification must assert the Rules outcome AND the
journal's presence/shape as two distinct checkpoints. No unseeded or
harness-side randomness is permitted in production-reachable paths.
