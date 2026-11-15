# Rogshai Mulligan Lab 1.10.1

Status: `mulligan_lab_ready_with_limitations`

All keep rules and placement values are model-based Structural estimates, not absolute rules or empirical win rates.

| Policy | First-seven keep | Mulligan rate | Avg. mulligans | Color issues | Full follow-ups | Avg. placement |
|---|---:|---:|---:|---:|---:|---:|
| `conservative` | 0.586 | 0.414 | 0.676 | 0.018 | 4/4 | 3.000 |
| `curve_oriented` | 0.606 | 0.394 | 0.632 | 0.028 | 4/4 | 2.250 |
| `commander_oriented` | 0.618 | 0.382 | 0.574 | 0.030 | 4/4 | 2.500 |
| `interaction_oriented` | 0.608 | 0.392 | 0.622 | 0.032 | 4/4 | 2.750 |
| `matchup_oriented` | 0.598 | 0.402 | 0.670 | 0.022 | 4/4 | 1.750 |
| `primer_policy` | 0.572 | 0.428 | 0.720 | 0.018 | 4/4 | 2.500 |
| `current_pilot` | 0.544 | 0.456 | 0.780 | 0.014 | 4/4 | 2.500 |
| `learned_policy` | 0.568 | 0.432 | 0.726 | 0.020 | 4/4 | 2.500 |

## Overfitting checks

- Executed validation contexts: 7
- Context kinds: holdout_pod, opponent_ensemble, pilot_profile, primary_pod
- Supported contexts: 5/7
- Primary pod, two holdouts, one opponent ensemble and three pilot profiles were actually executed.

## Boundaries

- Full follow-ups use the Structural Simulator with a forced public opening hand.
- No Tactical Oracle or external rules engine was used for complete games.
- No deck list, inventory or allocation was changed.
