# Usage

1. Call `find_counterfactual_branchpoints` for a project-relative JSONL event log.
2. Inspect the returned state and replay-prefix hashes.
3. Call `list_alternative_actions` at one offset.
4. Run `run_counterfactual` using only a returned legal alternative.
5. Use `multiple_future_samples` with derived seeds for uncertainty, or `public_information_only` for a strict information boundary.
6. Compare results and generate the regret report.

`external_engine` is rejected unless a real external engine is configured. Tactical Oracle is labeled separately and never promoted to external validation.
