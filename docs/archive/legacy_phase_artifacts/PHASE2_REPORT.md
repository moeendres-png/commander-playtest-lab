# Phase 2 Implementation Report

## Completed

- Initialized a local Git repository using the requested directory layout.
- Added all requested Pydantic models and supporting enums/value objects.
- Added read-only importers for plaintext, CSV, XLSX, Google-Drive-style XLSX exports,
  opponent profiles, and real playtest sheets.
- Added Oracle-name normalization and alias handling.
- Added deck-size, library-size, singleton, Commander legality, Commander eligibility,
  partner-pair, color-identity, and simultaneous physical-quantity validation.
- Added deterministic deck hashes and multi-file data-snapshot hashes.
- Imported only local current snapshots for Korvold and RogShai.
- Added deterministic unit and property-style tests.

## Current local baselines

| Deck ID | Total | Library | Lands in source | Deck hash |
|---|---:|---:|---:|---|
| `korvold/current` | 100 | 99 | 39 | `4af053a36d9cf4e84ff5ac2c2e5372daba5336c3cdfb48914ea4d72ea495677d` |
| `rogshai/current` | 100 | 98 | 37 | `2f2dab2a26e3889aa5399504295d2c6e485c8922397c6736bd4e6fa72f6b6656` |

The current combined minimal-allocation snapshot contains exactly the 200 copies required by those
lists. It is deliberately not represented as the user's complete physical collection.

## Oracle data boundary

The committed `oracle_subset.json` contains only the 161 unique Oracle names used by the two current
lists. Most stable cards have explicit project-local color identities. Seven newer cards whose
current Oracle records were not available in the local files are conservatively bounded by the
already validated deck color identity and marked `project_inferred`:

- Eumidian Hatchery
- Evendo Brushrazer
- Exploration Broodship
- Hearthhull, the Worldseed
- Horizon Explorer
- Scouring Swarm
- Szarel, Genesis Shepherd

This is sufficient for current local snapshot validation but is not a substitute for a later pinned
MTGJSON/Scryfall Oracle snapshot. The schema and catalog interface are designed so that replacement
does not require changes to deck importers or validators.

## Google Drive boundary

No Google Drive connector was used and no Drive file was created, edited, or deleted. The
`GoogleDriveExportImporter` accepts a local XLSX export and opens it read-only. Its test verifies that
the source workbook bytes do not change.

## Test boundary

Property-style tests use deterministic standard-library generation because the execution environment
could not download Hypothesis. Hypothesis remains listed in the optional development dependencies for
future expansion.
