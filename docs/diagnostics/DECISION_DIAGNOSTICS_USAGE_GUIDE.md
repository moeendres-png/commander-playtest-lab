# Decision Diagnostics usage — completion revision 1.10.1

1. Produce immutable Structural event logs with event capture enabled.
2. Build a `DiagnosticDataset` with `DiagnosticInstrumentationCollector`; source SHA-256 hashes are retained.
3. Run `diagnose_card_performance` and `diagnose_pilot_behavior` separately.
4. Compare deck, pilot, opponent, action and seed effects using identical evidence frames.
5. Inspect evidence, counterevidence, package dependency, counterfactual consistency and the cut release gate.
6. Run the recommended next experiment while any gate is blocked.
7. Treat `model_supported_cut_candidate` only as permission for a paired replacement test, never as an automatic cut.

The former Phase 12 generator was retired with the superseded own-deck baselines. The retained
diagnostic artifacts are historical evidence only; no tool changes a canonical deck automatically.
