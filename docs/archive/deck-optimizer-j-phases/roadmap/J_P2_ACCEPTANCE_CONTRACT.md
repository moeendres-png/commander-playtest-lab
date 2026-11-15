# Roadmap J-P2 Acceptance Contract — Modeling & Data Quality

Baseline: `main` `807b3602c48824df40a70d2a715f9dfb6dc3e8c6`, tree `50e66b90d7349ebe8e66ebbec0cb9f338a153087`, package `1.14.1`.

## Scope

J-P2 improves decision-relevant model/data truth without reopening J-P0/J-P1 reliability work and without changing canonical decks, inventory, purchases, physical allocations, or frozen opponent lists.

Priority axes:

1. opponent evidence provenance and uncertainty;
2. rules/card coverage scoping and truth labels;
3. active-own-deck versus frozen-opponent boundaries;
4. 3/4/5-player and politics/threat sensitivity;
5. stack/combat/finisher/rebuild decision abstractions;
6. development/golden/sensitivity evidence before any holdout use.

## Fail-closed invariants

- Active own optimization targets are Korvold and RogShai only.
- `kaervek/current` is frozen opponent-only and may be used as a simulation/matchup opponent, but not as an upgrade/swap/allocation target.
- Unknown Cosmic/Morcant slots are never promoted to observed cards.
- Official-precon evidence, direct/partial observation, inference, synthetic completion and unknowns remain explicitly distinguishable.
- Structural estimates are not empirical win rates.
- Tactical Oracle is not an external rules engine.
- Real-playtest calibration remains inactive project scope.

## Holdout policy

`J_HOLDOUT_v1` stays unopened and unevaluated during development. No tuning may use it.

Frozen identity:
- 12 cases; Korvold + RogShai; pod sizes 3/4/5;
- file SHA256 `a5875cd1a8edf6bbf79248b3e4ba26151579f628eaeefd4ef2369abb309da8d1`;
- set hash `724e84f1ea34bea9ec6b37929d945724c77c408a464b3a9dd05235738a00d5d6`;
- mutable=false; used_for_tuning=false; first_evaluation_timestamp=null.

A one-time P2 holdout evaluation is allowed only after the P2 candidate, development scenarios, metrics, and stop criteria are frozen. Holdout outcome must not trigger further tuning in the same P2 candidate.

## Development acceptance gates

Before a P2 candidate may be frozen:

- existing 24-case J/G development decision corpus passes;
- new P2 regression cases for truth boundaries pass;
- exact rules-coverage scoping is correct for own and opponent deck IDs;
- opponent structural profiles expose explicit evidence kinds without changing underlying known/synthetic/unknown counts;
- Kaervek cannot enter upgrade/swap/allocation optimization paths;
- canonical data audit remains MATCH;
- Ruff/format/Mypy/full pytest/compile pass;
- no canonical MTG data mutation;
- `J_HOLDOUT_v1` remains unevaluated.

## Stop rule

Prefer a small number of high-impact truth/model fixes over broad simulator retuning. Do not change heuristic weights merely because a development scenario is difficult; require a concrete misspecification and regression evidence.
