# Integrated ten-extension smoke 1.10.1

Status: `passed_with_limitations`
Passed steps: 10/10

| Step | Name | Validation level | Result |
|---:|---|---|---|
| 1 | load_meta_source | `source_fact` | loaded and schema-validated meta-2026-08-05-phase12-1 |
| 2 | compile_primer_rule | `curated_project_rule` | compiled 7 validated rules |
| 3 | select_multiple_pilots | `structural_model_estimates` | executed 3 legal-action pilot games; placements={'KorvoldPilot': 1, 'KorvoldValuePilot': 1, 'KorvoldSacrificePilot': 1} |
| 4 | analyze_packages | `curated_project_package` | evaluated 9 curated packages; machine candidates remain unconfirmed |
| 5 | trace_provenance | `provenance_verified` | traced derived-diagnostic-dataset-v1.10.1 through 7 retained records |
| 6 | load_local_opponent_profile | `insufficient_real_data` | real observations remain 0; no missing values inferred |
| 7 | simulate_opponent_ensemble | `structural_model_estimates` | executed 4 variants; worst=-0.2956, spread=0.0303 |
| 8 | apply_mulligan_policy | `structural_model_estimates` | executed 8 policies plus validation contexts ['holdout_pod', 'opponent_ensemble', 'pilot_profile', 'primary_pod'] |
| 9 | run_counterfactual_replay | `structural_counterfactual` | executed 4 futures; chosen_model_preferred; mean=-17.5305 |
| 10 | diagnose_failure_cause | `model_diagnosis` | executed event-derived diagnosis for Korvold, Fae-Cursed King: insufficient_evidence; cut_gate=blocked:sample_too_small,holdout_not_confirmed,diagnosis_not_deck_or_card_weakness |

Every step was executed in this run and stores source paths plus SHA-256 hashes.
No external rules engine was used.
