# Mulligan Lab Usage

1. Use `sample_opening_hands` for deterministic London-mulligan draw sequences.
2. Use `evaluate_opening_hand` for one explicit current-deck hand.
3. Use `compare_mulligan_policies` for a non-persistent comparison using common random numbers.
4. Use `run_mulligan_lab` to persist results.
5. Use `generate_keep_rules` to create candidate, non-absolute rules.
6. Use `test_keep_rule` on explicit hands or holdout fixtures.
7. Use `create_mulligan_report` for a truth-boundary-labelled report.

Large runs above the configured approval threshold require `APPROVED_LARGE_RUN`.
