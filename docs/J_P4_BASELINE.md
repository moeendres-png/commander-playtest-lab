# Roadmap J-P4 — Pre-tuning pilot baseline

Measured against the untouched `main` implementation at commit `01c03019fdbf835441514ddfee01f4ef5945fd5a` before any pilot-logic change.

## Identity

- development corpus: `J_P4_DEVELOPMENT_GOLDENS_v1`
- development SHA-256: `259cb59c70f86fe2117282c0751d218a9e9535b7121211117a1b504b81d49e78`
- cases: 37
- untouched P4 holdout SHA-256: `426e184e2dd3ade9245dd4756ee58e796841e1fa71237c3239b55ab16b0859f2`
- holdout outcomes evaluated at baseline: **false**
- Korvold deck hash: `72c0cb6a804cfb97b5cb048ca5e2b261782037044f6360b98a6b7df51c79bf1f`
- RogShai deck hash: `3827c35995e280753c4e714e391b9baf0a34e2c019e9df519ea1db0260ff9932`
- evidence class: `structural_model_estimates`
- external engine: `NO_PROVIDER_READY`; no external-rules-engine result claimed.

## Baseline result

| Pilot | Cases | Passed | Preferred | Mean class score |
|---|---:|---:|---:|---:|
| KorvoldPilot | 18 | 17 | 13 | 0.888889 |
| RogShaiPilot | 19 | 16 | 13 | 0.802632 |

The four observed strategic failures were:

1. `p4d_k_protection_reserve`: spent protection on a low-value disposable permanent instead of preserving it.
2. `p4d_r_counter_reserve`: countered harmless value instead of reserving interaction in a high-uncertainty five-player window.
3. `p4d_r_independent_axis_denial`: recast heavily taxed Ishai despite established extreme commander denial instead of developing the independent Veyran axis.
4. `p4d_r_five_player_exposure`: cast Ishai with zero reserve into four hostile response windows instead of holding interaction.

Existing legacy pilot/unit/golden regression at the same baseline: `21 passed` for `tests/unit/test_pilots.py`, `tests/golden/test_g_decision_quality.py`, and `tests/golden/test_phase6_golden.py`.

## Truth boundary

This measures modeled decision quality inside the structural pilot model. It is not empirical human skill and not a real win rate. Political visibility is an explicit heuristic only; no human social behavior is claimed.
