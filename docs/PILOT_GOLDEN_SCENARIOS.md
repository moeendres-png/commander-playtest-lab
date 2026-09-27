# Pilot Golden Scenarios — Audit G

Date: 2026-08-09
Mode: deterministic structural pilot evaluation, seed 0

## Corpus design

G creates two disjoint corpora:

- Development: 24 cases (12 Korvold, 12 RogShai);
- Holdout: 12 cases (6 Korvold, 6 RogShai).

Every case supports an acceptable-action set instead of requiring one exact action string. Bad-action IDs are represented independently. Cases store pod size, seat, commander state, board/resource state, opponents, uncertainty, optional stack context, strategic reason, failure mode, and utility dimensions.

The corpora cover 3-, 4- and 5-player pods, early/late seats, archenemy states, multi-opponent pressure, known and uncertain opponent profiles, protection timing, wipe timing, stack interaction, engine-vs-threat choices, finish windows, and rebuild.

## Korvold development coverage

- hold an exposed Korvold without material/protection;
- cast in a protected immediate-value window;
- use independent table-damage payoff while commander is offline;
- genuine land/graveyard rebuild after wipe;
- five-player compressed table finish;
- boardwipe timing;
- engine vs central threat;
- repeatable token engine without commander;
- Morcant + Blight pressure;
- Kaervek + Doom priority;
- Wakanda + Cosmic artifact pressure;
- archenemy survival/protection.

## RogShai development coverage

- hold unprotected combat-draw aura;
- protected aura window;
- Jeska as true Commander-damage support;
- Kediss as collateral table damage, not Commander damage;
- independent Guttersnipe axis after Ishai removal;
- counter Kaervek before own spell sequence;
- answer Blight engine;
- hold flexible response against uncertain Cosmic pressure;
- artifact answer against Doom/Wakanda;
- wipe vs interaction reserve;
- Silence-protected finish;
- archenemy protection of a grown Ishai.

## Holdout coverage

Holdout variants recombine the same strategic principles under unseen state combinations:

- Korvold: 3p land rebuild, 4p independent finish, 5p repeated removal, multiple engines, 5p finish compression, 3p low-threat development;
- RogShai: 3p Jeska lethal, 5p Kediss spread, offline independent axis, Kaervek stack window, Blight + Cosmic multi-threat, 5p archenemy reserve.

## Evaluation result

| Corpus | Pre-G pilot | Final G pilot |
|---|---:|---:|
| Development | 18/24 | 24/24 |
| Holdout | 9/12 | 12/12 |

Holdout was not used for parameter tuning. The full machine-readable evidence is in `artifacts/audit/G_HOLDOUT_EVAL_RESULTS.json`.

These are controlled structural decisions. They do not validate exact Magic priority, targeting legality, damage replacement effects, or stack resolution outside the existing validation boundary.
