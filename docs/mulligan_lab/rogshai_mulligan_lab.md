# Mulligan Lab Report

Deck: `rogshai/current`
Deck hash: `2f2dab2a26e3889aa5399504295d2c6e485c8922397c6736bd4e6fa72f6b6656`
Samples: 1000

All keep rules and follow-up outcomes are model-based structural estimates.

## Policy comparison

| Policy | First-seven keep | Mulligan rate | Avg mulligans | Color issues | Structural placement |
|---|---:|---:|---:|---:|---:|
| conservative | 0.529 | 0.471 | 0.850 | 0.015 | 1.268 |
| curve_oriented | 0.535 | 0.465 | 0.826 | 0.023 | 1.311 |
| commander_oriented | 0.531 | 0.469 | 0.809 | 0.021 | 1.240 |
| interaction_oriented | 0.555 | 0.445 | 0.791 | 0.023 | 1.310 |
| matchup_oriented | 0.541 | 0.459 | 0.833 | 0.019 | 1.360 |
| primer_policy | 0.510 | 0.490 | 0.897 | 0.019 | 1.277 |
| current_pilot | 0.504 | 0.496 | 0.922 | 0.016 | 1.404 |
| learned_policy | 0.522 | 0.478 | 0.871 | 0.016 | 1.342 |

## Boundaries

- Hand quality is separated from complete matchup performance.
- No rule is universal or empirically proven.
- No external rules engine was used.
