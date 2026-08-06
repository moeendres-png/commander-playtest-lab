# Mulligan Lab usage — completion revision 1.10.1

1. `sample_opening_hands` streams deterministic London-mulligan draw sequences; commanders are excluded from the library.
2. `evaluate_opening_hand` evaluates an explicit hand against a deckhash-bound policy and context.
3. `compare_mulligan_policies` uses Common Random Numbers for the eight supported policies.
4. `run_mulligan_lab` separates cheap hand-quality sampling from complete Structural Simulator follow-up games.
5. `generate_keep_rules` creates only model-based candidate rules.
6. The generated candidate is actually checked in the primary pod, two holdout pods, an opponent ensemble and three pilot profiles.
7. `test_keep_rule` evaluates a rule against an explicit hand; `create_mulligan_report` preserves uncertainty and validation labels.

Context includes deck version/hash, opponent ensemble, seat, starting player, pod size, pilot profile and intended game plan. Runs above the configured approval threshold require `APPROVED_LARGE_RUN`. The streaming sampler supports millions of cheap hands without materializing all samples in memory.
