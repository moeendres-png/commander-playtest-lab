# Stale-source consumer index — August → 2026-09-19

Baseline hashes: `source_audit_A.json → repo_baseline.tracked_files` (first 16 hex chars).
Policy: historical sources stay frozen; active consumers migrate to the versioned
`commander_lab.physical_pool` loader (fail-closed, no stale fallback).

| # | Consumer | August source | Status after this workstream | Action |
|---|----------|---------------|------------------------------|--------|
| 1 | `src/commander_lab/playstyle.py:38` | `data/canonical_import/2026-08-07/inventory_snapshot.json` | STALE (unchanged file) | Migrate to loader; not done here — needs product-owner scope |
| 2 | `src/commander_lab/mana_analysis.py:83` | same inventory snapshot | STALE (unchanged file) | same as 1 |
| 3 | `src/commander_lab/decision_context.py:359` | same inventory snapshot | STALE (unchanged file) | same as 1 |
| 4 | `src/commander_lab/project_context.py:330` | same inventory snapshot | STALE (unchanged file) | same as 1 |
| 5 | `src/commander_lab/tools/service.py:436` | `data/sync/current_sources.json` (Aug) | STALE pointer (unchanged) | Pointer update is a separate gated action |
| 6 | `src/commander_lab/tools/service.py:1348` | `data/cards/oracle_subset.json` (195 cards, non-authoritative) | STALE catalog (unchanged) | Replace reads with loader + oracle join; separate scope |
| 7 | `src/commander_lab/tools/local_snapshots.py:28` | `oracle_subset.json` | STALE (unchanged file) | same as 6 |
| 8 | `src/commander_lab/engine/structural/profiles.py:1215` | `oracle_subset.json` | STALE (unchanged file) | same as 6 |
| 9 | `src/commander_lab/engine/rules/validation.py:33` | `oracle_subset.json` | STALE (unchanged file) | same as 6 |
| 10 | `src/commander_lab/whole_deck/lab_context.py:31` | `rogshai_semantic_projection_current.zlib.b64` (795-base) | STALE derived (unchanged) | Rebuild from 828-context; separate scope + rerun |
| 11 | `src/commander_lab/whole_deck/optimizer_v2_decision_runtime.py:50` | same projection | STALE derived (unchanged) | same as 10 |
| 12 | `src/commander_lab/whole_deck/knowledge_quality.py:57` | `data/canonical_import/2026-08-07/inventory.json` | STALE (unchanged file) | same as 1 |
| 13 | `src/commander_lab/cli/app.py` (`data_sync` audit/sync) | `current_sources.json` | STALE pointer (unchanged) | same as 5 |
| 14 | `service.py:3497,3514` deck_lists refs | `data/canonical_import/2026-08-07/deck_lists.json` | FROZEN fixture (unchanged) | Do not touch without deck-owner grant |
| 15 | Optimizer manifests / dated simulator results | 795-candidate base | STALE results (unchanged) | Rerun required; cannot relabel 795→828 |

New (this workstream, non-overlapping with PR #206):
- `src/commander_lab/physical_pool/` — versioned loader + predicates (fail-closed).
- `data/sync/snapshot_2026_09_19_manifest.json` — pinned review manifest (hashes/dates/counts only, no inventory bytes).
- `tests/unit/test_physical_pool_snapshot.py` — synthetic-fixture gate tests.
- `tests/integration/test_physical_pool_snapshot_live.py` — opt-in live verification (env-gated).

Protected (verified untouched): `tools/foundry/safe_push.py`, `tests/foundry/*` (PR #206);
`moeendres-png/forge`, `moeendres-png/mage` (no checkouts modified); current decks,
opponents, allocations, reservations, historical archives (no mutations).
