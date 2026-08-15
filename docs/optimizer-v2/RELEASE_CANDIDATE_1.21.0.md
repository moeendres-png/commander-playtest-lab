# RogShai Optimizer v2 – 1.21.0 Release Candidate

This document records the technical acceptance contract for the adaptive Whole-Deck Optimizer v2. It is implementation documentation, not canonical deck or inventory state and not gameplay evidence.

## Evidence partitions

A release manifest freezes four mutually disjoint partitions:

1. `exploratory` – adaptive search, racing, policy/operator learning and near-frontier diagnostics.
2. `calibration` – synthetic known-direction calibration plus legal real-deck face-validity stress checks.
3. `confirmatory` – fresh finalist evaluation after the frontier is frozen; no search learning.
4. `holdout` – sealed final evaluation, inaccessible without explicit holdout authorization and never used for tuning.

All paired simulation evidence produced by these paths is classified as `structural_model_estimates`. Counterfactual structural replay remains structural-model evidence; no external rules-engine evidence is claimed unless a real external engine is separately executed and validated.

## Release-candidate production paths

`commander-lab-optimizer` provides manifest, preflight, exploratory run, confirmatory and explicitly authorized holdout commands. The exploratory run produces a manifest-bound frontier handoff, decision-weighted semantic review queue, near-frontier diagnostic report, calibration report and execution audit. The production evaluator uses the existing exact-result cache and records requested/executed scenario pairs, cache hits/misses/stores, skipped illegal candidates, failures, retries, requested workers and deterministic shard counts.

Early sensitivity is outcome-independent. Pilot assignment is frozen by scenario parity and Mulligan sensitivity uses shared deterministic draw sequences across `current_pilot`, `conservative` and `interaction_oriented` policies.

## Governance

Optimizer v2 does not automatically mutate the canonical RogShai deck, inventory quantities, physical allocations, purchase decisions, opponent observation evidence or the frozen Kaervek opponent. Semantic unknowns remain fail-closed until separately verified. Theorycraft candidates create no permanent card reservation.

The technical benchmark is not an official RogShai winner campaign. It must not consume confirmatory or holdout evidence and may not declare an official winner. The sealed holdout runner requires explicit authorization after a manifest-bound confirmatory report exists.

## Acceptance gates

Readiness requires all of the following on the final release head:

- Ruff lint and formatting, strict mypy, targeted Optimizer-v2 tests and the full repository CI;
- J-P6, J-FINAL, Windows Runtime Hygiene and release-artifact workflows;
- deterministic worker-count equivalence and exact cache fresh-vs-hit equivalence;
- four-way partition disjointness and fail-closed manifest/preflight checks;
- actual legal-deck face-validity calibration in the isolated calibration partition;
- full frontier handoff, semantic review queue and near-frontier diagnostic artifacts;
- technical Legacy-vs-v2 A/B demonstrating a material benefit without governance regression;
- no canonical state mutation and no holdout use for search/tuning.

`OPTIMIZER_V2_READY=true` may only be reported after those gates have actually completed successfully.