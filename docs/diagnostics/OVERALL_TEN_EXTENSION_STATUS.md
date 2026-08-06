# Overall status of extensions 12.1–12.10

| Phase | Capability | Version | Status |
|---:|---|---:|---|
| 12.1 | Meta Knowledge Base | 1.1.0 | `meta_knowledge_base_ready_with_limitations` |
| 12.2 | Primer-to-Pilot Compiler | 1.2.0 | `primer_compiler_ready_with_limitations` |
| 12.3 | Multi-Pilot Ensembles | 1.3.0 | `multi_pilot_system_ready_with_limitations` |
| 12.4 | Archetype and Package Extraction | 1.4.0 | `package_extraction_ready_with_limitations` |
| 12.5 | Full Provenance | 1.5.0 | `provenance_ready_with_limitations` |
| 12.6 | Local Meta Learning | 1.6.0 | `local_meta_learning_ready_with_insufficient_data` |
| 12.7 | Opponent Ensembles | 1.7.0 | `opponent_ensembles_ready_with_limitations` |
| 12.8 | Mulligan Lab | 1.8.0 | `mulligan_lab_ready_with_limitations` |
| 12.9 | Counterfactual Replay | 1.9.0 | `counterfactual_replay_ready_with_limitations` |
| 12.10 | Decision Diagnostics | 1.10.0 | `decision_diagnostics_ready_with_limitations` |

## Prioritized open functions

1. Import and calibrate a meaningful real-game dataset; current real imported game count is zero.
2. Configure and execute real XMage or Forge differential validation.
3. Increase same-format reference-deck samples before validating machine-extracted packages.
4. Capture complete executable replay states and legal-action transitions for stronger counterfactuals.
5. Learn opponent-ensemble weights from observations rather than leaving them unweighted.
6. Validate Mulligan and diagnostic policies on holdout real games and larger paired simulations.
7. Improve politics, threat perception and multiplayer negotiation abstractions.

No item above is reported as completed or empirically validated.
