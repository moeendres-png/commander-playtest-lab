# Commander Playtest Lab — Model Precision Policy CURRENT

**Status:** frozen for next fresh RogShai optimization campaign  
**Effective:** 2026-08-20  
**Operational pod size:** 4 players only  
**Evidence class:** `structural_model_estimates`

## 1. Retired model-resolution hard gate

The former single hard gate `effective_resolution = max(calibrated_sesoi, independent_same-model_seed-block_range)` is retired for candidate promotion, elimination and equivalence decisions. The historical value `0.375` and the four-block range remain diagnostic provenance only; neither is an intrinsic Structural Model resolution floor.

## 2. SESOI is separate from precision

`SESOI = 0.05 average placement positions`.

SESOI is the minimum practical deck-decision effect. It is not Model Precision and is not inflated by seed-block, seat, opponent or pilot variation.

## 3. 2F hybrid precision contract

Confirmatory inference combines four preregistered components instead of one scalar resolution number:

1. **sequential paired 4P budgets:** `128 → 256 → 512 → 1024 → 2048`;
2. **multiplicity-adjusted paired confidence interval** across the frozen shortlist and five planned looks;
3. **MCSE gate:** `MCSE <= 0.025` for promotion;
4. **within-partition seed stability:** four deterministic interleaved seed blocks, all block means `>= -0.05`, and maximum block deviation from the pooled mean `<= max(0.10, 4 × MCSE)`.

The seed-block condition is `PRECISION_ONLY_SAME_MODEL`; it is not real-world replication or opponent-input validation.

## 4. Shortlist multiplicity

Before confirmatory evidence is opened, exploratory QD evidence freezes at most **8** candidates. Search `robust_lower_bound` and QD cell quality are discovery/shortlisting heuristics only.

For a frozen shortlist of size `K`, family alpha is `0.05` across all `5 × K` planned candidate-look decisions:

`alpha_candidate_look = 0.05 / (5 × K)`

The corresponding two-sided decision confidence is `1 - alpha_candidate_look`. This is fixed from shortlist size before confirmatory evaluation and cannot be selected after seeing confirmatory outcomes.

## 5. Sequential decision rules

At each planned look:

- clear harm: interval upper bound `< 0` → `REJECT_HARM`;
- from `n >= 1024`, inability to reach practical relevance: interval upper bound `< +0.05` → `FUTILITY_BELOW_SESOI`;
- interval lower bound `> +0.05` can become `PROMOTION_CANDIDATE` only if MCSE, seed stability, broad 4P robustness and semantic-fidelity gates also pass;
- otherwise continue to the next preregistered look;
- unresolved at `2048` → `PRECISION_LIMIT`, `BLOCKED_PRECISION`, `BLOCKED_ROBUSTNESS`, or `BLOCKED_SEMANTIC_FIDELITY` as appropriate. No result is forced to WIN/LOSE.

## 6. 4P robustness remains separate

Broad strata are pilot policy, own seat and per-opponent exposure. Promotion requires complete broad-stratum coverage and no broad-stratum mean worse than one SESOI (`-0.05`). Exact opponent triples remain diagnostics and are never converted into invented local-frequency weights.

Commander-denial and package-ablation use a separate fresh diagnostics partition after confirmatory finalist selection and before holdout. These are synthetic Structural stress tests, not observations.

## 7. Pareto and single challenger

Candidates that pass confirmatory gates are compared on a multidimensional Pareto surface. No universal weighted card/deck score is introduced. If multiple candidates remain non-dominated, a preregistered lexicographic tie-break uses, in order: worst broad stratum, paired effect, precision, semantic support, fewer changed slots, stable deck hash. Exactly one challenger may proceed to critical diagnostics and then holdout.

## 8. Final sealed holdout

The final holdout is not sequential:

- exactly one challenger is frozen before opening;
- exactly `2048` paired 4P scenarios;
- one planned evaluation;
- two-sided 95% interval;
- winner requires holdout lower bound `> +0.05`, complete broad 4P robustness, and a passing frozen critical-diagnostics report;
- otherwise `NO_WINNER`.

The consumed historical Optimizer-v2 holdout is never reused.

## 9. Evidence boundary

This contract governs Structural decision precision only. It does not create empirical Commander winrates, independent real-world replication, Tactical Oracle evidence or external-rules-engine evidence.
