# artifacts/phase12_20/final_package/ — SUPERSEDED SNAPSHOT

**Everything in this directory is a 2026-08-07 snapshot that was superseded the next day.
Do not read any number here as a current value.**

The canonical successor for every rules-coverage artifact in this directory is under
`data/rules/`. The divergence is material, not cosmetic — see the table below.

## Why this warning exists

The directory name ends in `final_package`, which reads as authoritative. It is not. It was
committed on 2026-08-07 (`docs: record final engine-backed optimization acceptance`); the
canonical data was synced on 2026-08-08 (`release: sync canonical data for 1.13.3`). A reader
who trusted the name would silently use numbers that no longer match the live data.

## Measured divergence: `CARD_RULES_COVERAGE.json`

| Field | This snapshot (2026-08-07) | Canonical `data/rules/` (live) |
|---|---|---|
| `coverage_counts.unsupported` | **1460** | **1443** |
| `inventory_candidate_count` | **1349** | **1335** |
| `source_drive_files` | different Drive file ids | current ids |
| `cards`, `deck_statistics` | also differ | — |

So this snapshot reports **17 more unsupported cards** and **14 more inventory candidates**
than the live source.

## Canonical successors

| File in this directory | Live successor | Live consumers |
|---|---|---|
| `CARD_RULES_COVERAGE.json` | `data/rules/card_rules_coverage.json` | `src/commander_lab/mcp/server.py:195`, `src/commander_lab/tools/service.py:3491`, `:4259`, `tests/unit/test_phase1214_rules_coverage.py` |
| `UNSUPPORTED_CARD_REGISTER.json` | `data/rules/unsupported_card_register.json` | live |
| `GOLDEN_RULES_CORPUS.json`, `GOLDEN_RULES_SCENARIOS.json`, `RULES_SCENARIO_REGISTRY.json` | `data/rules/…` (byte-identical copies) | live |
| `PILOT_AND_POLITICS_REGISTRY.json`, `OPPONENT_UNCERTAINTY_REGISTRY.json`, `STATISTICAL_DECISION_PROTOCOL.md`, `FINAL_PERFORMANCE_REPORT.md`, `FINAL_SECURITY_REPORT.md` | the earlier `artifacts/phase12_*` originals | none |

## Nothing here is deleted, and nothing here is authoritative

This README was added by a project-hygiene audit. The snapshot files themselves are
unchanged, because they are historical evidence of what the 2026-08-07 phase actually
produced. Removing them would destroy that record, and renaming the directory would rewrite
historical paths.

`scripts/run_isolated_pytest_suite.py` writes to `artifacts/phase12_20/` but never reads
`final_package/`, so this directory is not on any live execution path.

## Related

- `artifacts/phase12_14/CARD_RULES_COVERAGE.json` is a **byte-identical** copy of the live
  file (same blob `d5993272`), so it cannot mislead even though nothing reads it.
- A full inventory of duplicate and divergent artifacts is recorded in
  `docs/project_hygiene_20260929/PROJECT_HYGIENE_AUDIT.md`.
