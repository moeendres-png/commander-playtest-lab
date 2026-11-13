# Forge current-boundary scenario lane (issue #455)

`FORGE-CURRENT-BOUNDARY-SCENARIO-LANE-20261001`

Objective: build the smallest Lab-side producer that consumes the **existing
Forge-authored `ScenarioBootstrap` seam** and measures exactly what it can and
cannot prove, without creating a second Rules engine and without modifying Forge.

Parent authority: #255. Workstream issue: #455. Branch:
`hardening/forge-scenario-lane-20261001`.

`PRODUCTION_PROVIDER = NOT_SELECTED`
`ARCHITECTURE_FREEZE = NOT_CLAIMED`

## What this lane is

* A Lab-side **transport and evidence pipeline** for the Forge scenario seam:
  it binds the exact pinned Forge identities, derives the bootstrap capability
  matrix from the pinned bridge source blob, translates an effective FULL107
  record into the supported `neutral_initial_state` subset, drives the engine
  with engine-authored decisions only, compares authoritative readback to the
  requested state field by field, and evaluates a bounded set of terminal
  obligations from engine-reported facts.
* A **fail-closed classifier**: every requested-state dimension the bootstrap
  cannot represent is an exact `UNSUPPORTED_DIMENSION` finding. Nothing is
  silently dropped, no fixture is weakened, and construction alone earns zero
  row credit.

## What this lane is not

* Not a second Rules engine: legality, costs, priority, stack, triggers,
  layers, SBAs and outcomes remain Forge's.
* Not a generic state injector: the lane sends only the fields the pinned
  bootstrap actually validates.
* Not a second decision-selector surface: decision families beyond
  pass/mulligan/starting-player/cost-order are recorded as exact execution
  blockers owned by the shared mid-game selector workstream.
* Not a Forge repair path: the Forge repository and Forge PR #11 are read-only.

## Files

| Path | Purpose |
| --- | --- |
| `src/commander_lab/qualification/current_boundary/forge_scenario_lane.py` | Producer, capability matrix, dimension classifier, readback comparison, decision driver, obligation evaluators |
| `scripts/run_forge_scenario_lane.py` | CLI: structural census, live capability probe, per-row receipts |
| `tests/qualification/test_forge_scenario_lane.py` | Unit/integration tests, fail-before, wrong-reason controls |
| `docs/forge_scenario_lane_20261001/receipts/*.json` | Machine-readable receipts (this run) |
| `.foundry/forge-scenario-lane-20261001.yaml` | Durable state file |

## How to run

Structural census only (no engine):

```bash
python3 scripts/run_forge_scenario_lane.py
```

Runtime (explicit clean Forge checkout at the bound bridge source; there is no
ambient default):

```bash
FORGE_WORKSPACE=/path/to/pinned/forge \
  python3 scripts/run_forge_scenario_lane.py --capability-probe --wave --eligible
```

`--row <FIXTURE_ID>` attempts a single effective row. Receipts are written to
`docs/forge_scenario_lane_20261001/receipts/` unless `--out` overrides it.

## Current result at this epoch

* Structural census over the effective denominator (contract
  `commander-lab.full107/1.0.9-successor`): 107 rows.
  * 94 `UNSUPPORTED_DIMENSION` (at least one requested-state field the current
    bootstrap cannot represent),
  * 4 constructible but not observable on the generic readback,
  * 9 credit-eligible (constructed and observable at the requested checkpoint).
* Runtime on the exact pinned Forge bridge (`20e3e1f7…`, Rules-Core
  `bb0a740d…`), 16 rows attempted:
  * 6 `EXECUTED_OBLIGATION_OBSERVED`,
  * 3 executed with `OBLIGATION_NOT_OBSERVABLE` (no observation contract in
    this lane; construction and checkpoint are recorded),
  * 7 `UNSUPPORTED_DIMENSION` with exact per-field blockers, including live
    engine rejection proofs for stack/decision injection.

The seven-row initial wave (`MICRO_COPY`, `MICRO_COSTS`, `MICRO_MODES`,
`MICRO_REPLACEMENT`, `MICRO_ZONE_CHANGES`, `WS05-MP-BLOCK-4`,
`WS05-MP-COMBAT-4`) is **structurally blocked by the current bootstrap
contract**, not by an unexercised execution path: every blocker is named and
evidenced per row (see `PER_ROW_EXECUTION_MATRIX.md` and
`UNSUPPORTED_DIMENSION_MATRIX.md`).

## Evidence semantics

* Receipts are `FRESH_CURRENT_BOUNDARY_EXECUTION` on the exact identities above.
* Historical Forge WSR evidence and native suites are supporting evidence only.
* Import, construction and a green engine suite are not obligation evidence.
* `UNKNOWN`/`PARTIAL`/`NOT_RUN` are never presented as PASS.
