# Commander Playtest Lab — Model Precision Policy CURRENT

**Status:** frozen for next fresh RogShai optimization campaign  
**Effective:** 2026-08-20  
**Operational pod size:** 4 players only  
**Evidence class:** `structural_model_estimates`

## 1. Retired model-resolution hard gate

The former single hard gate based on

`effective_resolution = max(calibrated_sesoi, independent_same-model_seed-block_range)`

is retired for candidate promotion, elimination and equivalence decisions.

The historical value `0.375` was dominated by a low sampling budget and is not treated as an intrinsic Structural Model resolution floor. The four-block range remains diagnostic provenance only.

Historical calibration evidence:

| games per independent seed block | historical range-derived value | block-mean MCSE |
|---:|---:|---:|
| 56 | 0.375000 | 0.068400 |
| 112 | 0.142857 | 0.026786 |
| 224 | 0.093750 | 0.018841 |
| 448 | 0.113839 | 0.020251 |

The non-monotone 224→448 range confirms that four-block range is itself an unstable hard threshold.

## 2. SESOI and precision are separate

`SESOI = 0.05 average placement positions`.

SESOI means the minimum effect considered practically relevant for a deck decision. It is not Model Precision and is not inflated by seed-block range, seat sensitivity, opponent sensitivity, pilot sensitivity, or other robustness axes.

## 3. Model Precision

There is no single scalar `MODEL_RESOLUTION` used as a universal hard gate. Precision is represented as a budget-dependent precision curve and reported with:

- paired effect interval;
- bootstrap uncertainty;
- MCSE / Monte-Carlo uncertainty where supported;
- independent same-model seed-block diagnostics;
- outcome/tie compression diagnostics.

Independent same-model seed blocks are `PRECISION_ONLY_SAME_MODEL`. They do not resolve opponent-input uncertainty or model discrepancy.

## 4. Sequential confirmatory sampling — policy 2E

Planned paired 4P looks:

`128 → 256 → 512 → 1024 → 2048`

The five looks are preregistered. Family error target is 0.05; a conservative Bonferroni allocation uses `alpha = 0.01` per look, corresponding to a two-sided 99% interval at each planned look.

Decision rules at each planned look:

- `PROMOTION_CANDIDATE` if interval lower bound `> +0.05`, subject to all 1E robustness/semantic/Pareto gates;
- `REJECT_HARM` if interval upper bound `< 0`;
- from `n >= 1024`, `FUTILITY_BELOW_SESOI` if interval upper bound `< +0.05`;
- otherwise `MORE_SAMPLES` until the preregistered ceiling;
- at the ceiling, unresolved candidates are `PRECISION_LIMIT`, never forced to WIN/LOSE.

## 5. Final sealed holdout

The final holdout is not sequential.

- exactly one challenger is frozen before holdout opening;
- `2048` paired 4P scenarios;
- one planned evaluation;
- two-sided 95% interval;
- final winner requires holdout lower bound `> +0.05` and every frozen critical robustness gate to pass;
- otherwise `WINNING_VARIANT = NONE`.

The consumed first Optimizer-v2 holdout is never reused.

## 6. Robustness is not precision

Seat position, opponent composition, pilot/mulligan policy, commander denial, ablation, rebuild, protection, interaction, finish and worst-case sensitivity remain separate 4P robustness axes.

For broad sufficiently populated seat/opponent/pilot strata, a point-estimate degradation worse than one SESOI (`-0.05`) is a preregistered robustness warning/blocking threshold for the 1E final decision path. Exact opponent triples remain diagnostics; no opponent-frequency probabilities are invented.

## 7. Truth boundary

This policy governs Structural decision precision only. It does not create empirical Commander winrates, real-world replication, Tactical Oracle evidence, or external-rules-engine evidence.
