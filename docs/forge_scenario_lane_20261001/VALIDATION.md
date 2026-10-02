# Validation record — Forge scenario lane (epoch 20261001)

## Environment

* Lab worktree: `/home/moeen/code/lab-forge-scenario-lane-20261001`,
  branch `hardening/forge-scenario-lane-20261001`.
* Audit base: `bcd903f2…` (tree `b7d44a0b…`); current main at authorization was
  merged in normally (`a9159084`, contract `1.0.9-successor`) before any
  evidence was produced.
* Executor: OpenCode Go / DeepSeek V4.1 Flash MAX (`opencode-go/deepseek-v4.1-flash`,
  native `max`).
* Forge execution checkout: an explicit clean checkout at the bound bridge
  commit `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c`; provided via
  `FORGE_WORKSPACE`, verified by the lane (Rules-Core tree equivalence +
  `forge-protocol2-bridge` module tree equality + clean porcelain).
* Runtime state: engine processes run in a dedicated `.runtime/engine` cwd
  outside the Git worktree; one bridge process at a time.

## Commands and results

### Structural census (no engine)

```bash
python3 scripts/run_forge_scenario_lane.py
```

Result: `{'UNSUPPORTED_DIMENSION': 94, 'CREDIT_ELIGIBLE': 9,
'CONSTRUCTIBLE_NOT_OBSERVABLE': 4}`, denominator 107, contract
`commander-lab.full107/1.0.9-successor`.

### Focused tests

```bash
python3 -m pytest tests/qualification/test_forge_scenario_lane.py -q
```

Result: `25 passed`.

### Runtime attempt (exact pinned bridge)

```bash
FORGE_WORKSPACE=<clean checkout at 20e3e1f7…> \
  python3 scripts/run_forge_scenario_lane.py --capability-probe --wave --eligible
```

Result:

```
execution classifications: {'UNSUPPORTED_DIMENSION': 7,
 'OBLIGATION_NOT_OBSERVABLE': 3, 'EXECUTED_OBLIGATION_OBSERVED': 6}
```

Receipts written to `docs/forge_scenario_lane_20261001/receipts/`.

Provider echo at execution: `engine_commit = 20e3e1f7…`,
`engine_build_tree = 000066890d…`, `engine_commit_verified = true`,
`bridge_version = 2.0.14-ws-a1d-h4f`, Java 21.

## Evidence classification

| Evidence | Class |
| --- | --- |
| Runtime receipts (`EXECUTION_RECEIPT.json`) | `FRESH_CURRENT_BOUNDARY_EXECUTION` / `DIRECTLY_VERIFIED` for the recorded engine facts |
| Capability matrix | `CODE_DERIVED` from the pinned source blob + `DIRECTLY_VERIFIED` by live rejection probes |
| Structural census | `CODE_DERIVED` over the effective materialization |
| Historical Forge WSR evidence | supporting only, not re-credited |
| Forge native suites | supporting only |

## Limitations and non-claims

* This lane did not modify Forge. It does not claim any Forge Rules-core
  behavior beyond what the recorded engine readback/decsions show.
* `OBLIGATION_NOT_OBSERVABLE` rows are **not** PASS; construction and checkpoint
  are recorded but no obligation credit is granted.
* `ALLOWED_VARIANCE` is used only where the fixture itself declares the native
  cause (`NATIVE_CAUSE_DECLARED_PLAYER_LOSS` + terminal postconditions); the
  variance source is recorded per field and the overall checkpoint verdict is
  never labelled `EXACT`.
* No shared current-boundary runner/assembler/contract/manifest was modified
  while foreign writers were active. Phase 2 integration is not started.
* `PRODUCTION_PROVIDER = NOT_SELECTED`, `ARCHITECTURE_FREEZE = NOT_CLAIMED`.
