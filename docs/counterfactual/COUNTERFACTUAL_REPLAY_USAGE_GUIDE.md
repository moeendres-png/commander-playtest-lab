# Counterfactual Replay usage — completion revision 1.10.1

1. Run `find_counterfactual_branchpoints` on a project-local JSONL event log.
2. Verify the returned event offset, replay-prefix hash and state hash.
3. Use `list_alternative_actions`; only actions marked legal may be evaluated.
4. Select a hidden-information mode: same realized future, resampled unknown future, multiple future samples, or public information only.
5. Use `structural` for role-level state deltas. Use `tactical_oracle` only when both recorded actions contain a supported tactical primitive and input.
6. Use `compare_counterfactuals`, `generate_decision_regret_report`, and `export_minimal_counterfactual_fixture` for comparison and regression evidence.

`external_engine` is rejected unless a real external engine is configured. Tactical Oracle is local tactical evidence, not XMage or Forge.
