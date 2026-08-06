# Mulligan Lab Report

Deck: `korvold/current`
Deck hash: `4af053a36d9cf4e84ff5ac2c2e5372daba5336c3cdfb48914ea4d72ea495677d`
Samples: 1000

All keep rules and follow-up outcomes are model-based structural estimates.

## Policy comparison

| Policy | First-seven keep | Mulligan rate | Avg mulligans | Color issues | Structural placement |
|---|---:|---:|---:|---:|---:|
| conservative | 0.737 | 0.263 | 0.359 | 0.044 | 1.264 |
| curve_oriented | 0.750 | 0.250 | 0.334 | 0.055 | 1.337 |
| commander_oriented | 0.737 | 0.263 | 0.358 | 0.063 | 1.367 |
| interaction_oriented | 0.741 | 0.259 | 0.351 | 0.058 | 1.346 |
| matchup_oriented | 0.752 | 0.248 | 0.336 | 0.059 | 1.378 |
| primer_policy | 0.712 | 0.288 | 0.402 | 0.058 | 1.341 |
| current_pilot | 0.708 | 0.292 | 0.413 | 0.047 | 1.482 |
| learned_policy | 0.751 | 0.249 | 0.343 | 0.058 | 1.368 |

## Boundaries

- Hand quality is separated from complete matchup performance.
- No rule is universal or empirically proven.
- No external rules engine was used.
