# Phase 12.19 Performance Report

Measurements are local technical timings, not cross-machine guarantees.

| Operation | Status | Seconds | Note |
|---|---|---:|---|
| `deck_import_and_service_initialization` | `passed` | 0.011785 |  |
| `structural_goldfish_1_games_workers_1` | `passed` | 0.029987 |  |
| `structural_goldfish_100_games_workers_1` | `passed` | 1.179133 |  |
| `structural_goldfish_1000_games_workers_1` | `passed` | 10.585304 |  |
| `four_player_50_games_workers_1` | `passed` | 3.412885 |  |
| `four_player_50_games_workers_2` | `passed` | 57.841002 |  |
| `mulligan_sampling_500x2` | `passed` | 4.331037 |  |
| `opponent_ensemble_evaluation` | `passed` | 0.001674 |  |
| `paired_variant_comparison_50` | `passed` | 5.598594 |  |
| `report_generation` | `passed` | 0.004227 |  |
| `sqlite_write_read_1000` | `passed` | 0.526889 |  |
| `mcp_initialize_in_process` | `passed` | 0.000011 |  |
| `mcp_tools_list_in_process` | `passed` | 0.037417 |  |
| `xmage_run` | `blocked` | — | No verified source/binary; GitHub DNS and build dependencies unavailable. |
| `forge_run` | `blocked` | — | No verified source/binary; GitHub DNS and build dependencies unavailable. |
| `parquet_roundtrip` | `not_run` | — | Parquet is not an active project feature; pyarrow/fastparquet not required. |
| `counterfactual_replay` | `not_run` | — | No canonical replay fixture selected for this performance run; functionality remains covered by tests. |
| `decision_diagnostics` | `not_run` | — | No canonical diagnostic dataset selected for this performance run; functionality remains covered by tests. |
