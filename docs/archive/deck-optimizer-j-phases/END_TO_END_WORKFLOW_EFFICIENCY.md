# End-to-End Workflow Efficiency

Package 1.16.0 introduces one small public deck-decision surface while retaining the full
expert/debug API. Structural estimates remain model evidence rather than empirical winrates.

## Frozen comparison

The reproducible benchmark runs the same current RogShai context, candidate challenge, swap,
paired seeds, denial question, cache repeat and Decision Bundle. The legacy path additionally
executes the hidden keep-rule validation and non-advanced sensitivity that the optimized path now
gates out. Each side was executed five isolated times.

| Metric (median) | Legacy `b9eeedb` | Optimized `fc7d211` |
| --- | ---: | ---: |
| Structural simulations | 94 | 20 |
| Wall time | 9.980 s | 3.648 s |
| Repository file opens | 767 | 265 |
| Repeated reads | 698 | 196 |
| Weighted read bytes | 66,868,962 | 22,762,485 |
| Workflow calls | 12 | 4 |
| Default tool-schema bytes | 101,891 | 2,872 |

All five optimized repetitions preserved legal-candidate recall, known-good recovery and
known-bad rejection at `1.0`. Every repetition produced the same
`MODEL_INFORMATION_LIMIT -> diagnose` classification, a reproducible cache miss followed by an
identical hit, zero non-advanced variant-sensitivity simulations and a complete Decision Bundle.

The benchmark does not claim that every future workflow is 63% faster or that structural model
outcomes are real winrates. It demonstrates the resource effect for the frozen representative
workflow only. The existing adaptive racing scheduler remains `JUSTIFIED_NOT_SHIPPED` because its
separate frozen benchmark does not preserve finalist quality.

The machine-readable benchmark generator is
`scripts/benchmark_end_to_end_efficiency.py`. The frozen output SHA-256 values are:

- legacy: `a92e48ec327200e33ff3704ad9547948da00a9996d3d082915364142498586d6`
- optimized: `8da5fb58b4d58c0652c3b911ea89708a5076a5c66f9667f5f06ee617e3256b09`
