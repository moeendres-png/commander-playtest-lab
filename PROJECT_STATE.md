# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed, uses XMage as Rules authority, and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when the exact WS-32 v1.0.2 XMage denominator is freshly runtime-qualified: mandatory Tax-3 = 3/3 PASS; total = 107/107 PASS; fail/unknown/not_run/mismatch = 0; historical PASS imported = 0; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; privacy/hidden-information PASS; RNG/replay PASS; unsupported production-reachable decision paths = 0; exact source locks/checksums/evidence exist; WS-39-modified quality surfaces are clean under unchanged configuration; `WS39_FINAL_HANDOFF.md` and this file are terminal. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-N-STACK-WIRING-BUILD-GREEN-CLASSPATH-PATH-BLOCKED`

## Source Lock

- XMage repo/branch: `moeendres-png/mage` / `foundry/ws39-commander-history-state-restore`
- XMage exact WS-39 head/tree: `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
- Commander Lab repo/branch: `moeendres-png/commander-playtest-lab` / `ws39/xmage-engine-remediation-requalification`
- Exact Tax-3 runtime head/tree: `c4b35c4c2a0017f3d3c57bc518a018c8049c456b` / `1ff6a5def7e2aa3751666002d56e585a6c937353`
- First exact Full-107 construction runtime head/tree: `e10ec2b0e6e9bd0068da73b93c512a9f52c1e672` / `e42f1514fdb6b1ba2de5d4ec596ba289f45793f2`
- Checkpoint-L regression head/tree: `c8018dda81c7cdefaabd65a855924584b4211cd9` / `c922acadbddca96244b2b27fbb78cbaba1789b4d`
- Checkpoint-M verified correction head/tree: `173718f5e7b91d69a1180a41b3ebe6e3356a2bf6` / `4ae0cd5c90c827dd09aaab38f6b55190486e83c7`
- Checkpoint-N stack-wiring staging head/tree: `54d75a5fcd501255cd1222d318f4ab5671e8cef9` / `d4302dba28f7c39ec33efc7b91813063b1f2370a`
- Draft PR: `#153`; no merge authorized.
- WS32 contract: `commander-lab.semantic-fixture-materialization/1.0.2`
- WS32 freeze commit/tree: `038d0f38635eecee4e331c99af41f148de267a26` / `0d160128119f2bad30b220a17c43419b50b7edbe`
- Canonical materialization digest: `ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23`
- Materialization file SHA256: `0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261`
- Exact successor denominator: 107 unique records. The frozen bundle itself contains 135 records; WS-39 excludes 28 Actual-Card records and includes only `CARD_02` from the Actual-Card family.

## Work Completed / Verified

1. **Native XMage Commander-history restoration — COMPLETE / VERIFIED.**
   - `CommanderPlaysCountState` + `CommanderPlaysCountWatcher.restoreStateForGameLoad(...)`.
   - Focused `CommanderPlaysCountStateRestoreTest` repeatedly PASS at exact WS-39 XMage head.
   - No synthetic historical cast events.

2. **Exact runtime infrastructure and Rules-RNG baseline — COMPLETE / VERIFIED.**
   - Exact source locks, legal bootstrap, project/runtime dependency install, fail-safe diagnostics and exact-head qualification-only Rules-RNG instrumentation are closed for the verified predecessor executions.
   - Rules randomness remains XMage-owned.

3. **Mandatory Tax-3 — COMPLETE / 3-of-3 fresh PASS.**
   - Run `33772428630`, job `100705752538`, workflow/job SUCCESS.
   - Artifact id `9900377069`, digest `sha256:5b76015f49bcbabd8482b9f978003d24057e1648fa2c755f1d2269d6ef733ad1`.
   - `WS39_TAX3_RESULTS.json` SHA256 `b3b89d32952402471a8800d80dfba8d5d9aa8f43db1db56d0926482c8b8d6a4b`.
   - Tax-2, Tax-4 and Partner-Tax all `FRESH_WS39_RUNTIME_PASS`; `historical_pass_imported=false`.

4. **Full-107 immutable census — VERIFIED / ZERO RUNTIME CREDIT.**
   - Exact denominator 107; 63 unique native operation names; 50 unique ordered native-operation sets.
   - Census grants no runtime credit.

5. **First exact Full-107 native-construction runtime probe — COMPLETE / VERIFIED.**
   - Run `33775617820`, job `100716451124`, head/tree `e10ec2b0e6e9bd0068da73b93c512a9f52c1e672` / `e42f1514fdb6b1ba2de5d4ec596ba289f45793f2`: SUCCESS.
   - Artifact id `9901713320`, digest `sha256:5ccd849a7235d7007bb2c437c29ff9dbfd1888562d26becc0f4e85fdf330a106`.
   - Result: 15 native setup PASS/no credit; 7 natural-start delegated; 85 unsupported; 0 native construction failures.

