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

# Phase 12.4 limitations

- Meta samples are too small within each exact format band for confirmed machine extraction.
- Co-occurrence does not prove synergy; all accepted domain packages are manually curated.
- Package status is `curated`, not `validated`.
- Structural role annotations can represent the same card differently by deck context, but they are not full card-rules proofs.
- Three-game package ablations are smoke tests only.
- No real XMage/Forge runtime was executed.
- Package evidence is evaluated through synthetic holdouts, pilot sensitivity, and rules-coverage gates; no manual-playtest dataset is used.
- No package is automatically added to a canonical deck or treated as inventory.
