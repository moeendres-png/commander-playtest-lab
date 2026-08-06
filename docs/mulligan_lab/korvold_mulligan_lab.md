# Korvold Mulligan Lab 1.10.1

Status: `mulligan_lab_ready_with_limitations`

All keep rules and placement values are model-based Structural estimates, not absolute rules or empirical win rates.

| Policy | First-seven keep | Mulligan rate | Avg. mulligans | Color issues | Full follow-ups | Avg. placement |
|---|---:|---:|---:|---:|---:|---:|
| `conservative` | 0.758 | 0.242 | 0.314 | 0.046 | 4/4 | 1.250 |
| `curve_oriented` | 0.756 | 0.244 | 0.316 | 0.046 | 4/4 | 1.000 |
| `commander_oriented` | 0.742 | 0.258 | 0.350 | 0.050 | 4/4 | 1.500 |
| `interaction_oriented` | 0.748 | 0.252 | 0.336 | 0.048 | 4/4 | 1.500 |
| `matchup_oriented` | 0.760 | 0.240 | 0.322 | 0.050 | 4/4 | 1.250 |
| `primer_policy` | 0.716 | 0.284 | 0.394 | 0.050 | 4/4 | 1.500 |
| `current_pilot` | 0.726 | 0.274 | 0.384 | 0.050 | 4/4 | 1.000 |
| `learned_policy` | 0.758 | 0.242 | 0.328 | 0.050 | 4/4 | 1.750 |

## Overfitting checks

- Executed validation contexts: 7
- Context kinds: holdout_pod, opponent_ensemble, pilot_profile, primary_pod
- Supported contexts: 5/7
- Primary pod, two holdouts, one opponent ensemble and three pilot profiles were actually executed.

## Boundaries

- Full follow-ups use the Structural Simulator with a forced public opening hand.
- No Tactical Oracle or external rules engine was used for complete games.
- No deck list, inventory or allocation was changed.
