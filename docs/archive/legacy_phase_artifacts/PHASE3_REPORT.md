# Phase 3 – Structural Simulator

## Status

Phase 3 is implemented on top of the Phase-2 repository. No Google Drive file was read or changed.
The only real deck inputs are the local immutable Korvold and RogShai snapshots.

## Implemented components

### Structural models

Added validated models for:

- `CardRole`;
- `ConditionalStrength`;
- `StructuralCardProfile`;
- `StructuralDeckProfile`;
- `StructuralAbortLimits`;
- `StructuralMatchConfig`;
- `StructuralBatchConfig`;
- `StructuralPlayerMetrics`;
- `StructuralMatchResult`;
- `StructuralBatchResult`.

All Structural Simulator outputs use the exact label `structural_model_estimates`.

### Card roles and dimensions

The role snapshot contains 161 profiles and provides complete coverage for both current 100-card
lists. Profiles allow multiple roles and include:

- role-specific strength;
- approximate mana value and color requirements;
- produced colors for mana sources;
- commander synergy;
- floor value without commander;
- immediate impact;
- turn-cycle risk;
- multiplayer scaling;
- conditional-strength annotations;
- data-quality provenance.

Cards without complete local Oracle information remain structural assumptions. Newly introduced
Edge of Eternities cards used by Korvold received explicit role metadata and source references where
verified.

### Game systems

The simulator models:

1. London mulligan with a free first multiplayer mulligan;
2. seeded shuffle and seeded turn order;
3. normal and engine-driven draw;
4. land play and approximate colored-source availability;
5. persistent and temporary ramp;
6. card selection;
7. commander casting and two-mana commander tax per previous cast;
8. proactive removal and reactive protection;
9. reactive counterspells;
10. broad board wipes;
11. graveyard hate;
12. recursion;
13. creature, token, commander, and engine pressure;
14. normal damage and commander damage tracked by source commander;
15. engine resources and payoff triggers;
16. combat and noncombat finishers;
17. life, commander-damage, and empty-library elimination;
18. normal game completion and explicit abort states.

This is a role-level simulation. It does not execute the Comprehensive Rules or exact Oracle text.

### Event logs

Every turn emits at least:

- `turn_started`;
- action and resolution events;
- `end_step`;
- `turn_summary`.

All events contribute to a deterministic rolling SHA-256 hash. When an output directory is provided,
the complete event stream is written as immutable JSON Lines.

### Batch and parallel execution

The batch runner provides:

- deterministic per-match seed derivation;
- ordered results independent of worker completion order;
- process-based parallelism;
- starting-seat rotation;
- maximum turns;
- maximum event count;
- no-progress cutoff;
- spell-count cutoff per turn;
- aggregate structural metrics.

Normal script and CLI execution use the portable `spawn` multiprocessing context. Interactive POSIX
execution falls back to `fork`, because Python `spawn` cannot reload a `<stdin>` main module.

## Validation

### Automated tests

```text
44 passed
```

Coverage includes:

- structural-model validation;
- full profile coverage;
- multiple roles per card;
- commander tax;
- London-mulligan event generation;
- byte-identical event logs for fixed seeds;
- changed log hashes for changed seeds;
- Goldfish completion;
- one-, three-, four-, and five-player pods;
- explicit abort reporting;
- worker-count independence;
- stable, distinct derived seeds;
- valid placement ranges across multiple seeds.

### Scenario validation

Each scenario ran 24 iterations with two workers and master seed `20260804`.

| Scenario | Games | Completed | Aborted | Average turns |
|---|---:|---:|---:|---:|
| Korvold Goldfish | 24 | 24 | 0 | 7.667 |
| RogShai Goldfish | 24 | 24 | 0 | 14.417 |
| Three-player | 24 | 24 | 0 | 10.875 |
| Four-player | 24 | 24 | 0 | 14.208 |
| Five-player | 24 | 24 | 0 | 16.417 |

The multiplayer scenarios add synthetic Aggro, Control, and Engine decks solely to validate pod
mechanics and role interactions. Their results are not matchup claims.

### Rerun verification

The complete 120-game suite was run twice with identical configuration. A recursive SHA-256
comparison found all persisted result and JSONL files byte-identical.

### Performance observation

In the current container, a 1,000-game four-player batch with two workers completed in 11.36 seconds
and used approximately 137 MB maximum resident memory. This is an environment-specific engineering
observation, not a guaranteed benchmark. Full event persistence increases storage and I/O costs.

## Known limitations

- Colored mana is source-availability based, not exact tapping or pip assignment.
- Priority, stack ordering, targets, modes, replacement effects, state-based actions, and exact
  timing restrictions are intentionally abstracted.
- Counter and protection decisions use fixed structural heuristics.
- Board wipes operate on structural permanent value rather than exact destruction or exile rules.
- Combat uses aggregate pressure and blocking rather than individual attackers and blockers.
- Political behavior is not implemented.
- The role profiles are not yet calibrated against real playtests.
- The synthetic validation decks are not the known project opponents.
- Results cannot be called simulations of exact Magic games or empirical win rates.

## Next implementation boundary

Phase 4 should build pilot policies on top of legal structural actions without embedding strategic
choices directly in state mutation. Before optimization work, opponent precons and the marked
Cosmic Spider-Man completion should be imported as separate versioned profiles.
