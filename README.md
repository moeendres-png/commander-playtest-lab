# Commander Playtest Lab

Local, reproducible foundation for importing, validating, structurally simulating, and later optimizing MTG Commander decks.

## Current scope: Phase 3

The repository now provides:

- Pydantic models for cards, physical inventory, decks, opponents, game state, actions, events,
  simulation runs, contributions, upgrades, structural role profiles, and structural results;
- plaintext, CSV, XLSX, local Google-Drive-export, opponent-profile, and real-playtest importers;
- Oracle-name normalization and local Commander validation;
- immutable local snapshots of `korvold/current` and `rogshai/current`;
- a role-based Structural Simulator with deterministic replay;
- London mulligans, turn order, cards drawn, lands, approximate colored mana, ramp, selection,
  independent draw, commander casting and tax, removal, counters, protection, board wipes,
  graveyard hate, recursion, board pressure, commander and normal damage, engines, resources,
  finishers, elimination, and game end;
- deterministic batch seeds independent of worker count;
- process-based parallel execution;
- compact event generation for every turn and optional full JSONL event persistence;
- Goldfish, three-player, four-player, and five-player validation scenarios.

Every result produced by this engine is labelled exactly:

```text
structural_model_estimates
```

These outputs are not comprehensive rules simulations, rules-validated games, or empirical win rates.

## Local baselines

- `korvold/current`: 100 cards, including Korvold and 39 lands;
- `rogshai/current`: 100 cards, including Ishai + Rograkh and 37 lands.

Older optimization proposals are not imported as current deck data. No Google Drive file is modified.

## Structural card profiles

`data/cards/structural_role_profiles.json` contains validated profiles for all 161 Oracle names in
the local two-deck catalog. A card may have multiple roles:

- `mana_source`
- `ramp`
- `draw`
- `selection`
- `removal`
- `counter`
- `protection`
- `wipe`
- `recursion`
- `graveyard_hate`
- `engine`
- `enabler`
- `payoff`
- `finisher`
- `combat_payoff`
- `token_source`
- `sacrifice_outlet`
- `land_synergy`

Each profile also records approximate mana value, color needs, commander synergy, floor value,
immediate impact, turn-cycle risk, multiplayer scaling, and conditional strength. The profiles are
structural abstractions rather than substitutes for Oracle text.

## Setup

```bash
uv sync --extra dev
uv run pytest
```

A standard editable installation also works:

```bash
python -m pip install -e .
pytest
```

## Commands

Validate the local deck and collection snapshots:

```bash
commander-lab validate-local --root .
```

Regenerate and Pydantic-validate structural profiles:

```bash
commander-lab generate-structural-profiles --root .
```

Run the Phase-3 validation suite:

```bash
commander-lab validate-structural \
  --iterations 24 \
  --workers 2 \
  --seed 20260804 \
  --root .
```

Run an ad hoc batch:

```bash
commander-lab run-structural-batch \
  --deck korvold/current \
  --deck rogshai/current \
  --deck synthetic/aggro \
  --deck synthetic/control \
  --iterations 1000 \
  --workers 4 \
  --seed 20260804
```

The `synthetic/*` decks are engine-validation fixtures. They are not claims about real opponents and
must not be used as matchup evidence.

## Reproducibility

A match seed is derived only from:

- engine version;
- master seed;
- run ID;
- match index.

Worker count and task completion order do not affect match seeds or ordered results. Identical
inputs produce identical placements, event hashes, and persisted JSONL logs.

The batch runner supports:

- fixed seeds;
- starting-seat rotation;
- `max_turns`;
- `max_events`;
- `max_no_progress_turns`;
- `max_spells_per_turn`;
- one or more worker processes.

## Phase-3 validation

The committed validation summary covers 24 iterations for each of:

- Korvold Goldfish;
- RogShai Goldfish;
- three-player pod;
- four-player pod;
- five-player pod.

All 120 validation games completed under the configured limits. Repeating the complete validation
with the same seed and worker count produced byte-identical result and event files.

The actual aggregates are useful only for detecting engine regressions. They are not deck-strength
conclusions because three of the validation seats use synthetic fixtures.

## Project boundaries

Not implemented yet:

- full Oracle snapshot ingestion;
- tactical stack engine;
- card-by-card rules execution;
- strategic pilot classes;
- real opponent-precon import for simulation;
- Cosmic Spider-Man synthetic completion;
- Forge or XMage runtime adapters;
- OpenAI tool server and agent orchestration;
- optimization and holdout validation.
