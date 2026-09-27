# Pre-Simulation Architecture Migration Report

## Baseline

- audited default branch: `main`
- audited commit: `63d48bc635118e255d7585db0697694811dd849b`
- audited tree: `92485bf41d5c515002fcb623423016fbde9ca5ac`
- audited package: `1.23.3`
- migration package target chosen after audit: `1.24.0` (SemVer minor: additive public candidate contracts plus material pipeline semantics, while legacy APIs remain importable)

## Audit conclusion

The old productive concept mixed deck construction, heuristic search, Structural evidence and selection. Legal candidates could be absent from downstream evidence because they were never constructed, rejected by search acceptance, removed by archive/finalist limits, routed away by Structural fidelity, omitted from QD elites/racing survivors or excluded by confirmatory shortlist construction.

`PRE_SIMULATION_FILTER_INVENTORY.json` enumerates the identified mechanisms and future disposition.

## New productive boundary

Added `commander_lab.candidates`:

- `DeckCandidateSet` / versioned schema;
- canonical deck normalization/hash;
- read-only hard validator;
- exact duplicate deduplication with source provenance;
- lossless simulation queue builder;
- machine-readable invariant report;
- strict future XMage 4-player scenario interface;
- CLI `commander-lab candidates normalize|validate|prepare-simulation`.

The console entrypoint now layers the `candidates` CLI onto the existing CLI without invoking legacy whole-deck search.

## Legacy disposition

No historical search code was deleted solely to reduce code volume. Instead, the productive admission authority moved outside it. `whole_deck.decision_authority` records the new authority boundary:

- legacy whole-deck generation/search: deprecated for simulation input;
- Structural: diagnostic only;
- Tactical: bounded diagnostic/test support;
- fidelity: diagnostic/metadata;
- QD/racing/Pareto: future post-game evidence tools, not pre-game gates.

## Canonical truth boundary

No canonical deck/inventory/allocation/opponent files are modified by this migration. Hard validation reads current project routing and physical/legal truth only.

## Gameplay boundary

No official game was run. No Structural/Tactical campaign was run. No XMage result was synthesized. No sealed holdout was opened.

## Remaining work after this migration

A separate phase must implement:

1. queue → XMage deck/scenario materialization;
2. autonomous 4-player XMage lifecycle;
3. Our Pilots as external decision controllers;
4. deterministic bridge/action synchronization and recovery;
5. all-candidate initial gameplay screening;
6. gameplay-evidence persistence and provenance;
7. post-simulation racing/comparison/decision;
8. validated external-rules differential/end-to-end fixtures.
