# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed, uses XMage as Rules authority, and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when the exact WS-32 v1.0.2 XMage denominator is freshly runtime-qualified: mandatory Tax-3 = 3/3 PASS; total = 107/107 PASS; fail/unknown/not_run/mismatch = 0; historical PASS imported = 0; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; privacy/hidden-information PASS; RNG/replay PASS; unsupported production-reachable decision paths = 0; exact source locks/checksums/evidence exist; WS-39-modified quality surfaces are clean under unchanged configuration; `WS39_FINAL_HANDOFF.md` and this file are terminal. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-K-FIRST-FULL107-CONSTRUCTION-RUNTIME`

## Source Lock

- XMage repo/branch: `moeendres-png/mage` / `foundry/ws39-commander-history-state-restore`
- XMage exact WS-39 head/tree: `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
- Commander Lab repo/branch: `moeendres-png/commander-playtest-lab` / `ws39/xmage-engine-remediation-requalification`
- Exact Tax-3 runtime head/tree: `c4b35c4c2a0017f3d3c57bc518a018c8049c456b` / `1ff6a5def7e2aa3751666002d56e585a6c937353`
- First exact Full-107 construction runtime head/tree: `e10ec2b0e6e9bd0068da73b93c512a9f52c1e672` / `e42f1514fdb6b1ba2de5d4ec596ba289f45793f2`
- Draft PR: `#153`; no merge authorized.
- WS32 contract: `commander-lab.semantic-fixture-materialization/1.0.2`
- WS32 freeze commit/tree: `038d0f38635eecee4e331c99af41f148de267a26` / `0d160128119f2bad30b220a17c43419b50b7edbe`
- Canonical materialization digest: `ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23`
- Materialization file SHA256: `0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261`
- Exact successor denominator: 107 unique records.

## Work Completed / Verified

1. **Native XMage Commander-history restoration — COMPLETE / VERIFIED.**
   - `CommanderPlaysCountState` + `CommanderPlaysCountWatcher.restoreStateForGameLoad(...)`.
   - Focused `CommanderPlaysCountStateRestoreTest` repeatedly PASS at exact WS-39 XMage head.
   - No synthetic historical cast events.

2. **Exact runtime infrastructure and Rules-RNG — COMPLETE / VERIFIED.**
   - Exact source locks, legal bootstrap, project/runtime dependency install, Maven classpath, fail-safe diagnostics and exact-head qualification-only Rules-RNG instrumentation are closed.
   - Rules randomness remains XMage-owned.

3. **Mandatory Tax-3 — COMPLETE / 3-of-3 fresh PASS.**
   - Run `33772428630`, job `100705752538`, workflow/job SUCCESS.
   - Artifact `ws39-engine-runtime-c4b35c4c2a0017f3d3c57bc518a018c8049c456b`, id `9900377069`, digest `sha256:5b76015f49bcbabd8482b9f978003d24057e1648fa2c755f1d2269d6ef733ad1`.
   - `WS39_TAX3_RESULTS.json` SHA256 `b3b89d32952402471a8800d80dfba8d5d9aa8f43db1db56d0926482c8b8d6a4b`.
   - Tax-2, Tax-4 and Partner-Tax all `FRESH_WS39_RUNTIME_PASS`; `historical_pass_imported=false`.

4. **Full-107 immutable census — VERIFIED / ZERO RUNTIME CREDIT.**
   - Exact denominator 107; 63 unique native operation names; 50 unique ordered native-operation sets.
   - Census is bound into WS-39 evidence and explicitly grants no runtime credit.

