# Structural Model Resolution Measurement Protocol

Version: `model-resolution-measurement-0.1.0`

## Purpose

This protocol measures the current Structural Model's same-model sampling resolution on the
`placement_improvement` scale without launching a RogShai optimizer campaign and without consuming
confirmatory or sealed-holdout evidence.

The protocol is deliberately narrower than a deck-power benchmark. It asks: **how far can repeated
independent Structural estimates of the same current RogShai control move under the frozen model and
balanced experimental design?**

## Evidence boundary

All outputs are `structural_model_estimates`.

The measurement is not:

- empirical Commander winrate evidence;
- an external-rules-engine validation;
- a local opponent-frequency estimate;
- evidence that unknown Morcant/Cosmic cards equal a synthetic completion;
- a new RogShai search or canonical-deck recommendation;
- confirmatory or sealed-holdout evidence.

## Frozen technical design

Default protocol:

- canonical current RogShai control only;
- 4-player Structural simulation;
- current `CurrentOpponentRepository` and balanced pod scheduler;
- strong deterministic pilot for the sampling-resolution blocks;
- four independent seed blocks;
- 56 balanced scenarios per seed block;
- 56 scenarios for the separate pilot sensitivity axis;
- 35-turn cap;
- two workers;
- calibrated SESOI floor `0.05` from Optimizer-v2 calibration.

Each block uses a disjoint deterministic seed domain. Overlapping scenario-seed sets are a hard
failure.

The existing paired campaign runner is reused with control = control to avoid creating a second
simulation path. Only the baseline side is consumed for the sampling estimate. The identical
variant side is an execution-control duplicate and **must not** be interpreted as evidence that
model noise is zero.

## Resolution metric

The measurement scale is average placement positions, which is the same signed unit used by
`placement_improvement = baseline_average_placement - candidate_average_placement`.

For each independent seed block, calculate the current control's mean placement. The sampling
resolution spread is the full range across those independent block means:

`seed_block_range = max(block_mean) - min(block_mean)`

The current effective Structural resolution is:

`max(calibrated_SESOI, seed_block_range)`

This is intentionally conservative. It is a current-model decision threshold, not a real-game
minimum effect size.

## Axes that are not folded into the threshold

Seat, admissible opponent-group and pilot differences answer different questions from same-model
Monte Carlo precision. They are therefore reported separately as robustness/input-sensitivity axes:

- `seat_assignment`
- `admissible_opponent_group`
- `pilot_policy`

They are not averaged into the resolution threshold and do not become empirical replication.

This separation prevents input/model sensitivity from being mislabeled as stochastic sampling
uncertainty.

## Seat / turn-order contract

The Whole-Deck campaign runner passes `starting_player_seat=0` to the Structural Simulator. Physical
seat 1 therefore starts each campaign game, while the balanced scenario scheduler rotates RogShai's
own seat across seats 1–4.

This is not itself a pairing defect: a baseline/candidate pair uses the same seed, own seat,
opponent seat assignment, pilot configuration and turn cap, so the direct physical-seat effect is a
common condition within the paired contrast. It does mean that **absolute pooled Structural
performance is seat-sensitive** and must not be interpreted as seat-neutral deck power.

When the measured seat spread exceeds the effective sampling resolution:

- absolute pooled Structural claims are blocked;
- candidate comparisons remain eligible only under same-seat paired execution;
- own-seat coverage must be balanced;
- the paired effect must be reported stratified by seat;
- a directional conclusion must survive the declared seat-robustness check.

This gate is based on the measured axis being larger than the measured decision resolution; no
arbitrary seat-effect percentage threshold is introduced.

## Scenario/input and pilot robustness

Admissible opponent-group and pilot spreads are also compared with the measured sampling resolution,
but remain separate axes. A material opponent-group spread requires scenario-robustness evidence.
A material pilot spread requires pilot-robustness evidence. Neither spread is converted into
additional Monte Carlo noise or averaged into the resolution threshold.

Opponent-group measurements retain their evidence boundary: incomplete Morcant/Cosmic inputs remain
partial/synthetic scenario evidence and do not become local observation through repetition.

## Compression and unsupported axes

Outcome compression is reported directly through the observed placement distribution, dominant
placement share, unique placement values, place-1 share and seat spread. A compressed cohort can
trigger a `MODEL_INFORMATION_LIMIT` diagnostic.

No arbitrary numeric tie/quantization penalty is invented.

A separate frozen mulligan-policy intervention on the same placement metric is not currently exposed
by the Structural match runner. It remains explicitly unsupported rather than being proxied through a
different metric.

## Promotion to Current State

A measurement artifact may replace `MODEL_RESOLUTION_CURRENT.json` only after:

1. the dedicated measurement workflow succeeds;
2. the artifact passes evidence-boundary checks;
3. normal CI / quality / security / Windows / acceptance gates are acceptable;
4. the artifact is reviewed for model-information compression and unexpected sensitivity;
5. no confirmatory or sealed-holdout evidence was consumed.

Promotion changes the technical Decision-Quality calibration state only. It does not alter canonical
RogShai, inventory, physical allocation, purchases, opponent observations or frozen Kaervek.