6. **Checkpoint-L `zone_position + controlled_since_turn_began` regression — COMPLETE / CLASSIFIED.**
   - Implementation head/tree `c8018dda81c7cdefaabd65a855924584b4211cd9` / `c922acadbddca96244b2b27fbb78cbaba1789b4d`.
   - Run `33777054968`, job `100721273753`: SUCCESS; artifact id `9902427299`, digest and downloaded ZIP SHA256 `7401f465c8740d1bfd378640b50144b4b642acb5d62fa6d7dad865576b2a4eeb`.
   - Result: 6 setup PASS/no credit; 7 delegated; 61 unsupported; 33 native construction FAIL.
   - All 33 failures were the same qualification-overlay overconstraint: omitted optional `controlled_since_turn_began` was silently interpreted as frozen false.

7. **Checkpoint-M optional-field correction — COMPLETE / VERIFIED.**
   - Remediation commit/tree `173718f5e7b91d69a1180a41b3ebe6e3356a2bf6` / `4ae0cd5c90c827dd09aaab38f6b55190486e83c7`.
   - Change is bounded to validation: `Permanent.wasControlledFromStartOfControllerTurn()` is compared only when the frozen object explicitly contains `controlled_since_turn_began`. Explicit true is still loaded natively through `PermanentImpl.removeSummoningSickness()` and read back through XMage; omitted field is unconstrained rather than converted to false.
   - Workflow `WS39 Full107 Native Construction Probe`, run `33786273981`, job `100751708633`: construction step, sealing and artifact upload all SUCCESS at the exact head.
   - Artifact `ws39-full107-construction-173718f5e7b91d69a1180a41b3ebe6e3356a2bf6`, id `9905927349`.
   - GitHub artifact digest and downloaded ZIP SHA256 both `708946bcfd73bb44d8c9288b7b71ea9699362030ba6c75cf29d3c0081eef520c`.
   - Artifact source locks: provider `173718f5e7b91d69a1180a41b3ebe6e3356a2bf6` / `4ae0cd5c90c827dd09aaab38f6b55190486e83c7`; XMage `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`.
   - `WS39_FULL107_CONSTRUCTION_PROBE.json` SHA256 `2a1e5d587bd3a96a9aeb5884e261b88db9ded498a76b0d5156e2a798546ace70`; all ten entries in artifact `SHA256SUMS` independently verified with zero mismatch.
   - Fresh exact result: **39 `NATIVE_SETUP_PASS_NO_RUNTIME_CREDIT`; 7 `DEFERRED_TO_FRESH_NATURAL_EXECUTOR`; 61 `FAIL_CLOSED_UNSUPPORTED_NATIVE_DIMENSION`; 0 `FAIL_CLOSED_NATIVE_CONSTRUCTION`**.
   - `historical_pass_imported=false`; `runtime_credit_granted=false`.

8. **Checkpoint-N bounded stack-wiring staging — BUILD GREEN / INFRASTRUCTURE BLOCKED BEFORE PROBE.**
   - Stack implementation commits preceding staging: `5b15ba502774013b50e4726d1b9bb1ade41d5697` (new v1.0.2 stack overlay), `062c3371a4d402450fcc86909ac30dcc93e41b71` (canonical v1.0.2 stack transport), and staging head/tree `54d75a5fcd501255cd1222d318f4ab5671e8cef9` / `d4302dba28f7c39ec33efc7b91813063b1f2370a` (workflow wiring).
   - `run_full107_construction_probe.py` intentionally still does **not** declare `stack_state` or `zone:stack` supported. Therefore the new stack code cannot gain construction credit until a dedicated fresh staging run proves the bridge path and a later atomic enablement is executed.
   - Workflow run `33787971776`, job `100757275170`, exact head `54d75a5fcd501255cd1222d318f4ab5671e8cef9`: overall FAILURE.
   - Fresh step status: checkout/provider identity/WS32 lock/XMage lock/JDK/Python/project install/source-lock verification/native `CommanderPlaysCountStateRestoreTest`/qualification overlays/XMage build/qualification bridge build all PASS. Step `Materialize runtime classpath` FAIL. Full-107 construction probe was SKIPPED. Evidence sealing and artifact upload PASS.
   - Exact classpath failure is infrastructure-only: Maven `dependency:copy-dependencies` reports BUILD SUCCESS and dependencies already present in destination, but the following assertion fails with `find: ‘target/dependency’: No such file or directory`. Logs show dependency output below a nested `engine-bridge/engine-bridge/target/dependency` path while the assertion checks `engine-bridge/target/dependency` from the declared working directory.
   - No successor record was executed in this run. No stack semantic failure was observed. No new construction or behavior credit is granted.
   - Artifact `ws39-full107-construction-54d75a5fcd501255cd1222d318f4ab5671e8cef9`, id `9906583541`.
   - Fresh GitHub artifact digest and independently re-downloaded ZIP SHA256 both `f0347ec21a9de4fede7553dbbfc9295bbfcfbee5a3c765658888b027d2456e4f`.
   - Artifact source locks: provider commit/tree `54d75a5fcd501255cd1222d318f4ab5671e8cef9` / `d4302dba28f7c39ec33efc7b91813063b1f2370a`; XMage commit/tree `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`.
   - Artifact contains provider/XMage locks, qualification bridge patch, exact Rules-RNG instrumentation evidence and native Commander-history surefire evidence; it correctly contains no `WS39_FULL107_CONSTRUCTION_PROBE.json` because the run failed before that step.
   - Every entry in artifact `SHA256SUMS` was independently reverified after normalizing the archived path prefix, with zero mismatch.
   - Classification: **WS39 qualification-workflow classpath output-path defect**, not Rules-Core, not stack semantics, not dependency resolution, and not a provider capability result.
   - `historical_pass_imported=false` remains authoritative; this run grants zero runtime credit.

