# Final Performance Report

## Measured configuration

All measurements were executed on the audit container with Python 3.13.5. Structural results remain `structural_model_estimates`.

| Operation | Configuration | Wall | Peak RSS | Throughput / result |
|---|---|---:|---:|---:|
| Structural pod | 1 four-player game, 1 worker, max_turns=20 | 1.52 s | 156,308 KiB | 0.66 games/s including startup |
| Structural pod | 100 four-player games, 1 worker, max_turns=20 | 10.14 s | 160,600 KiB | 9.86 games/s |
| Structural pod | 100 four-player games, 2 workers, max_turns=20 | 12.95 s | 155,568 KiB | 7.72 games/s |
| Structural goldfish | 1,000 games, 4 workers, max_turns=8 | 15.85 s | 165,728 KiB | 63.09 games/s |
| Phase-10 acceptance | iterations=1, workers=1 | 28.12 s | 167,744 KiB | passed |

Two workers were slower than one for the 100-game pod batch. The process-start and serialization overhead exceeds the benefit at this small workload. No worker-count default was changed.

A 1,000-game four-player batch with max_turns=20 did not finish within the bounded command window and is therefore `not_run` as a completed benchmark. It is not reported as a pass.

## Microbenchmarks

- Package startup/import: P50 638.30 ms; P95 657.80 ms.
- Deck validation: P50 7.77 ms; P95 11.80 ms.
- Replay branchpoint scan: P50 1,571.90 ms; P95 1,598.00 ms.
- Single-future counterfactual: P50 1,610.32 ms; P95 1,626.89 ms.
- Diagnostic classification: P50 0.0136 ms; P95 0.0833 ms.
- Toolserver `/health`: P50 50.76 ms; P95 57.36 ms.
- Parquet write: `blocked` because neither `pyarrow` nor `fastparquet` is installed.

## Implemented efficiency improvement

The 14-message JSONL protocol contract previously started one Python process per message. It now reuses one persistent bridge process.

| Contract test | Before | After | Change |
|---|---:|---:|---:|
| Wall time | 14.68 s | 3.64 s | −75.2% |
| Peak RSS | 138,816 KiB | 134,008 KiB | −3.5% |
| Assertions | passed | passed | unchanged |

The optimization changes only the test harness process lifecycle. Protocol requests, response validation and all 14 message types remain identical.

## Reproducibility

The same four-game Korvold pod with identical run identity and seed produced identical seeds, winners, placements, turn counts and event-log hashes with one and two workers. Repeated Function Tool requests now derive simulation identity from the request rather than the random storage directory.
