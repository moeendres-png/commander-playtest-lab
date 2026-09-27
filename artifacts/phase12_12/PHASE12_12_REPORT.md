# Phase 12.12 — Manual-playtest subsystem removal

## Result

```text
execution_status=passed
completion_status=manual_playtest_subsystem_removed
active_validation_levels=structural_only,tactical_oracle,external_rules_engine
current_tools=83
```

The active product no longer exposes manual real-game ingestion, empirical local-meta learning, or real-playtest calibration. Historical Git objects and archived audit evidence were not rewritten.

## Removed active surface

- tools: `ingest_playtest`, `calibrate`, `ingest_local_game`, `update_local_opponent_profile`, `inspect_local_meta`, `compare_observed_to_assumed`, `detect_local_meta_drift`, `build_local_meta_scenarios`, `generate_local_meta_report`;
- CLI: `ingest-playtest`, `calibrate-playtests`, `validate-phase9`;
- manual CSV/XLSX/JSON playtest importers, append-only real-game stores, calibration models and reports;
- active local-observation profiles and playtest templates;
- real-playtest-only tests and active documentation requirements.

## Migration

Database schema version 2 removes known manual-playtest-only tables (`calibration_profiles`, `local_opponent_profiles`, `local_games`, `playtest_games`, `playtests`) when present. The migration writes structured metadata with the migration status and removed table list. New databases record that the legacy tables were not present.

## Verification

```text
249 passed
1 skipped
0 failed
2 collection warnings
runtime=73.99s
```

The skip is the real XMage/Forge differential test and remains correctly non-passing. The former manifest count of 259 passing tests is not reused: after removing manual-playtest-only tests, the active suite contains 250 collected tests.

A reproducible pytest capture-pipe blockage was found during worker-count integration testing. Under pytest only, the batch runner uses a bounded thread executor; production runs continue to use process parallelism. The full integration group and full regression suite pass after the fix.

## Data protection

No canonical deck list, inventory quantity, or physical allocation was changed. No recommendation was applied.
