# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed, uses XMage as Rules authority, and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when the exact WS-32 v1.0.2 XMage denominator is freshly runtime-qualified: mandatory Tax-3 = 3/3 PASS; total = 107/107 PASS; fail/unknown/not_run/mismatch = 0; historical PASS imported = 0; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; privacy/hidden-information PASS; RNG/replay PASS; unsupported production-reachable decision paths = 0; exact source locks/checksums/evidence exist; WS-39-modified quality surfaces are clean under unchanged configuration; `WS39_FINAL_HANDOFF.md` and this file are terminal. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-L-CONTROLLED-SINCE-VALIDATOR-REGRESSION`

## Source Lock

- XMage repo/branch: `moeendres-png/mage` / `foundry/ws39-commander-history-state-restore`
- XMage exact WS-39 head/tree: `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
- Commander Lab repo/branch: `moeendres-png/commander-playtest-lab` / `ws39/xmage-engine-remediation-requalification`
- Exact Tax-3 runtime head/tree: `c4b35c4c2a0017f3d3c57bc518a018c8049c456b` / `1ff6a5def7e2aa3751666002d56e585a6c937353`
- First exact Full-107 construction runtime head/tree: `e10ec2b0e6e9bd0068da73b93c512a9f52c1e672` / `e42f1514fdb6b1ba2de5d4ec596ba289f45793f2`
- Checkpoint-L construction runtime head/tree: `c8018dda81c7cdefaabd65a855924584b4211cd9` / `c922acadbddca96244b2b27fbb78cbaba1789b4d`
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
   - Census grants no runtime credit.

5. **First exact Full-107 native-construction runtime probe — COMPLETE / VERIFIED.**
   - Workflow `WS39 Full107 Native Construction Probe`, run `33775617820`, job `100716451124`: SUCCESS.
   - Exact runtime head `e10ec2b0e6e9bd0068da73b93c512a9f52c1e672`.
   - Artifact id `9901713320`, digest `sha256:5ccd849a7235d7007bb2c437c29ff9dbfd1888562d26becc0f4e85fdf330a106`.
   - Exact result: 15 `NATIVE_SETUP_PASS_NO_RUNTIME_CREDIT`; 7 `DEFERRED_TO_FRESH_NATURAL_EXECUTOR`; 85 `FAIL_CLOSED_UNSUPPORTED_NATIVE_DIMENSION`; 0 native construction failures.
   - `historical_pass_imported=false`, `runtime_credit_granted=false`.

6. **Checkpoint-L `zone_position + controlled_since_turn_began` probe — COMPLETE / VERIFIED, REGRESSION CLASSIFIED.**
   - Atomic implementation commit `c8018dda81c7cdefaabd65a855924584b4211cd9`, tree `c922acadbddca96244b2b27fbb78cbaba1789b4d`.
   - Workflow `WS39 Full107 Native Construction Probe`, run `33777054968`, job `100721273753`: SUCCESS.
   - Artifact `ws39-full107-construction-c8018dda81c7cdefaabd65a855924584b4211cd9`, id `9902427299`.
   - GitHub artifact digest and downloaded ZIP SHA256 both `7401f465c8740d1bfd378640b50144b4b642acb5d62fa6d7dad865576b2a4eeb`.
   - Artifact source locks: provider commit/tree `c8018dda81c7cdefaabd65a855924584b4211cd9` / `c922acadbddca96244b2b27fbb78cbaba1789b4d`; XMage commit/tree `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`.
   - `WS39_FULL107_CONSTRUCTION_PROBE.json` SHA256 `34d7c234e9de7f310f7f7d2622e418ca6a3c13c7ec598d0ce4674363f8a9b798`.
   - Exact result: 6 `NATIVE_SETUP_PASS_NO_RUNTIME_CREDIT`; 7 `DEFERRED_TO_FRESH_NATURAL_EXECUTOR`; 61 `FAIL_CLOSED_UNSUPPORTED_NATIVE_DIMENSION`; 33 `FAIL_CLOSED_NATIVE_CONSTRUCTION`.
   - All 33 construction failures share `NATIVE_VALIDATION_FAILED: battlefield-controlled-since-turn-began:<semantic-id>`.
   - Regression root cause is **qualification-overlay validator overconstraint**, not a new XMage Rules-Core defect: the readback compares `Permanent.wasControlledFromStartOfControllerTurn()` against `booleanValue(spec, "controlled_since_turn_began", false)` for every battlefield object, even when the frozen object omits that optional field. Example `PILOT_PRIORITY` has three Grizzly Bears without the field and one Mountain with explicit `true`; failure occurs first on `obj:p1-bears`. By contrast, all Replay-5 records whose battlefield objects explicitly carry `controlled_since_turn_began=true` pass native setup, proving the native `PermanentImpl.removeSummoningSickness()` load/readback path is functional for the explicit true state.
   - Therefore absent `controlled_since_turn_began` must mean **unconstrained by that dimension**, not frozen false. The validator must perform this readback only when `spec.has("controlled_since_turn_began")`.
   - This probe grants zero runtime qualification credit and imports no historical PASS.

## Current unsupported / blocked construction state after Checkpoint L

Fresh exact counts:

- 6 native loaded-state PASS, no runtime credit.
- 7 natural-start records intentionally delegated to fresh natural executors.
- 33 native construction failures caused by the now-classified optional-field validator defect.
- 61 records still fail closed on genuinely unsupported native setup dimensions.

Remaining unsupported dimension families include stack state / stack zone, combat and temporal combat state, hidden-information knowledge grants, zone-move events, elimination/nonpositive-life setup, commander-damage matrices, owner/controller split, counters, attachments, extra turns, revealed zone and additional temporal entry points. Counts must be recomputed from the next fresh probe after the validator correction; no historical census is promoted over fresh runtime evidence.

## Important Decisions

- Construction equality is necessary but not sufficient for successor runtime PASS.
- Provider-request echo without native validation receives no credit.
- Optional frozen-state fields constrain native readback only when the field is actually present; omission must not be silently converted into a false semantic obligation.
- Every eventual 107/107 PASS needs native construction plus transaction/postcondition evidence for its frozen procedure.
- No historical same-ID PASS may be imported.
- Unsupported production-reachable decisions fail closed; no first/random/default/AI/GUI/parent fallback.
- No AF07 or Architecture Freeze claim. No merge.

## Quality

- Security and core Python tests/mypy/compile have fresh green predecessor evidence.
- Repository-wide Ruff contains inherited qualification debt; WS-39-owned files must be explicitly clean under unchanged configuration before terminal closure.

## Exact Next Action

1. Correct `apply_ws39_state_surface_overlay.py` so `battlefield-controlled-since-turn-began` is natively read back **only when the frozen card spec contains `controlled_since_turn_began`**; do not default an omitted dimension to false.
2. Keep native state loading for explicit `true` through XMage `PermanentImpl.removeSummoningSickness()` and retain exact native readback through `Permanent.wasControlledFromStartOfControllerTurn()`.
3. Re-run the exact Full-107 construction workflow and persist the new counts before any next setup-family remediation.
4. Continue bounded setup groups until all 107 records are construction-ready or naturally delegated with exact executor evidence.
5. Materialize fresh behavior executors for the 50 ordered native-operation sets; execute all 107 frozen v1.0.2 records with zero historical PASS import.
6. Remediate genuine runtime failures fail-closed until 107/107 PASS and required AF/category summaries are exact.
7. Close WS-39-local quality, seal final evidence/checksums, write `WS39_FINAL_HANDOFF.md`, and terminally update this file.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: Tax-3 is complete 3/3 fresh PASS. Checkpoint L proves the first `zone_position + controlled_since_turn_began` attempt introduced a qualification-validator overconstraint; 6 loaded-state records currently pass, 7 natural-start records are delegated, 33 are blocked by that validator defect, and 61 remain unsupported. Full 107/107 fresh behavior runtime remains open.