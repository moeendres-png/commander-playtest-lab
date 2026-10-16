# J-P4 CI hygiene attestation

This hygiene pass happened after the first and only intended holdout evaluation solely because CI reported Ruff hygiene failures. It was not selected from, tuned to, or justified by holdout outcomes.

## Exact diagnosed changes

- `scripts/run_j_p4_sensitivity.py`: removed one unused `collections.defaultdict` import (`F401`) and applied Ruff-only line wrapping.
- `tests/golden/test_j_p4_pilot_quality.py`: rewrote the mathematically equivalent set relation `REQUIRED_DIMENSIONS <= covered` as `covered >= REQUIRED_DIMENSIONS` (`SIM300`) and applied Ruff-only line wrapping.
- `src/commander_lab/agents/pilots.py`: Ruff-only line wrapping. No decision expression, constant, branch, action score, metadata lookup, threshold, weight, or heuristic was changed.

## Holdout integrity

The hygiene workflow computed a normalized Python AST fingerprint of `src/commander_lab/agents/pilots.py` before and after formatting and required exact equality before it could commit. That equality gate passed. The historical pre-format raw pilot SHA-256 remains `a8a262ab91d42a7d38de79630cf5a1711878ecaf943c59361524c5474980bc39`; its later byte change is formatting-only provenance, not decision-logic tuning.

The holdout corpus bytes were not changed, the holdout was not rerun, and no development/holdout action-class expectation was modified after the first holdout result.

Therefore:

```text
holdout_tuning_violation = false
post_holdout_change_class = ci_hygiene_only
pilot_decision_semantics_changed = false
holdout_rerun = false
```
