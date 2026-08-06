# Deck, Pilot and Model Diagnostics

All diagnoses are model-dependent unless an explicit empirical validation level is listed.

## WeakPilot

- Hypothesis: `pilot_does_not_recognize_line`
- Confidence: 0.590
- Cut gate: `blocked:pilot_error_or_style_not_excluded,alternative_line_improves,holdout_not_confirmed,diagnosis_not_deck_or_card_weakness`
- Next test: `add_golden_line_and_retest_same_deck_across_pilots`

## Weak Card

- Hypothesis: `genuine_deck_construction_issue`
- Confidence: 0.688
- Cut gate: `model_supported_cut_candidate`
- Next test: `paired_replacement_test_with_role_coverage_gate`

## Support Card

- Hypothesis: `package_is_incomplete`
- Confidence: 0.590
- Cut gate: `blocked:package_incomplete,holdout_not_confirmed,diagnosis_not_deck_or_card_weakness`
- Next test: `restore_or_ablate_the_complete_package_before_judging_single_cards`

## Test Card

- Hypothesis: `opponent_model_is_wrong`
- Confidence: 0.590
- Cut gate: `blocked:package_dependency_unchecked,opponent_assumptions_fragile,counterfactuals_inconclusive,holdout_not_confirmed,diagnosis_not_deck_or_card_weakness`
- Next test: `collect_observed_opponent_constraints_and_rebuild_ensemble`

## Test Card

- Hypothesis: `random_variance`
- Confidence: 0.590
- Cut gate: `blocked:package_dependency_unchecked,seed_sensitivity_high,counterfactuals_inconclusive,holdout_not_confirmed,diagnosis_not_deck_or_card_weakness`
- Next test: `increase_paired_seed_count_and_report_interval`

## Test Card

- Hypothesis: `simulation_abstraction_is_wrong`
- Confidence: 0.720
- Cut gate: `blocked:package_dependency_unchecked,counterfactuals_inconclusive,holdout_not_confirmed,diagnosis_not_deck_or_card_weakness`
- Next test: `repair_structural_abstraction_and_repeat_tactical_or_real_validation`

## Boundaries

- No automatic deck changes.
- No model diagnosis is presented as empirical proof.
- External engine validation was not used.
