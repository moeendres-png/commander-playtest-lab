# Phase 7 — Deck Optimization

## Status

Phase 7 implements a constrained, multi-objective deck-optimization layer above the deterministic Structural Simulator. It never writes a proposed variant into the canonical deck snapshots. Every numerical result remains labelled `structural_model_estimates`.

## Implemented methods

- complete cut/add swap matrix with invalid cells retained as evidence;
- constrained iterative local search;
- multi-step beam search;
- explicit and automatically generated package search;
- multi-objective Pareto-front extraction;
- paired card and package ablation;
- approximate permutation Shapley contributions with paired single-card ablation evidence;
- full proposal validation with paired comparison, holdout pods, sensitivity runs, and deterministic red-team review.

The local Function-Tool server now exposes 23 strict tools. The five new Phase-7 tools are:

- `run_local_search`;
- `run_beam_search`;
- `run_package_search`;
- `evaluate_pareto_front`;
- `estimate_shapley`.

## Hard constraints

The optimization contract checks:

- exactly 100 cards;
- singleton, except basic lands;
- Commander color identity;
- locally verified candidate inventory;
- simultaneous physical allocation through a shared candidate ledger;
- deck-specific role minima;
- land-count bounds;
- minimum colored-source counts;
- average nonland mana-value ceiling;
- maximum high-mana-value count.

Deck-specific constraints are stored in `config/phase7_optimization.json`. The local candidate ledger is `data/collections/phase7_optimization_pool.json`. It is a narrow optimization snapshot and does not replace the canonical collection.

## Optimization objectives

The Pareto layer maximizes seven separate objectives rather than collapsing them into one score:

1. four-player-pod placement improvement;
2. worst-quartile paired outcome;
3. Commander independence;
4. rebuild capacity;
5. closing power;
6. worst holdout-matchup robustness;
7. physical allocation feasibility.

## Proposal boundary

Search results are candidates, not recommendations. A proposal is eligible for confirmation only after it contains:

- a concrete cut and addition;
- structural rationale;
- affected matchup classes;
- paired baseline comparison;
- holdout tests;
- seed and pilot-strength sensitivity;
- red-team review.

Even a confirmed result is returned as `validated_not_applied`. Deck JSON, plaintext decklists, and Google Drive files are never modified by the optimizer.

## Local validation

### Automated tests

- 108 tests passed;
- one external XMage/Forge differential test remained skipped;
- no local test failed.

### Complete structural swap matrices

The matrices below enumerate all unique non-protected cut names against every locally eligible candidate. The Phase-7 smoke run performed complete constraint screening but intentionally did not simulate all cells.

| Deck | Matrix cells | Constraint-valid | Paired-simulated in smoke run |
|---|---:|---:|---:|
| Korvold | 150 | 150 | 0 |
| RogShai | 70 | 68 | 0 |

### Search-method smoke validation

- Local search, Beam Search, package search, Pareto extraction, and Shapley estimation all completed.
- The initial larger Beam Search validation exceeded the execution window. A reduced validation sample completed; production limits remain configurable.
- Search candidates were not applied.

### Full validation chains

#### Korvold: `Scouring Swarm → Idol of Oblivion`

- paired average-placement improvement: `0.0000` over four paired games;
- holdouts: `0.0000` and `−0.2500`;
- sensitivity varied from `0.0000` to `+0.2500` across seeds and pilot strengths;
- red team detected role losses in land synergy, payoff, and token production;
- decision: **rejected**.

#### RogShai: `Izzet Signet → Talisman of Creativity`

- paired average-placement improvement: `0.0000` over four paired games;
- holdouts: `0.0000` and `0.0000`;
- sensitivity ranged from `0.0000` to `+0.2500`, but the primary comparison remained neutral;
- primary paired evidence did not favor the variant;
- decision: **rejected**.

These are small deterministic smoke samples, not final deck judgments. They demonstrate that a plausible direct upgrade can still be rejected when robustness criteria fail.

## Shapley boundary

The Shapley method is an approximate structural coalition analysis. It samples seeded permutations of selected cards and combines profile marginal values with paired single-card ablation evidence. It does not claim causal real-game contribution and is not a substitute for larger paired, rules-validated, or empirical playtests.

## External gates

Phase 6's XMage/Forge differential release gate remains open. Phase-7 proposals should not be treated as final physical deck changes until later phases add:

- verified external rules-backend checks for critical interactions;
- larger holdout simulations;
- real-playtest calibration;
- final physical-inventory certification against the current canonical source.
