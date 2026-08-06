# Overall status of extensions 12.1–12.10

| Phase | Capability | Original release | Current status | Completion revision |
|---:|---|---:|---|---:|
| 12.1 | Meta Knowledge Base | 1.1.0 | `meta_knowledge_base_ready_with_limitations` | 1.10.1 verified |
| 12.2 | Primer-to-Pilot Compiler | 1.2.0 | `primer_compiler_ready_with_limitations` | 1.10.1 verified |
| 12.3 | Multi-Pilot Ensembles | 1.3.0 | `multi_pilot_system_ready_with_limitations` | 1.10.1 executed in smoke |
| 12.4 | Archetype and Package Extraction | 1.4.0 | `package_extraction_ready_with_limitations` | 1.10.1 executed in smoke |
| 12.5 | Full Provenance | 1.5.0 | `provenance_ready_with_limitations` | 1.10.1 executed trace |
| 12.6 | Local Meta Learning | 1.6.0 | `local_meta_learning_ready_with_insufficient_data` | 0 real games |
| 12.7 | Opponent Ensembles | 1.7.0 | `opponent_ensembles_ready_with_limitations` | 1.10.1 executed sensitivity |
| 12.8 | Mulligan Lab | 1.8.0 | `mulligan_lab_ready_with_limitations` | 1.10.1 completed |
| 12.9 | Counterfactual Replay | 1.9.0 | `counterfactual_replay_ready_with_limitations` | 1.10.1 completed |
| 12.10 | Decision Diagnostics | 1.10.0 | `decision_diagnostics_ready_with_limitations` | 1.10.1 completed |

## Prioritized open functions

1. Import and calibrate a meaningful real-game dataset; current real imported game count is zero.
2. Configure and execute real XMage or Forge differential validation.
3. Validate Mulligan and diagnostic policies on real holdout games and larger paired Structural batches.
4. Capture external-engine executable states for stronger rules-complete counterfactual branches.
5. Learn opponent-ensemble weights from observations.
6. Increase same-format reference-deck samples before validating machine-extracted packages.
7. Improve politics, threat perception and multiplayer negotiation abstractions.

No open item is reported as completed or empirically validated.
