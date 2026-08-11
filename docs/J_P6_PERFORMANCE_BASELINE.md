# J-P6 Performance Baseline

Evidence class: technical runtime measurements. Simulation outputs remain `structural_model_estimates`.

## Frozen baseline

- J-P5 canonical baseline: `0d5dbc633d0776f72e80e271e52234018e80e307`
- baseline tree: `169fee0f88b550f5897324b14451b1086c0b3617`
- package: `1.15.0`
- benchmark policy: `config/J_P6_BENCHMARK_POLICY_v1.json`
- runner: GitHub-hosted `ubuntu-latest`, Python 3.12.13, 4 logical CPUs
- performance run: `31450047116`
- raw artifact: `9086012106`
- raw artifact digest: `sha256:8e511c5fd07bbe055c49b3f3f9437b412e45ba8284f3c324edc6b14e71bc1009`

Each benchmark was repeated three times except service initialization, which used five repetitions. Medians below are not empirical game-performance claims.

| Benchmark | Median wall s | Median CPU s | Max RSS KiB |
|---|---:|---:|---:|
| service initialization | 0.1182 | 0.1182 | 76,468 |
| goldfish 50, 1 worker | 0.8946 | 0.8190 | 83,512 |
| matchup 32, requested 1 worker | 3.9914 | 3.9314 | 86,316 |
| matchup 32, requested 2 workers | 4.0267 | 3.9671 | 86,352 |
| matchup 64, requested 1 worker | 7.8069 | 7.7027 | 86,352 |
| matchup 64, requested 2 workers | 5.3270 | 0.0844 parent CPU | 86,792 |
| paired comparison, 8 | 0.0280 | 0.0203 | 86,824 |
| card ablation, 4 | 0.9377 | 0.9233 | 86,848 |
| package ablation, 4 | 0.9621 | 0.9473 | 86,848 |
| commander denial, 4 | 1.0111 | 0.9964 | 86,976 |
| sensitivity smoke | 0.3708 | 0.3404 | 87,036 |
| bounded local search | 0.0533 | 0.0394 | 87,036 |
| report generation | 0.0538 | 0.0402 | 87,036 |
| 1,000 serializations | 0.7655 | 0.7655 | 87,036 |
| 10,000 card lookups | 0.00108 | 0.00109 | 87,036 |
| SQLite 1,000 write/read rows | 0.00574 | 0.00216 | 87,036 |

## Measured bottleneck assessment

The material runtime cost is structural multiplayer simulation. At 64 games, requesting two workers reduced median wall time from 7.8069 s to 5.3270 s, approximately 31.8%. At 32 games, requesting two workers did not improve runtime because the existing scheduler correctly avoids process-pool overhead for undersized batches.

This confirms the existing measured-evidence scheduler rather than justifying a new scheduler. No new caching, database, card-lookup, or serialization infrastructure is justified by the measured profile:

- card lookup cost is negligible at the measured scale;
- SQLite registry-style access is negligible at the measured scale;
- service startup and reporting are small relative to simulation;
- serialization is measurable but was not shown to dominate an end-to-end decision workflow.

Therefore J-P6 does **not** add speculative performance infrastructure. Performance changes are retained only when they exceed the predeclared 5% improvement threshold and pass semantic/deterministic/decision-quality/holdout regression gates.

## Existing worker-scaling conclusion

The existing workload threshold and effective-worker calculation remain the preferred production behavior. J-P6 treats this as validated current performance behavior, not as a new optimization claim.

## Cache / storage conclusion

No production result cache is added. `cache_hit_rate` is therefore `not_applicable`. Storage remains the existing registry/SQLite design; no new database architecture is added because the profile did not show a relevant bottleneck.
