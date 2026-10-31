# Deck comparison: a decided verdict needs the per-seed t test (2026-10-31)

Refs #1085, #1070 (E6 stage 2). Measurement tool only (`full_game_comparison.py`, no bridge, fork,
pin or sealed record), so no requalification. Win rates stay UNDECIDED.

## 1. Finding

The four seat rotations of one seed share a library shuffle. The pair sign test counts every pair
as an independent observation, so it decides too often when the pairs of a seed lean the same way.
Simulation (`raw/sim_cluster_t_rule.py` in the project folder; 20 000 runs per cell, H0 true, 4
rotations per seed, discordance rate 0.10): the old verdict decided 7.4 % of runs at 25 seeds and
8.8 % at 40 seeds when a seed's discordant pairs share their sign completely (nominal 5 %).

## 2. Change

`aggregate_comparison` keeps the pair sign test as the first condition. When some seed holds more
than one pair, the verdict also needs the cluster-robust t statistic (one cluster per seed, CR1,
df = seeds - 1, the statistic behind `cluster_difference_stats`) to exceed the t quantile of the
same level (so the per-look level of a sequential run applies). If it does not, the verdict is
`NO_CLEAR_DIFFERENCE` and `pair_test_verdict` keeps the verdict the pair test alone gave; the
summary prints it. With one pair per seed nothing changes. When all seeds have the same net
difference there is no spread to divide by; then the sign test over the seeds (2 / 2**seeds)
decides, which needs six identical seeds at 5 % and eight at 1.25 %.

New result fields `cluster_t_statistic`, `cluster_t_df`, `pair_test_verdict` (default empty, old
reports load as before).

## 3. Rates (alpha 0.05, 4 rotations per seed)

"w" is the share of a seed's discordant pairs that follow the seed's common sign (0 = independent
pairs, 1 = fully shared).

| Seeds | w | Decided under H0: old | new | Decided for a real effect (variant wins 65 % of discordant pairs, rate 0.25): old | new |
|---|---|---|---|---|---|
| 9 | 0.0 | 0.4 % | 0.2 % | 7.5 % | 3.2 % |
| 9 | 1.0 | 2.3 % | 0.8 % | 20.2 % | 5.8 % |
| 25 | 0.0 | 2.3 % | 1.9 % | 25.7 % | 21.9 % |
| 25 | 1.0 | **7.4 %** | 4.2 % | 34.8 % | 15.7 % |
| 40 | 0.0 | 2.7 % | 2.5 % | 42.4 % | 38.8 % |
| 40 | 1.0 | **8.8 %** | 4.6 % | 45.3 % | 22.3 % |
| 60 | 0.0 | not run | not run | 60.9 % | 58.1 % |
| 60 | 1.0 | not run | not run | 57.4 % | 30.7 % |

Reading: the new rule holds 5 % in every cell. With independent pairs (w = 0) it costs 1 to 4
percentage points of power; with fully shared signs it costs more, and there the old power was
partly false decisions. An earlier variant (pair test and a sign test over seeds) was simulated
too and cost about half the power at 25 seeds, which is why the t statistic was chosen.

## 4. What changes in practice

- A look with few seeds decides less. With four rotations the sign fallback needs six identical
  seeds at 5 %, so `--look-every 5` can no longer decide at the first look; use ten or more seeds
  per look (the sequential tests use looks of ten and seven seeds).
- The stored comparison reports of `pilot-ai/992-acceptance` hold one seat per seed; their
  verdicts do not change.
- Verdicts of runs with rotated seats may turn from decided to `NO_CLEAR_DIFFERENCE`; the summary
  says so in a NOTE line.

## 5. Not done

- Holm over several variants (stage 3) and a spending rule instead of the Bonferroni split over
  looks (stage 4) are separate changes.
- The simulation covers a sign-sharing model and fair or 65 % signs; it does not cover fractional
  shares or censored pairs. The intraclass correlation of real pair differences is still UNKNOWN.
