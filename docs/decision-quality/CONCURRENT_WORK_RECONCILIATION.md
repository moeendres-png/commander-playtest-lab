# Decision Quality – Concurrent Work Reconciliation

## Audit timestamp

- Local project audit: `2026-08-15 16:03 CEST`
- Stable GitHub main at audit: `256f3a1b418afef274a98e6dfdbed3d26bcc28ad`
- Stable tree: `07a045c3aa8b57999ba533c5d759add53fd60a51`
- Stable package: `1.21.0`
- Structural engine: `structural-0.6.0`
- Optimizer-v2 PR: `#69`, merged to main
- Open pull requests at audit: none

## Concurrency decision

`IMPLEMENTATION_GATE = OPEN_AFTER_OPTIMIZER_V2_BASELINE`

The Decision Quality work starts only after the adaptive Optimizer-v2 refactor was merged and its
final PR-head gates completed successfully. This branch therefore extends the accepted v2 baseline
rather than re-implementing or competing with it.

## Optimizer-v2 components that are reused

The following are explicitly **reused and not duplicated**:

- exploratory / calibration / confirmatory / sealed-holdout evidence partitions;
- adaptive whole-deck search and QD / archive behavior;
- racing and adaptive simulation budgets;
- policy/operator learning with exploration floors;
- deterministic run identity, cache, locks, checkpoints, resume and sharding;
- frontier handoff and semantic review queue;
- pilot and Mulligan sensitivity infrastructure;
- near-frontier commander-denial, matchup, ablation, mana, finish and counterfactual diagnostics;
- synthetic decision calibration and legal-deck face-validity calibration;
- confirmatory and explicitly authorized holdout runners.

The new work supplies epistemic gates around these existing execution capabilities. It does not
create a second optimizer or a second evidence-partition implementation.

## New integration responsibilities

Version `1.22.0` adds or tightens:

1. domain/input validity before strong local-matchup inference;
2. evidence-bounded opponent ambiguity sets with no invented probability weights;
3. question-specific Structural Fidelity classes;
4. Model Information Limit before effect/equivalence decisions;
5. Model Resolution that requires measured Structural-model variability in addition to synthetic
   calibration;
6. same-model seedblock classification as precision evidence, not independent replication;
7. resource-to-closure diagnostics with unsupported telemetry marked explicitly;
8. experiment evidence-target semantics (`CUT`, `ADD`, `REPLACEMENT`, `PACKAGE`,
   `CONDITIONAL_EFFECT`, `INTERACTION`);
9. multi-axis robust decision integration without a universal super-score;
10. fail-closed StructuralDeckProfile commander representation and production 100-profile
    Commander-deck validation.

## Research rationale

The implementation follows established simulation-methodology distinctions:

- input uncertainty is distinct from Monte Carlo uncertainty and cannot be removed merely by more
  simulation replications;
- robust ranking/selection can reason over ambiguity sets of plausible inputs rather than a single
  point-estimated input;
- verification, validation and uncertainty quantification are distinct evidence questions;
- adaptive exploratory evidence must remain separate from confirmatory and holdout evidence.

Relevant methodology includes Wu, Wang & Zhou (Operations Research 2024,
DOI `10.1287/opre.2022.2375`), Chick (Management Science 2001,
DOI `10.1287/mnsc.47.6.742.9814`), distributionally robust selection work in Management Science,
and NIST verification/validation/UQ guidance. These references motivate evidence boundaries; they
do not provide empirical Commander effect sizes.

## Protected-state reconciliation

This refactor is software/governance work only.

- `NEW_ROGSHAI_OPTIMIZER_RUN_STARTED = false`
- `CANONICAL_ROGSHAI_CHANGED = false`
- `INVENTORY_CHANGED = false`
- `PHYSICAL_ALLOCATION_CHANGED = false`
- `PURCHASE_DECISION_CHANGED = false`
- `OPPONENT_OBSERVATION_EVIDENCE_CHANGED = false`
- `KAERVEK_CHANGED = false`
- `FIRST_OFFICIAL_ROGSHAI_OPTIMIZER_V2_CAMPAIGN = NOT_RUN`

Public deck/archetype data may later be used only as `external_archetype_prior` scenario provenance.
It must never be promoted to direct local opponent observation.
