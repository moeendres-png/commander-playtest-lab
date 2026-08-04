# Phase 4 – Pilot Agents

Date: 2026-08-04

## Status

Phase 4 is complete. The structural simulator now uses configurable pilot agents for mulligan, main-phase, reaction, target, and combat decisions. The authoritative game state remains inside the simulator; pilots only score engine-supplied legal actions.

No Google Drive file was read, changed, created, or deleted during this phase. No OpenAI API call is required or performed by the pilot runtime.

## Version

- Package: `commander-playtest-lab 0.4.0`
- Structural engine: `structural-0.4.0`
- Input baselines: local `korvold/current` and `rogshai/current`
- Result label: `structural_model_estimates`

## Implemented models

The following validated pilot models were added:

- `PilotStrength`
- `PilotDecisionMode`
- `PilotUtilityWeights`
- `PilotConfig`
- `PilotCommanderView`
- `PilotOpponentView`
- `PilotStateView`
- `PilotActionView`
- `PilotUtilityBreakdown`
- `PilotDecision`

`CardRole` was moved into a shared role module so the engine, structural profiles, and pilot schemas use the same enum without circular imports.

## Utility dimensions

Each legal action is evaluated through all requested dimensions:

1. survival
2. mana_efficiency
3. card_advantage
4. tempo
5. engine_development
6. interaction_reserve
7. commander_value
8. threat_reduction
9. win_progress
10. political_visibility
11. rebuild_capacity

The selected action and its complete breakdown are persisted in `pilot_decision` events. The weights can be replaced per `PilotConfig`.

## Pilot modes and strengths

### Decision modes

- `deterministic`: stable utility ranking and deterministic tie-breaking.
- `stochastic`: seeded softmax choice with configurable temperature and mistake rate.

Stochastic pilot RNG is derived separately for every seat. Repeating the same match configuration and seed reproduces the same choices and event hash, including when the batch worker count changes.

### Strengths

- `weak`
- `average`
- `strong`
- `near_optimal_heuristic`

The levels change information weighting, reserve behavior, shortlist size, precision, stochastic temperature, and mistake rate. `near_optimal_heuristic` means near-optimal only under the current structural utility model; it is not a claim of optimal Magic play.

A controlled action-choice benchmark tests early ramp, urgent removal, post-wipe rebuilding, and a table finisher. With 192 seeded trials per scenario, expected-choice rates were:

| Strength | Expected-choice rate |
|---|---:|
| weak | 0.8073 |
| average | 0.9362 |
| strong | 0.9831 |
| near_optimal_heuristic | 1.0000 |

The sequence is monotonic in this controlled benchmark. Match results are deliberately not used to rank pilot strength because a single archetype fixture can reward an overly aggressive or overly conservative policy.

## Specialized pilots

### KorvoldPilot

The specialist models:

- sacrifice material and sacrifice outlets;
- token and resource density;
- land-synergy and land-recursion packages;
- immediate value when casting Korvold;
- delaying Korvold when no sacrifice value or protection exists;
- protection for Korvold and high-value engines;
- graveyard-hate timing;
- independent resource engines;
- table-damage cards such as Mirkwood Bats, Exsanguinate, Massacre Wurm, and Hearthhull;
- rebuild value from the graveyard;
- commander-damage pressure per target.

### RogShaiPilot

The specialist models:

- early Rograkh deployment and use with mana resources;
- Ishai growth with additional opponents;
- holding protection and counter mana;
- combat-draw auras only when the relevant commander and protection window exist;
- Jeska with a sufficiently large Ishai;
- Kediss as normal table damage rather than commander damage;
- double-strike and Duelist's Heritage effects;
- Kykar, Whirlwind of Thought, Storm-Kiln Artist, and Guttersnipe as an independent spellslinger axis;
- commander-damage counters separately for each opponent;
- target selection based on lethal pressure and existing commander damage.

## Additional pilots

The automatic pilot registry also contains:

- `AggroPilot`
- `ControlPilot`
- `EnginePilot`
- `GraveyardPilot`
- `ArtifactPilot`
- `GenericCommanderPilot`

`auto` assignment maps the deck strategy to the matching specialist.

## Simulator integration

Pilots now participate in:

- London mulligan keep and bottom decisions;
- main-phase card and commander choices;
- deliberate passing to preserve interaction;
- counterspell decisions;
- protection decisions;
- board-protection decisions;
- removal target selection;
- graveyard-hate target selection;
- combat target selection.

Dynamic action annotations expose conditions such as sacrifice-package availability, land-engine availability, commander attack readiness, and turn-cycle survival. Pilots cannot write any game-state field directly.

## Event logging

The final validation audit contained 86 pilot-decision events:

| Decision phase | Events |
|---|---:|
| main | 61 |
| combat | 15 |
| counter | 3 |
| protection | 2 |
| removal_target | 5 |

All eleven required utility dimensions were present. The log also contains the pilot name, strength, mode, selected action, candidate utilities, specialist bonus, and total utility.

## Validation runs

Two four-player technical batches were executed with 24 matches each:

- deterministic specialist batch: 24 completed, 0 aborted;
- stochastic specialist batch: 24 completed, 0 aborted.

The stochastic batch was repeated with a different worker count. Ordered seeds, placements, winners, turns, termination reasons, and log hashes were identical.

These matches use synthetic Aggro and Control fixtures and are only regression tests. Their placements and place-one shares are not empirical win rates or matchup evidence.

## Tests

The complete repository test suite contains 67 passing tests. Phase-4 coverage includes:

- deterministic choice independence from incidental RNG state;
- seeded stochastic replay and variation across different seeds;
- strength benchmark ordering;
- interaction-mana preservation;
- Korvold sacrifice-outlet, land-rebuild, table-damage, protection, and commander-timing decisions;
- Rograkh, Ishai, combat draw, Jeska, Kediss, double strike, spellslinger fallback, and protection decisions;
- commander-damage target selection per opponent;
- removal and graveyard target selection;
- pilot-aware mulligan events;
- decision breakdown persistence;
- batch reproducibility across worker counts;
- Phase-4 validation audit.

## CLI

Run the Phase-4 validation:

```bash
commander-lab validate-pilots \
  --iterations 24 \
  --workers 2 \
  --seed 20260804 \
  --root .
```

Run an ad hoc batch with a shared pilot policy:

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

Per-seat `PilotConfig` values remain available through the Python API.

## Limitations

- Utility values are model parameters, not learned ground truth.
- Pilots operate on structural roles rather than complete Oracle rules.
- Threat assessment and politics are simplified numeric views.
- Lookahead search and LLM escalation are not part of Phase 4.
- External rules validation with Forge or XMage remains pending.
- Opponent precons and the synthetic Cosmic Spider-Man list are not imported yet.
- Stronger heuristic levels are validated through controlled action decisions, not guaranteed to dominate every deck or matchup fixture.

## Acceptance result

Phase 4 meets the requested scope:

- deterministic pilots: implemented;
- stochastic pilots: implemented and seed-reproducible;
- configurable utility function: implemented;
- KorvoldPilot: implemented;
- RogShaiPilot: implemented;
- four pilot strengths: implemented;
- typical-game-state tests: implemented;
- event-log integration: implemented;
- batch and parallel replay: passed.
