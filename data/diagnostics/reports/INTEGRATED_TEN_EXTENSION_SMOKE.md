# Integrated ten-extension smoke

Status: `passed_with_limitations`
Passed steps: 10/10

| Step | Name | Validation level | Result |
|---:|---|---|---|
| 1 | load_meta_source | `source_fact` | loaded meta snapshot meta-2026-08-05-phase12-1 |
| 2 | compile_primer_rule | `curated_project_rule` | compiled 7 rules |
| 3 | select_multiple_pilots | `structural_model_estimates` | KorvoldPilot, KorvoldValuePilot, KorvoldSacrificePilot |
| 4 | analyze_packages | `curated_project_package` | loaded 10 Korvold package records |
| 5 | trace_provenance | `provenance_verified` | graph commander-playtest-lab-provenance-1.5.0 contains 7 sources |
| 6 | load_local_opponent_profile | `insufficient_real_data` | real observations: 0 |
| 7 | simulate_opponent_ensemble | `structural_model_estimates` | validated 4 variants |
| 8 | apply_mulligan_policy | `structural_model_estimates` | compared 8 policies |
| 9 | run_counterfactual_replay | `structural_counterfactual` | chosen_model_preferred |
| 10 | diagnose_failure_cause | `model_diagnosis` | insufficient_evidence |

Every step stores source paths and SHA-256 hashes. No external engine, canonical deck change, inventory change or allocation change occurred.
