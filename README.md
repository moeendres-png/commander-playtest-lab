# Commander Playtest Lab

Local, reproducible data and validation foundation for the MTG Commander Playtest Lab.

## Phase 2 scope

This repository currently provides:

- Pydantic domain models for cards, physical inventory, decks, opponents, game state,
  actions, events, simulation runs, results, contributions, and upgrade proposals;
- importers for plaintext, CSV, XLSX, Google-Drive-style XLSX exports, opponent profiles,
  and real playtest sheets;
- Oracle-name normalization and a local card catalog;
- Commander deck size, singleton, commander/partner, color-identity, legality, and physical
  quantity validation;
- deterministic deck and data-snapshot hashes;
- local immutable snapshots of the current Korvold and RogShai lists only;
- unit tests and deterministic property-style tests.

Phase 2 does **not** implement the simulator, agents, OpenAI tool server, XMage adapter, or Forge
adapter. Google Drive is never written to.

## Local data policy

The local deck baselines are:

- `korvold/current`: 100 cards, including Korvold and 39 lands;
- `rogshai/current`: 100 cards, including Ishai + Rograkh and 37 lands.

Older optimization proposals are not imported as current deck data.

The card catalog in `data/cards/oracle_subset.json` is a project-local subset sufficient for the
current two deck snapshots and tests. It records provenance and confidence. A later phase may
replace it with a pinned authoritative MTGJSON or Scryfall snapshot without changing importer or
validator interfaces.

## Setup

```bash
uv sync --extra dev
uv run pytest
```

The current execution environment already contains the runtime dependencies. `hypothesis` is listed
as an optional development dependency; the committed property tests intentionally use deterministic
standard-library generators so they also run in network-isolated environments.

## Validate local snapshots

```bash
PYTHONPATH=src python -m commander_lab.cli.app validate-local
```

## Repository layout

The requested top-level layout is preserved. Empty future-phase packages are present so later phases
can add the simulator, agents, API, optimization, and reporting layers without reorganizing the data
foundation.
