# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed, uses XMage as Rules authority, and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when the exact WS-32 v1.0.2 XMage denominator is freshly runtime-qualified: mandatory Tax-3 = 3/3 PASS; total = 107/107 PASS; fail/unknown/not_run/mismatch = 0; historical PASS imported = 0; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; privacy/hidden-information PASS; RNG/replay PASS; unsupported production-reachable decision paths = 0; exact source locks/checksums/evidence exist; WS-39-modified quality surfaces are clean under unchanged configuration; `WS39_FINAL_HANDOFF.md` and this file are terminal. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-M-OPTIONAL-CONTROLLED-SINCE-FIX-VERIFIED`

## Source Lock

- XMage repo/branch: `moeendres-png/mage` / `foundry/ws39-commander-history-state-restore`
- XMage exact WS-39 head/tree: `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
- Commander Lab repo/branch: `moeendres-png/commander-playtest-lab` / `ws39/xmage-engine-remediation-requalification`
- Exact Tax-3 runtime head/tree: `c4b35c4c2a0017f3d3c57bc518a018c8049c456b` / `1ff6a5def7e2aa3751666002d56e585a6c937353`
- First exact Full-107 construction runtime head/tree: `e10ec2b0e6e9bd0068da73b93c512a9f52c1e672` / `e42f1514fdb6b1ba2de5d4ec596ba289f45793f2`
- Checkpoint-L regression head/tree: `c8018dda81c7cdefaabd65a855924584b4211cd9` / `c922acadbddca96244b2b27fbb78cbaba1789b4d`
- Checkpoint-M verified correction head/tree: `173718f5e7b91d69a1180a41b3ebe6e3356a2bf6` / `4ae0cd5c90c827dd09aaab38f6b55190486e83c7`
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

2. **Exact runtime infrastructure and Rules-RNG — COMPLETE / VERIFIED.**
   - Exact source locks, legal bootstrap, project/runtime dependency install, Maven classpath, fail-safe diagnostics and exact-head qualification-only Rules-RNG instrumentation are closed.
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
   - This closes the Checkpoint-L regression and proves `zone_position`, explicit `controlled_since_turn_began`, face-down and commander-history construction surfaces currently accepted by the probe without granting behavior credit.

## Current construction state after Checkpoint M

- 39 loaded-state records pass exact native construction/readback, with zero behavior runtime credit.
- 7 natural-start records are intentionally delegated to fresh natural executors.
- 61 records fail closed only because at least one requested native setup dimension is not yet implemented.
- 0 records currently fail native construction among the surfaces declared supported.

Fresh remaining unsupported dimension families from the exact 107 denominator include:

- `stack_state` / `zone:stack`: 24 records;
- `combat_state`: 12;
- `knowledge_grants`: 11;
- `zone_move_event`: 8;
- `elimination_trigger` / nonpositive-life setup: 6-class surface;
- `commander_damage_matrix`: 5;
- owner/controller split: 3;
- counters: 2;
- attachments: 2;
- extra-turn creation: 2;
- revealed zone: 1;
- additional temporal entry points including declare attackers/blockers, combat damage, upkeep/draw and postcombat main.

Counts must be recomputed after every bounded implementation; overlapping dimensions mean these family counts do not sum to 61.

## Stack-state audit prepared after Checkpoint M

- Exactly 24 denominator records require `stack_state` and `zone:stack`; six additional stack-bearing records in the frozen 135 bundle are out-of-scope Actual-Card records and receive no WS-39 credit.
- Historical v1.0.1 `apply_micro_stack_overlay.py` is provenance only. It uses genuine XMage `Spell`, `SpellAbility`, native target validation and `GameState.setZone(..., Zone.STACK)`, but its schema is incompatible with v1.0.2 (`source_object` vs `source_semantic_id`) and it receives zero historical credit.
- Current v1.0.2 stack records use player and semantic-object targets; target resolution must therefore map `P#` to native player UUIDs and semantic IDs to native object UUIDs and validate each through XMage target legality.
- `MICRO_COPY` contains two ordered stack objects, so stack cardinality/order must be natively read back.
- Two denominator records (`WS05-CMD-ZONE-LIB-YES/NO`) require Bant Charm mode `put_creature_on_bottom_of_owners_library`. XMage `BantCharm` represents this as a real second `Mode` with `PutOnLibraryTargetEffect(false)` and `TargetCreaturePermanent`; a string echo is insufficient. Native mode selection/readback is required.
- All frozen denominator stack entries currently assert `cast_complete=true` and `costs_paid=true`; unsupported values must remain fail closed.

## Important Decisions

- Construction equality is necessary but not sufficient for successor runtime PASS.
- Provider-request echo without native validation receives no credit.
- Optional frozen-state fields constrain native readback only when explicitly present.
- Every eventual 107/107 PASS needs native construction plus transaction/postcondition evidence for its frozen procedure.
- No historical same-ID PASS may be imported.
- Unsupported production-reachable decisions fail closed; no first/random/default/AI/GUI/parent fallback.
- No AF07 or Architecture Freeze claim. No merge.

## Quality

- Security and core Python tests/mypy/compile have fresh green predecessor evidence.
- Repository-wide Ruff contains inherited qualification debt; WS-39-owned files must be explicitly clean under unchanged configuration before terminal closure.

## Exact Next Action

1. Implement the bounded v1.0.2 `stack_state + zone:stack` native construction surface using XMage stack primitives, semantic source mapping, native player/object target validation, stack order/cardinality readback, and explicit native Bant Charm mode selection for the two library-mode records.
2. Keep `zone_move_event` and every other not-yet-implemented dimension fail closed even when stack construction becomes available.
3. Re-run the exact Full-107 construction workflow; seal, inspect and persist new counts before any subsequent setup-family remediation.
4. Continue bounded setup groups until all 107 records are construction-ready or naturally delegated with exact executor evidence.
5. Materialize fresh behavior executors for all 50 ordered native-operation sets; execute all 107 frozen v1.0.2 records with zero historical PASS import.
6. Remediate genuine runtime failures fail closed until 107/107 PASS and all required AF/category summaries are exact.
7. Close WS-39-local quality, seal final evidence/checksums, write `WS39_FINAL_HANDOFF.md`, and terminally update this file.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: Tax-3 is complete 3/3 fresh PASS and Checkpoint M establishes 39 exact loaded-state construction PASS + 7 natural-start delegations with zero construction failure. Sixty-one records still require unsupported setup surfaces, and full 107/107 fresh behavior runtime remains open.