5. **First exact Full-107 native-construction runtime probe — COMPLETE / VERIFIED.**
   - Workflow `WS39 Full107 Native Construction Probe`, run `33775617820`, job `100716451124`: SUCCESS.
   - Exact runtime head `e10ec2b0e6e9bd0068da73b93c512a9f52c1e672`.
   - Artifact `ws39-full107-construction-e10ec2b0e6e9bd0068da73b93c512a9f52c1e672`, id `9901713320`, artifact digest `sha256:5ccd849a7235d7007bb2c437c29ff9dbfd1888562d26becc0f4e85fdf330a106`.
   - `WS39_FULL107_CONSTRUCTION_PROBE.json` SHA256 `926205f89a9c11555a77959a0f03f7889dac59f3b192395821c9a2ca0d606fa8`.
   - Exact result: 15 `NATIVE_SETUP_PASS_NO_RUNTIME_CREDIT`; 7 `DEFERRED_TO_FRESH_NATURAL_EXECUTOR`; 85 `FAIL_CLOSED_UNSUPPORTED_NATIVE_DIMENSION`; 0 unexpected native construction failures.
   - Total `native_setup_ready=true` rows = 22 (15 actual loaded-state construction + 7 delegated natural-start rows).
   - `historical_pass_imported=false`, `runtime_credit_granted=false`.

## Exact unsupported native-dimension census from runtime artifact

- `zone_position`: 28
- `stack_state`: 24
- `zone:stack`: 24
- `controlled_since_turn_began`: 23
- `combat_state`: 12
- `knowledge_grants`: 11
- `zone_move_event`: 8
- `elimination_trigger`: 6
- `nonpositive_life`: 6
- `temporal:combat/declare_attackers`: 5
- `commander_damage_matrix`: 5
- `owner_controller_split`: 3
- `counters`: 2
- `temporal:combat/declare_blockers`: 2
- `attachments`: 2
- `extra_turn_creation`: 2
- `temporal:postcombat_main/main`: 2
- `temporal:beginning/draw`: 2
- `zone:revealed`: 1
- `temporal:beginning/upkeep`: 1
- `temporal:combat/combat_damage`: 1

## Current remediation ordering

The next bounded native setup group is `zone_position + controlled_since_turn_began` because both can be represented/read back using existing XMage state primitives without reimplementing Magic rules:
- library position is native library order and already observable through `Player.getLibrary().getCardList()` / privileged replay state;
- controlled-since-turn-began is native `Permanent.wasControlledFromStartOfControllerTurn()` state; true can be established through XMage's native permanent state method used to remove summoning sickness, while false is the native ETB default.

The provider translation must begin carrying `face_down`, `zone_position` and `controlled_since_turn_began` explicitly. The loader must validate library positions and controlled-since state natively before those dimensions are promoted to construction-ready.

## Important Decisions

- Construction equality is necessary but not sufficient for successor runtime PASS.
- Provider-request echo without native validation receives no credit.
- Every eventual 107/107 PASS needs native construction and transaction/postcondition evidence for its frozen procedure.
- No historical same-ID PASS may be imported.
- Unsupported production-reachable decisions fail closed; no first/random/default/AI/GUI/parent fallback.
- No AF07 or Architecture Freeze claim. No merge.

## Quality

- Security and core Python tests/mypy/compile have fresh green predecessor evidence.
- Repository-wide Ruff contains inherited qualification debt; WS-39-owned files must be explicitly clean under unchanged configuration before terminal closure.

## Exact Next Action

1. Implement qualification-only native construction/readback for `zone_position` and `controlled_since_turn_began`, and make `canonical_v102.py` carry the already-supported `face_down` field explicitly.
2. Promote only those dimensions that receive actual native readback validation in `run_full107_construction_probe.py`.
3. Re-run the exact Full-107 construction workflow and checkpoint the new exact counts.
4. Continue bounded setup groups until all 107 records are construction-ready.
5. Materialize fresh behavior executors for the 50 ordered native-operation sets; execute all 107 frozen v1.0.2 records with zero historical PASS import.
6. Remediate genuine runtime failures fail-closed until 107/107 PASS and required AF/category summaries are exact.
7. Close WS-39-local quality, seal final evidence/checksums, write `WS39_FINAL_HANDOFF.md`, and terminally update this file.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: Tax-3 is complete 3/3 fresh PASS. Full-107 construction has first exact runtime evidence at 15 loaded-state PASS + 7 delegated natural-start + 85 unsupported; full 107/107 behavior runtime remains open.
