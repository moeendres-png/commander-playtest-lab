# Commander Playtest Lab

Local, reproducible foundation for importing, validating, structurally simulating, and later optimizing MTG Commander decks.

## Current scope: Phase 7

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
- tactical stack engine and card-by-card rules execution;
- real opponent-precon import for simulation;
- Cosmic Spider-Man synthetic completion;
- rule-validating XMage or Forge runtime adapters;
- a live OpenAI workflow smoke test in this build container, because its configured package index did not provide the optional Agents SDK and external DNS was unavailable.


## Phase 5: local Function-Tool server and OpenAI agents

Phase 5 introduced a local FastAPI Function-Tool server. Phase 7 extends it to 23 strict, Pydantic-validated tools:

- deck validation and inspection;
- goldfish and multiplayer batches;
- paired deck and variant comparison;
- card and package ablation;
- commander-denial stress tests;
- swap matrices and bounded variant search;
- holdout and sensitivity runs;
- upgrade screening and validation;
- real-playtest ingestion and provisional calibration;
- structured Markdown reports.

Start the local server:

```bash
python -m pip install -e '.[api]'
commander-lab serve-tools --host 127.0.0.1 --port 8765
```

Endpoints:

```text
GET  /health
GET  /v1/tools
POST /v1/tools/{tool_name}:invoke
POST /v1/workflows:run
```

The deterministic tools run without an API key. Live workflows require the optional OpenAI dependencies and `OPENAI_API_KEY`:

```bash
python -m pip install -e '.[api,openai]'
export OPENAI_API_KEY=...
```

The OpenAI workflow contains four separate agents:

- `Orchestrator Agent`;
- `Deck Analyst`;
- `Simulation Analyst`;
- `Red-Team Reviewer`.

The SDK integration uses Responses-path agents, strict function schemas, `WorkflowReport` structured output, persistent `SQLiteSession` storage, SDK tracing, blocking input guardrails, output guardrails, lifecycle hooks, and local cost tracking. Agents receive only the structured tools and cannot mutate deterministic game state.

OpenAI traces are stored separately from deterministic game logs:

```text
data/runs/openai_traces/
data/runs/openai_sessions.sqlite
data/runs/tool_runs/<invocation>/events/
```

Budget controls include maximum model turns, total tokens, output tokens per call, configurable estimated USD cost, simulation time, variant count, a hard iteration ceiling, and an explicit approval threshold for large runs. Model prices are deliberately configuration values rather than hard-coded assumptions.

Run the offline, deterministic end-to-end demonstration:

```bash
commander-lab demo-phase5 --iterations 80 --seed 20260804 --root .
```

The demo validates Korvold, runs a four-player structural matchup, screens one potential cut, performs a paired swap comparison, executes holdout validation, and writes a structured report. Synthetic opponents remain technical fixtures and are not evidence about the real metagame.

## Phase 6: multi-tier evaluation system

Phase 6 adds a release-gated evaluation suite with five independent tiers:

- unit tests for import, legality, quantities, commander damage, commander tax, London mulligans, abstract trigger ordering, seeds, and event logs;
- property checks for nonnegative zones, card conservation, zone consistency, eliminated-player inactivity, seed replay, and rejection of illegal actions;
- reviewed golden pilot decisions for Korvold, RogShai, and generic tactical situations;
- differential fixtures that can be executed through an external XMage or Forge adapter command;
- agent trajectory evaluations for tool selection, evidence grounding, interpretation, uncertainty disclosure, model/real separation, and validation before recommendations.

Run the complete local evaluation:

```bash
commander-lab eval-phase6 \
  --iterations-per-scenario 64 \
  --workers 2 \
  --seed 20260804 \
  --root .
```

The default run checks 256 complete structural games across goldfish, three-player, four-player, and five-player fixtures. Local acceptance requires all local blocking gates to pass. Full release acceptance additionally requires three real differential observations and a 100% match rate against a configured XMage or Forge backend.

Configure an external differential adapter with one of:

```bash
export COMMANDER_LAB_FORGE_DIFFERENTIAL_CMD='python adapter.py --input {input} --output {output}'
export COMMANDER_LAB_XMAGE_DIFFERENTIAL_CMD='python adapter.py --input {input} --output {output}'
```

The adapter receives a JSON fixture and must write a normalized JSON result. Missing external configuration is reported as `blocked`; it is never converted into a passing comparison.

Acceptance thresholds are versioned in `config/evals.yaml`. Golden, differential, and agent cases are stored under `data/evals/`. The local agent cases can also be exported as JSONL input for a separate OpenAI custom-eval workflow; exporting the dataset performs no API call.

Every simulation-derived value remains labeled `structural_model_estimates`. Passing the local suite is not evidence of a real match win rate and does not authorize an upgrade recommendation without paired and holdout validation.


## Phase 7: constrained deck optimization

Phase 7 adds:

- complete structural swap matrices;
- constrained local and Beam Search;
- multi-card package search;
- Pareto fronts over seven separate objectives;
- paired card and package ablation;
- approximate Shapley contribution estimates;
- a mandatory validation chain with paired comparison, holdouts, sensitivity, and red-team review.

Optimization constraints are configured in `config/phase7_optimization.json`. Candidate physical allocation is read from the narrow local snapshot `data/collections/phase7_optimization_pool.json`.

No search result is automatically applied. `validate_upgrade` returns `validated_not_applied` or `rejected_not_applied`, and canonical deck files remain unchanged.

Run the Phase-7 validation suite:

```bash
pytest -q
PYTHONPATH=src python scripts/run_phase7_validation.py
```

The included smoke outputs use small samples to validate the workflow. They are `structural_model_estimates`, not real win rates or final deck recommendations.

## Phase 8: tactical and rules-validated mode

Phase 8 adds a bounded tactical oracle and persistent JSONL adapters for XMage and Forge. The adapter boundary supports deck loading, Commander game start, deterministic seeds or injected starting states, legal-action queries, programmatic action submission, event logs, and normalized Python results.

Probe available backends:

```bash
commander-lab probe-rules-engines --root .
```

Run the local tactical and optional external validation suite:

```bash
commander-lab validate-rules-phase8 --seed 20260804 --root .
```

The interaction catalog contains more than 50 project-critical cases under `data/evals/differential/project_critical_interactions.json`. The generated registry marks every local card and interaction as one of:

- `structural_only`;
- `tactical_validated`;
- `rules_engine_validated`.

A tactical pass is not an external rules proof. `rules_engine_validated` is emitted only after a matching XMage or Forge bridge observation. Missing external engines remain a visible blocked gate.
