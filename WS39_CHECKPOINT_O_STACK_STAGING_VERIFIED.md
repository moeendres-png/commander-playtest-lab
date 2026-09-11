# WS-39 CHECKPOINT O — STACK STAGING VERIFIED

## Checkpoint

`WS39-CHECKPOINT-2026-09-03-O-STACK-WIRING-STAGING-VERIFIED`

## Scope

This checkpoint closes only the bounded WS-39 stack-wiring staging prerequisite. It grants no new successor runtime PASS and does not yet declare `stack_state` / `zone:stack` construction capability.

## Exact Source Lock

- Commander Lab staging commit: `e0c51838745d3dbe417505ebfad37919d261ead6`
- Commander Lab staging tree: `9c90af6b3f1e59f460917f8fe77a3f017933d879`
- XMage commit: `7bde812727817723616c575759f39bfc4cda4607`
- XMage tree: `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
- WS32 freeze commit: `038d0f38635eecee4e331c99af41f148de267a26`
- WS32 freeze tree: `0d160128119f2bad30b220a17c43419b50b7edbe`
- WS32 materialization: `commander-lab.semantic-fixture-materialization/1.0.2`
- exact WS39 denominator: `107`

## Infrastructure Remediation Proven

The Checkpoint-N classpath defect was repaired only in `.github/workflows/ws39-full107-construction.yml` by anchoring both Maven `dependency:copy-dependencies` output and the subsequent JAR assertion to `${{ github.workspace }}/engine-bridge/target/dependency`.

`engine-bridge/pom.xml`, XMage source, Rules-Core semantics and stack capability declaration were not changed by this remediation.

## Fresh Runtime Evidence

- workflow: `WS39 Full107 Native Construction Probe`
- run: `33792862430`
- job: `100773397031`
- result: `SUCCESS`

Fresh step results:

- exact WS39 checkout: PASS
- provider identity: PASS
- exact WS32 freeze checkout: PASS
- exact WS39 XMage checkout: PASS
- Python/JDK setup: PASS
- Commander Lab runtime dependency install: PASS
- immutable source lock verification: PASS
- native `CommanderPlaysCountStateRestoreTest`: PASS
- exact qualification overlays, including staged stack overlay: PASS
- exact XMage build: PASS
- qualification bridge build: PASS
- runtime classpath materialization: PASS
- fail-closed Full-107 construction probe: PASS
- evidence seal: PASS
- artifact upload: PASS

## Artifact

- artifact id: `9908372945`
- artifact name: `ws39-full107-construction-e0c51838745d3dbe417505ebfad37919d261ead6`
- GitHub artifact digest: `sha256:10747f1fceb55b1cf50f7049f04729f596636943522ecfca3d771eb39fd5a281`
- independently downloaded ZIP SHA256: `10747f1fceb55b1cf50f7049f04729f596636943522ecfca3d771eb39fd5a281`
- `WS39_FULL107_CONSTRUCTION_PROBE.json` SHA256: `1b046b7dc0c8b8e125216e5d23ba5955aa22df204f542be7de9b71c40f96092f`
- all 10 internal `SHA256SUMS` entries independently reverified: `PASS / 0 mismatches`

Artifact source-lock files independently read back:

- `PROVIDER_COMMIT.txt`: `e0c51838745d3dbe417505ebfad37919d261ead6`
- `PROVIDER_TREE.txt`: `9c90af6b3f1e59f460917f8fe77a3f017933d879`
- `XMAGE_COMMIT.txt`: `7bde812727817723616c575759f39bfc4cda4607`
- `XMAGE_TREE.txt`: `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`

## Construction Census

Because stack capability remained intentionally disabled during staging, the fresh census correctly reproduced the prior enabled capability boundary:

- `NATIVE_SETUP_PASS_NO_RUNTIME_CREDIT`: `39`
- `DEFERRED_TO_FRESH_NATURAL_EXECUTOR`: `7`
- `FAIL_CLOSED_UNSUPPORTED_NATIVE_DIMENSION`: `61`
- `FAIL_CLOSED_NATIVE_CONSTRUCTION`: `0`
- record count: `107`
- historical PASS imported: `false`
- runtime credit granted: `false`

Current declared native dimensions in the artifact:

- `commander_history`
- `controlled_since_turn_began`
- `face_down`
- `zone_position`

## Result

`STACK_WIRING_STAGING = PASS`

`STACK_CONSTRUCTION_CAPABILITY_ENABLED = FALSE`

`NEW_SUCCESSOR_RUNTIME_CREDIT = 0`

`HISTORICAL_PASS_IMPORTED = FALSE`

## Exact Next Action

Atomically add only `stack_state` and `zone:stack` to `CURRENT_NATIVE_DIMENSIONS` in `run_full107_construction_probe.py`, execute a fresh exact 107-record construction probe, inspect every newly attempted stack record, and fail closed on any native construction mismatch. Persist that result before any further setup-family remediation.

## Global WS-39 Status

`TASK_COMPLETE = NO`

`WS39_STATUS = PARTIAL`

`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

AF07 and Architecture Freeze remain explicitly out of scope.