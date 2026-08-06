# Phase 12.10 – Deck, pilot and model diagnostics

Status: `decision_diagnostics_ready_with_limitations`

The diagnostic layer records per-card usage, compares pilots/decks/opponent ensembles/counterfactual actions, classifies ten failure causes, exposes model-dependent regret metrics, and enforces a conservative release gate before a card can become a model-supported cut candidate.

The integrated smoke executes all ten extension stages with source hashes and validation levels. No external engine was used and no diagnosis is presented as empirical proof.
