# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed, uses XMage as Rules authority, and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when the exact WS-32 v1.0.2 XMage denominator is freshly runtime-qualified: mandatory Tax-3 = 3/3 PASS; total = 107/107 PASS; fail/unknown/not_run/mismatch = 0; historical PASS imported = 0; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; privacy/hidden-information PASS; RNG/replay PASS; unsupported production-reachable decision paths = 0; exact source locks/checksums/evidence exist; WS-39-modified quality surfaces are clean under unchanged configuration; `WS39_FINAL_HANDOFF.md` and this file are terminal. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-J-FULL107-CONSTRUCTION-WORKFLOW-MATERIALIZED`

## Source Lock

- XMage repo/branch: `moeendres-png/mage` / `foundry/ws39-commander-history-state-restore`
- XMage exact WS-39 head/tree: `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
- Commander Lab repo/branch: `moeendres-png/commander-playtest-lab` / `ws39/xmage-engine-remediation-requalification`
- Exact Tax-3 runtime head/tree: `c4b35c4c2a0017f3d3c57bc518a018c8049c456b` / `1ff6a5def7e2aa3751666002d56e585a6c937353`
- Full-107 census generator commit: `1aa3e5c5cc3808dd9400a61b32bf70614e0a8516`
- Census workflow binding commit: `c2ff6276bcc330831a00ebf3a7f74a7d84d86764`
- Full-107 construction probe commit: `2bd548d001138f082ab10f7eea707a9b6ceb5ef8`
- Dedicated full-107 construction workflow commit: `e10ec2b0e6e9bd0068da73b93c512a9f52c1e672`
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
   - Artifact `ws39-engine-runtime-c4b35c4c2a0017f3d3c57bc518a018c8049c456b`, id `9900377069`.
   - Artifact digest `sha256:5b76015f49bcbabd8482b9f978003d24057e1648fa2c755f1d2269d6ef733ad1`.
   - `WS39_TAX3_RESULTS.json` SHA256 `b3b89d32952402471a8800d80dfba8d5d9aa8f43db1db56d0926482c8b8d6a4b`.
   - Exit code 0; historical PASS imported = false.
   - Tax-2, Tax-4 and Partner-Tax all `FRESH_WS39_RUNTIME_PASS`.

4. **Full-107 immutable census — MATERIALIZED / ZERO RUNTIME CREDIT.**
   - Exact denominator 107.
   - 63 unique native operation names.
   - 50 unique ordered native-operation sets.
   - Census explicitly sets `historical_pass_imported=false` and `runtime_credit_granted=false`.
   - It is bound into the exact WS-39 contract-shape evidence workflow.

5. **Full-107 native-construction probe — MATERIALIZED / NOT YET CREDIT-BEARING.**
   - `run_full107_construction_probe.py` classifies every frozen record by required starting-state dimensions.
   - Records with unsupported current native dimensions are fail-closed without execution.
   - Candidate records are actually started against XMage and must pass provider-emitted native validation plus exact requested-state digest equality.
   - Every row and the top-level artifact explicitly use `runtime_credit=NONE`, `runtime_credit_granted=false`, `historical_pass_imported=false`.
   - A dedicated exact-source workflow `.github/workflows/ws39-full107-construction.yml` now builds the same locked XMage head with the same WS-39 overlays and executes this 107-record construction probe independently of the already frozen Tax-3 workflow.

## Current Full-107 Construction Model

Conservative pre-runtime analysis of the current loader yields:
- 7 records delegated to the fresh `NATURAL_GAME_START` executor path;
- approximately 15 `NATIVE_STATE_LOAD` records whose complete starting-state dimensions appear within the presently supported loader surface and therefore are eligible for a real native-construction attempt;
- approximately 85 records fail closed before runtime because they require at least one additional native snapshot dimension.

These counts are provisional until the dedicated construction workflow produces the machine-readable runtime artifact. No successor runtime PASS is granted by this classification.

Known additional snapshot families include exact zone/library position, controlled-since-turn-began, owner/controller split, counters, attachments, stack state, combat state, non-default temporal state, extra-turn creation, elimination trigger state, zone-move event state, commander damage matrix, commander identity outside command zone and explicit knowledge grants.

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

1. Execute the new exact `WS39 Full107 Native Construction Probe` workflow at current branch head and seal/download its artifact.
2. Persist the exact runtime construction counts and every unsupported-dimension family in this file.
3. Remediate missing starting-state dimensions in bounded XMage-native reusable groups, with native readback validation, rerunning the construction probe after each group until all 107 are construction-ready.
4. Materialize fresh behavior executors for the 50 ordered native-operation sets; execute all 107 frozen v1.0.2 records with zero historical PASS import.
5. Remediate genuine runtime failures fail-closed until 107/107 PASS and required AF/category summaries are all exact.
6. Close WS-39-local quality, seal final evidence/checksums, write `WS39_FINAL_HANDOFF.md`, and terminally update this file.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: Tax-3 is complete 3/3 fresh PASS; the complete fresh 107/107 successor runtime remains open. The dedicated full-107 construction workflow is materialized and is the current execution gate.
