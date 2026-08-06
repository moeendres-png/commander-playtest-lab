# Decision Diagnostics limitations — completion revision 1.10.1

- The classifier is an explainable heuristic, not a causal estimator.
- Event-derived counters are Structural Simulator observations, not real games.
- Dead/unplayable classification uses the final structural state and role/mana approximations.
- Zero real imported games means no empirical local-meta validation is available.
- Tactical Oracle is not an external rules engine.
- Synthetic known-cause fixtures verify uncertainty behavior but not real-world accuracy.
- `model_supported_cut_candidate` is not an automatic cut or validated upgrade.