## Current construction state after Checkpoint N

Last successfully executed fresh construction census remains Checkpoint M:

- 39 loaded-state records pass exact native construction/readback, with zero behavior runtime credit.
- 7 natural-start records are intentionally delegated to fresh natural executors.
- 61 records fail closed because at least one requested native setup dimension remains unsupported by the currently enabled probe.
- 0 records fail native construction among the currently enabled surfaces.

The bounded stack overlay now compiles and the exact XMage + qualification bridge build succeeds, but **stack support is intentionally still disabled in the construction capability declaration** until the classpath workflow path is repaired and a fresh staging run completes through the probe.

Fresh remaining unsupported dimension families include `stack_state` / `zone:stack`, combat/temporal combat, knowledge grants, zone-move events, elimination/nonpositive-life setup, commander-damage matrices, owner/controller split, counters, attachments, extra turns, revealed zone and additional temporal entry points. Counts must be recomputed only from the next successful exact probe because dimensions overlap.

## Stack-state audit / implementation notes

- Exactly 24 denominator records require `stack_state` and `zone:stack`; six additional stack-bearing records in the frozen 135 bundle are out-of-scope Actual-Card records and receive no WS-39 credit.
- Historical v1.0.1 `apply_micro_stack_overlay.py` is provenance only and receives zero historical credit.
- Current v1.0.2 stack overlay constructs genuine XMage `Spell` objects, binds provider-neutral semantic source identities, validates targets through XMage target legality, preserves stack order/cardinality, and performs native readback.
- Frozen target identities can be players (`P#`) or semantic objects; the loader resolves each to the corresponding native UUID and rejects non-unique/unavailable mappings.
- `MICRO_COPY` requires ordered two-object stack readback.
- `WS05-CMD-ZONE-LIB-YES/NO` requires Bant Charm's genuine native second mode (`PutOnLibraryTargetEffect(false)` / `TargetCreaturePermanent`). The overlay selects by normalized native mode semantics with exactly-one-match enforcement; it does not select a first/default mode.
- All denominator stack entries currently require `cast_complete=true` and `costs_paid=true`; unsupported values fail closed.

## Important Decisions

- Construction equality is necessary but not sufficient for successor runtime PASS.
- Provider-request echo without native validation receives no credit.
- Optional frozen-state fields constrain native readback only when explicitly present.
- Staged implementation does not become a declared capability merely because it compiles. Capability is enabled only after the exact staging path reaches a fresh native probe.
- Every eventual 107/107 PASS needs native construction plus transaction/postcondition evidence for its frozen procedure.
- No historical same-ID PASS may be imported.
- Unsupported production-reachable decisions fail closed; no first/random/default/AI/GUI/parent fallback.
- No AF07 or Architecture Freeze claim. No merge.

## Quality

- Security and core Python tests/mypy/compile have fresh green predecessor evidence.
- Repository-wide Ruff contains inherited qualification debt; WS-39-owned files must be explicitly clean under unchanged configuration before terminal closure.

## Exact Next Action

1. Inspect `engine-bridge/pom.xml` and repair only the WS39 construction-workflow runtime-classpath output/assertion path so the copied dependency directory is unambiguous and anchored to the repository workspace.
2. Re-run the stack-wiring staging workflow with stack capability declaration still disabled. Require exact source locks, native Commander-history regression, XMage build, bridge build, classpath materialization, full 107 construction census, evidence seal and checksums to complete.
3. Persist the fresh staging result before changing `CURRENT_NATIVE_DIMENSIONS`.
4. Only after staging is green, atomically enable `stack_state` and `zone:stack` in the construction probe and execute a fresh exact 107 construction run.
5. Remediate concrete stack construction failures one at a time, persisting each bounded result.
6. Continue bounded setup groups until all 107 records are construction-ready or naturally delegated with exact executor evidence.
7. Materialize fresh behavior executors for all 50 ordered native-operation sets; execute all 107 frozen v1.0.2 records with zero historical PASS import.
8. Remediate genuine runtime failures fail closed until 107/107 PASS and all required AF/category summaries are exact.
9. Close WS-39-local quality, seal final evidence/checksums, write `WS39_FINAL_HANDOFF.md`, and terminally update this file.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: Tax-3 is complete 3/3 fresh PASS. Checkpoint M remains the last successful exact Full-107 construction census at 39 native setup PASS + 7 natural-start delegations + 61 unsupported + 0 construction failures. Checkpoint N proves the bounded stack overlay compiles and both exact XMage and bridge builds pass, but a qualification-workflow classpath output-path defect prevents the staging run from reaching the 107er probe; stack support therefore remains deliberately disabled and receives no credit.