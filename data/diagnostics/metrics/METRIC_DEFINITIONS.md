# Diagnostic metric definitions

- `decision_regret`: non-negative model difference between the recorded action and tested legal alternatives.
- `missed_line_count`: number of recorded decision points where an evaluated stronger line was not selected.
- `dead_card_rate`: dead-in-hand observations divided by instrumented samples.
- `unplayable_rate`: non-playable observations divided by instrumented samples.
- `package_failure_rate`: deficit below the curated package completeness requirement.
- `pilot_disagreement`: normalized spread across pilots on the same deck/evidence frame.
- `counterfactual_improvement`: mean model improvement for legal alternative actions.
- `evidence_strength`: sample-size and validation-level weighted support. It is not a probability that the diagnosis is true.

All metrics are model-dependent unless explicitly cross-checked by a real external rules engine.
