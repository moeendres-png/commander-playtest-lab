# Archetype and package extraction usage

Use the tool server functions:

- `extract_archetypes` for weighted role-based archetypes.
- `extract_packages` for curated packages plus conservative machine-candidate diagnostics.
- `inspect_package` for one versioned package definition.
- `compare_package_versions` for explicit package drift.
- `evaluate_package_density` for completeness, redundancy and failure modes.
- `detect_orphaned_cards` for support/payoff mismatches.
- `generate_package_report` for a human-readable report.
- Existing `run_package_ablation` accepts either explicit `card_names` or a registry `package_id`.

A package result is advisory. `automatic_deck_application` remains false.
