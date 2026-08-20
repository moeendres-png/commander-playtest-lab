# Operational Simulation Policy

Current policy effective 2026-08-20:

- The Commander Playtest Lab operational simulation target is **4-player Commander only**.
- 3-player and 5-player pod sensitivity are out of scope and must not be scheduled, calculated, or used as readiness/robustness gates.
- Project-level tournament/robustness configuration and structural self-play fail closed unless `pod_sizes == (4,)`.
- Generic low-level StructuralSimulator capability may remain for isolated technical engine-correctness tests; it is not an operational 3P/5P simulation path.
- Historical 3P/5P references or artifacts are provenance only, not current evidence requirements.
- Useful robustness axes remain within 4P: opponent composition, pilot/mulligan policy, seat position, commander denial, ablation, worst case, rebuild, protection, interaction, and finish structure.
- Structural results remain `structural_model_estimates`, not empirical win rates.
- This policy does not mutate canonical deck lists, inventory, purchases, opponent truth, or physical allocations.
