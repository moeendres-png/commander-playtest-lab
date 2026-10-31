# Deck comparison: verdicts of several variants in one run are corrected by Holm (2026-10-31)

Refs #1104, #1070 (E6 stage 3). Measurement tool only (`full_game_comparison.py` and the summary
lines of `run_full_game_deck_comparison.py`, no bridge, fork, pin or sealed record), so no
requalification. Win rates stay UNDECIDED.

## 1. Finding

A run with K variants judged every variant on its own at the level alpha. Looking at several
variants and reporting the one that stands out makes a false "decided" much more likely than
alpha. Simulation (`raw/sim_holm_variants.py` in the project folder; 3000 runs per cell, H0 true
for every variant, 25 seeds, 4 rotations per seed, discordance rate 0.10, independent draws per
variant): with the verdict rule of stage 2 and no correction, at least one variant was decided in
8.9 % of runs at K = 5 and 17.1 % at K = 10 with independent pairs (w = 0), and 19.7 % and 35.4 %
with fully shared signs (w = 1); nominal 5 %.

## 2. Change

Each variant gets one effective p-value, the larger of its pair sign test and, when some seed
holds more than one pair, its per-seed t test (so it is below alpha exactly when both conditions
of stage 2 pass; a t statistic that leans the other way, or a missing cluster test, is 1). With
two or more variants that have a verdict basis, Holm (`holm_adjust`, already in the repo) adjusts
these p-values over the variants of the run. A decided verdict stands only when its adjusted
p-value is below the level (the per-look level of a sequential run). Otherwise the verdict is
`NO_CLEAR_DIFFERENCE` and `holm_withheld_verdict` keeps the verdict it would have had; the
summary prints a NOTE. Holm can only hold a verdict back, never decide one.

A run with one variant is unchanged (no Holm fields are set). Variants without a verdict basis
(`INSUFFICIENT`) are not part of the family.

New result fields `effective_p_value`, `holm_adjusted_p_value`, `holm_withheld_verdict` (default
empty; old reports load as before). New summary line "Holm over K variants: adjusted p=...".

## 3. Rates (alpha 0.05, 25 seeds, 4 rotations per seed)

Decided under H0, share of runs with at least one decided variant:

| Variants K | w | old (stage 2 per variant) | new (Holm) |
|---|---|---|---|
| 1 | 0.0 / 1.0 | 1.6 % / 4.2 % | 1.6 % / 4.2 % |
| 2 | 0.0 / 1.0 | 3.3 % / 8.5 % | 1.1 % / 2.5 % |
| 5 | 0.0 / 1.0 | 8.9 % / **19.7 %** | 0.6 % / 2.0 % |
| 10 | 0.0 / 1.0 | 17.1 % / **35.4 %** | 0.6 % / 1.5 % |

Power for one real effect (the variant wins 65 % of its discordant pairs, rate 0.25, the other
K - 1 variants null), share of runs in which the true variant is decided, and share in which some
null variant is wrongly decided (w = 0 / w = 1):

| Seeds | K | true variant decided: old | new | a null variant decided: old | new |
|---|---|---|---|---|---|
| 25 | 5 | 22.0 % / 16.9 % | 5.8 % / 5.2 % | 8.7 % / 17.8 % | 0.8 % / 3.0 % |
| 40 | 5 | 37.6 % / 23.8 % | 14.0 % / 8.2 % | 11.1 % / 18.3 % | 1.4 % / 4.0 % |
| 60 | 5 | 57.8 % / 30.2 % | 30.7 % / 12.6 % | 13.6 % / 17.8 % | 2.0 % / 3.3 % |
| 60 | 10 | 57.5 % / 30.8 % | 22.0 % / 8.5 % | 27.0 % / 36.6 % | 1.8 % / 3.9 % |

K = 1 is identical before and after (25 seeds: 21.4 % / 16.5 % decided, 40 seeds 37.9 % / 22.5 %,
60 seeds 57.0 % / 30.1 %).

Reading: the correction does what it is for: the chance that a run reports a wrong variant falls
from 18 to 37 % (K = 5 to 10, shared signs) to 2 to 4 %. The price is power: with five variants a
real edge of this size is found about half as often as before (60 seeds, independent pairs: 57.8 %
to 30.7 %), with ten variants less than half. Runs that compare many variants need more seeds
for the same chance to find a real edge, or fewer variants.

## 4. What changes in practice

- The family is the set of variants of one run. A variant tested in its own run is judged alone;
  the correction does not follow a person from run to run.
- A decided verdict in a multi-variant run is now stronger evidence than before and rarer.
- The stored comparison reports (`pilot-ai/992-acceptance`) hold one variant; their verdicts do
  not change.

## 5. Not done

- Stage 4 (a spending rule instead of Bonferroni over the looks of a sequential run) is its own
  step after this measurement.
- The simulation draws the variants independently; real variants share the baseline games. Holm is
  valid under any dependence, so the false-decision rates hold, but the power numbers are for
  independent variants.
- No winner's-curse correction of the reported differences.
