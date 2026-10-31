# Collection snapshots

`current_deck_allocations.json` is a legacy/read-only physical-inventory allocation snapshot generated from the canonical inventory state on 2026-08-07. It is retained for regression and allocation-validation context and is **not** the authoritative source for the current active-own-deck scope.

Current active-own-deck truth is defined under `data/collections/current/`, especially `ACTIVE_OWN_DECKS_CURRENT.json`. As of the current project state, `rogshai/current` is the sole active own deck; `korvold/current` is an inactive former own deck and does not reserve cards for simultaneous own-deck construction.

This repository snapshot does not replace the canonical physical inventory workbook in Google Drive. Printing metadata such as set, collector number, language, condition, and foil status is inventory/provenance data; it does not change the Oracle identity or simulated rules behavior of the same card.

## Stand-ins and the owner's private data

The files under `data/collections/current/`, `data/collections/current_deck_allocations.json`,
`data/collections/phase7_optimization_pool.json`, `data/canonical_import/` and
`data/sync/current_sources.json` are **stand-ins**: the same files and schema as the owner's real
data, with one copy of every named card, no pointers to the owner's storage (`redacted`, digests as
64 zeros) and no printing data. The only per-card owner list in this repository is
`owner_collection_2026-10-12.txt` (card names, nothing else).

The real files live outside the repository. Set `COMMANDER_LAB_OWNER_DATA` to a folder with the same
layout and every read of these paths goes there instead (no fallback to the stand-ins). The stand-ins
are produced from the real files with `python scripts/project_owner_data.py --source PRIVATE_ROOT
--target .`; `tests/unit/test_project_owner_data.py` fails if a real inventory or a storage pointer is
committed here.
