# Sequential deck comparison: alpha is spent over the looks, not split equally (2026-10-31)

Refs #1106, #1070 (E6 stage 4). Measurement tool only (`full_game_comparison.py` and the sequential
runner in `run_full_game_deck_comparison.py`, no bridge, fork, pin or sealed record), so no
requalification. Win rates stay UNDECIDED.

## 1. Finding

`--stop-when-decided` split the 5 % equally over the planned looks (alpha / L, #832). With the
verdict rule of stage 2 that split is very conservative. Simulation (`raw/sim_sequential_looks.py`
in the project folder; 1200 runs per cell; 4 rotations per seed, discordance rate 0.10 under H0 and
0.25 with a real effect where the variant wins 65 % of discordant pairs; looks of 10 seeds): the
share of H0 runs in which some look decided was 0.6 to 1.8 % at a nominal 5 %, and power was lost
with it.

## 2. Change

`sequential_look_alphas(significance_level, cumulative_seeds)` gives each look its own level from a
Lan-DeMets spending function of the O'Brien-Fleming type, `a(t) = 2 - 2 * Phi(z / sqrt(t))` (`z` the
two-sided normal quantile of the level, `t` the share of the seeds played). Look k decides at the
increment `a(t_k) - a(t_k-1)`. Each look's test has at most its own level, so the chance that any
look decides falsely is at most the sum of the increments, which is exactly the significance level:
a union bound that assumes nothing about how the looks depend on each other. The runner uses the
level of the current look, the CLI prints the levels, and the `sequential` payload carries
`look_alphas` instead of the single `per_look_alpha`. `sequential_look_alpha` (equal split) is gone.
With Holm over several variants (stage 3) the correction applies inside each look at that look's
level, which keeps the bound.

The default of `--look-every` is now 10: with four seat rotations a look of five seeds cannot
decide under the rule of stage 2 (`VERDICT_CLUSTER_T_2026-10-31.md`).

Examples of the levels: two looks of 10 seeds 0.0056 and 0.0444; four looks 0.0001, 0.0055, 0.018,
0.026; six looks 0.0000, 0.0007, 0.0049, 0.0108, 0.0154, 0.0182 (the first is about 1e-6).

## 3. Rates (alpha 0.05, looks of 10 seeds, w = share of a seed's discordant pairs that follow the
seed's common sign; 0 = independent pairs, 1 = fully shared)

| Max. seeds (looks) | Rule | Error under H0 (w = 0 / 1) | Power for the real effect (w = 0 / 1) | Mean seeds played |
|---|---|---|---|---|
| 30 (3) | equal split | 0.6 % / 1.5 % | 13.5 % / 11.7 % | 29.3 / 29.0 |
| 30 (3) | spending | 1.1 % / 2.9 % | 20.6 % / 15.6 % | 29.4 / 29.4 |
| 40 (4) | equal split | 0.8 % / 1.8 % | 20.7 % / 13.0 % | 38.3 / 38.5 |
| 40 (4) | spending | 1.6 % / 2.6 % | 29.4 % / 17.6 % | 38.5 / 38.9 |
| 60 (6) | equal split | 1.0 % / 1.4 % | 33.0 % / 17.2 % | 54.7 / 56.5 |
| 60 (6) | spending | 1.2 % / 2.5 % | 43.8 % / 20.5 % | 54.5 / 57.2 |

Reading: the error stays below the nominal 5 % (as the construction guarantees) and the power
rises by 4 to 11 points; the mean number of seeds does not change because a run rarely stops early
at these effect sizes. Other spending functions (alpha * t^1.5, ^2, ^3) lie between the two rows.
A constant level calibrated to 5 % under one assumption about w (Pocock style) overshot to 6 to 7 %
under fully shared signs, which is why a calibrated constant was not used.

## 4. What changes in practice

- Early looks decide only on overwhelming evidence (the first look of a 4-look run needs a level of
  0.0001); a run that would have stopped at the first look under the equal split may now go on.
  Most of the gain is at the last look.
- Stored sequential reports hold `per_look_alpha`; new ones hold `look_alphas`. Nothing reads the
  old field.

## 5. Not done

- No futility rule (not measured).
- The union bound is not the exact boundary that accounts for the correlation between looks; the
  measured error (1 to 3 %) shows there is room left, and an exact boundary would be a larger step
  than this one.
- The simulation uses one variant; with several variants the stage-3 correction applies per look.
