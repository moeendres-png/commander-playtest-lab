# Commander Playtest Lab

Local, reproducible foundation for importing, validating, structurally simulating, and later optimizing MTG Commander decks.

## Current scope: Phase 4

The repository provides:

- Pydantic models for cards, physical inventory, decks, opponents, game state, actions, events, simulation runs, contributions, upgrades, structural role profiles, pilot configuration, utility breakdowns, and structural results;
- plaintext, CSV, XLSX, local Google-Drive-export, opponent-profile, and real-playtest importers;
- Oracle-name normalization and local Commander validation;
- immutable local snapshots of `korvold/current` and `rogshai/current`;
- a role-based Structural Simulator with deterministic replay;
- London mulligans, turn order, cards drawn, lands, approximate colored mana, ramp, selection, independent draw, commander casting and tax, removal, counters, protection, board wipes, graveyard hate, recursion, board pressure, commander and normal damage, engines, resources, finishers, elimination, and game end;
- deterministic and seeded stochastic pilot decisions;
- specialized `KorvoldPilot` and `RogShaiPilot` implementations;
- generic Aggro, Control, Engine, Graveyard, Artifact, and Commander pilots;
- four configurable pilot strengths;
- deterministic batch seeds independent of worker count;
- process-based parallel execution;
- JSONL event logs containing the complete utility breakdown for each pilot decision.

Every game result produced by this engine is labelled exactly:

```text
structural_model_estimates
```

These outputs are not comprehensive rules simulations, rules-validated games, or empirical win rates.

## Local baselines

- `korvold/current`: 100 cards, including Korvold and 39 lands;
- `rogshai/current`: 100 cards, including Ishai + Rograkh and 37 lands.

Older optimization proposals are not imported as current deck data. No Google Drive file is modified.

## Pilot utility model

Each legal action is scored through the configurable dimensions:

- `survival`
- `mana_efficiency`
- `card_advantage`
- `tempo`
- `engine_development`
- `interaction_reserve`
- `commander_value`
- `threat_reduction`
- `win_progress`
- `political_visibility`
- `rebuild_capacity`

Pilots only rank legal action views supplied by the engine. They cannot mutate life totals, zones, mana, targets, the stack, or game results directly.

Decision modes:

- `deterministic`: the same state, configuration, and legal actions produce the same choice;
- `stochastic`: seeded softmax selection with a strength-dependent temperature and mistake rate.

Pilot strengths:

- `weak`
- `average`
- `strong`
- `near_optimal_heuristic`

The strength labels describe increasing decision fidelity within the structural heuristic model. They do not claim optimal Magic play.

### KorvoldPilot

The Korvold specialist evaluates sacrifice material and outlets, land recursion, immediate Korvold value, protection windows, graveyard pressure, independent resource engines, table-damage payoffs, rebuild capacity, and commander-damage pressure.

### RogShaiPilot

The RogShai specialist evaluates Rograkh as a resource, multiplayer Ishai growth, protection and counter mana, combat-draw auras, Jeska, Kediss, double strike, the Kykar/spellslinger axis, and commander damage separately for every opponent.

## Structural card profiles

`data/cards/structural_role_profiles.json` contains validated profiles for all Oracle names in the local two-deck catalog. Cards may have several roles, including mana, ramp, draw, selection, interaction, protection, wipes, recursion, graveyard hate, engines, enablers, payoffs, finishers, combat payoffs, token sources, sacrifice outlets, and land synergy.

Each profile records approximate mana value, color needs, commander synergy, floor value, immediate impact, turn-cycle risk, multiplayer scaling, and conditional strength. These profiles are structural abstractions rather than substitutes for Oracle text.

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

OpenAI-backed phases use the optional dependency group:

```bash
python -m pip install -e '.[openai]'
```

No API key is required for the Phase-4 simulator or pilots.

## Commands

Validate the local deck and collection snapshots:

```bash
commander-lab validate-local --root .
```

Regenerate and validate structural profiles:

```bash
commander-lab generate-structural-profiles --root .
```

Run the Phase-3 structural validation:

```bash
commander-lab validate-structural \
  --iterations 24 \
  --workers 2 \
  --seed 20260804 \
  --root .
```

Run the Phase-4 pilot validation:

```bash
commander-lab validate-pilots \
  --iterations 24 \
  --workers 2 \
  --seed 20260804 \
  --root .
```

Run an ad hoc batch with a shared pilot configuration:

```bash
commander-lab run-structural-batch \
  --deck korvold/current \
  --deck rogshai/current \
  --deck synthetic/aggro \
  --deck synthetic/control \
  --pilot-strength strong \
  --pilot-mode stochastic \
  --iterations 1000 \
  --workers 4 \
  --seed 20260804
```

The `synthetic/*` decks are engine-validation fixtures. They are not claims about real opponents and must not be used as matchup evidence.

## Reproducibility

A match seed is derived only from:

- engine version;
- master seed;
- run ID;
- match index.

Each seat receives a separate pilot RNG derived from the match identity and seat. Worker count and task completion order do not affect match seeds, pilot choices, ordered results, or event hashes.

The batch runner supports fixed seeds, starting-seat rotation, run-abort limits, one or more worker processes, deterministic or stochastic pilots, and per-seat pilot configurations.

## Phase-4 validation

The validation suite covers:

- deterministic specialist pilots in a four-player fixture;
- seeded stochastic specialist pilots;
- byte-identical stochastic replay with different worker counts;
- all eleven utility dimensions in decision logs;
- main-phase, combat, counter, protection, and target decisions;
- a controlled action-choice benchmark for all four strength levels;
- unit tests for typical Korvold and RogShai situations.

The strength benchmark measures choices in controlled decisions such as early ramp, urgent removal, post-wipe rebuilding, and a table finisher. It is not a match win-rate benchmark.

## Project boundaries

Not implemented yet:

- full Oracle snapshot ingestion;
- tactical stack engine;
- card-by-card rules execution;
- real opponent-precon import for simulation;
- Cosmic Spider-Man synthetic completion;
- Forge or XMage runtime adapters;
- OpenAI tool server and agent orchestration;
- optimization and holdout validation.
