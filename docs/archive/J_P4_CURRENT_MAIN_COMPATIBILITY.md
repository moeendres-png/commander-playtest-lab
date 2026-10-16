# J-P4 current-main compatibility check

## Why this check exists

J-P4 started from the then-canonical P3D state `main@01c03019fdbf835441514ddfee01f4ef5945fd5a`. After development was frozen and the first/only J-P4 holdout evaluation had already completed, `main` advanced to `2a4bcda8c5ea9bc00ed769b924f0fce0c4b495aa` with a verified current Lorehold Spirit / Niko opponent integration.

The concurrent change does not modify `KorvoldPilot`, `RogShaiPilot`, either own deck identity, or the frozen J-P4 corpora. It adds current opponent data, registry/projection support, and its integration test.

## Protocol

This is a **post-holdout compatibility/sensitivity check only**. No pilot, evaluator, development corpus, holdout corpus, or frozen J-P4 runner was changed in response to the result. `holdout_tuning_violation=false` remains true by construction.

The Lorehold structural role profile was transformed with the same deterministic risk mapping used by `run_j_p4_sensitivity.py`:

- hidden-information uncertainty: `0.12`
- opponent-intent uncertainty: `0.25`
- unknown-opponent fraction: `0.0`
- boardwipe risk: `0.5285714285714286`
- commander-denial risk: `0.6`
- stack pressure: `0.08`

No opponent frequency or empirical weight was invented.

## Result

| Pilot | Cases | Preferred | Acceptable | Bad | Critical |
|---|---:|---:|---:|---:|---:|
| KorvoldPilot | 18 | 16 | 2 | 0 | 0 |
| RogShaiPilot | 19 | 18 | 1 | 0 | 0 |
| **Total** | **37** | **34** | **3** | **0** | **0** |

`current_lorehold_compatibility = PASS` under `structural_model_estimates`.

## Truth boundary

This is modeled structural decision-quality evidence, not empirical human play strength, a real win rate, or external-rules-engine evidence. P3 remains `NO_PROVIDER_READY`; no external engine was available for J-P4.
