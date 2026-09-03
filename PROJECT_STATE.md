# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed, uses XMage as Rules authority, and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when the exact WS-32 v1.0.2 XMage denominator is freshly runtime-qualified: mandatory Tax-3 = 3/3 PASS; total = 107/107 PASS; fail/unknown/not_run/mismatch = 0; historical PASS imported = 0; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; privacy/hidden-information PASS; RNG/replay PASS; unsupported production-reachable decision paths = 0; exact source locks/checksums/evidence exist; WS-39-modified quality surfaces are clean under unchanged configuration; `WS39_FINAL_HANDOFF.md` and this file are terminal. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-H`

## Source Lock

- XMage repo/branch: `moeendres-png/mage` / `foundry/ws39-commander-history-state-restore`
- XMage exact WS-39 head/tree: `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
- XMage retained base: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c` / tree `f0a028b265f9c008ea0aedc4cec6b8f14500b69f`
- Commander Lab repo/branch: `moeendres-png/commander-playtest-lab` / `ws39/xmage-engine-remediation-requalification`
- Latest runtime-evidenced Commander Lab head/tree: `94fba8619a083809ee9ad16d5368b60e864e6738` / `ff5a4fdace638cfed7f22504188cda7e876143e1`
- Draft PR: `#153`
- WS32 contract: `commander-lab.semantic-fixture-materialization/1.0.2`
- WS32 freeze commit/tree: `038d0f38635eecee4e331c99af41f148de267a26` / `0d160128119f2bad30b220a17c43419b50b7edbe`
- Canonical materialization digest: `ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23`
- Materialization file SHA256: `0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261`
- Exact denominator: 107 unique records.

## Work Completed / Verified

1. **Native XMage Commander-history restoration — COMPLETE / VERIFIED.**
   - `CommanderPlaysCountState` + `CommanderPlaysCountWatcher.restoreStateForGameLoad(...)`.
   - Focused `CommanderPlaysCountStateRestoreTest` repeatedly PASS at exact WS-39 XMage head.
   - No synthetic historical cast events.

2. **Exact runtime infrastructure through Rules-RNG — COMPLETE / VERIFIED.**
   - Python project install, exact source locks, legal Wastes-only Commander bootstrap, Maven runtime classpath and fail-safe Tax-3 diagnostics are closed.
   - Exact-head qualification-only Rules-RNG instrumentation is bound into the build, exact-anchor checked and built successfully. Rules randomness remains XMage-owned.

3. **Frozen scenario semantic-source evidence projection — COMPLETE / VERIFIED through build.**
   - Commit `94fba8619a083809ee9ad16d5368b60e864e6738` separates normal actor-visible opaque Knowledge-Ledger identity from qualification-only frozen WS-32 `semantic_id` evidence.
   - `visible_source_object_id` remains actor-visible/opaque; `semantic_source_object_id` is derived only from the already-applied native scenario UUID→semantic-id map.
   - Dedicated run `33771684502`, job `100703214094`: exact locks PASS, native history test PASS, runtime overlays PASS, instrumented XMage build PASS, bridge build PASS, runtime classpath PASS.

4. **Latest Tax-3 runtime evidence — still 1/3 PASS, but the semantic-source blocker is CLOSED.**
   - Run: `33771684502`
   - Job: `100703214094`
   - Artifact: `ws39-engine-runtime-94fba8619a083809ee9ad16d5368b60e864e6738`
   - Artifact id: `9900088113`
   - Artifact digest: `sha256:25d4f7f5b848aee67f91b6d1082f7aa48d1dedef2f8b415e9e91c21e23e4d760`
   - `historical_pass_imported = false`.
   - `WS05-CMD-PARTNER-TAX`: fresh PASS.
   - `WS05-CMD-TAX-2` and `WS05-CMD-TAX-4`: exact native construction PASS, Commander-history restore PASS, native Rograkh base 0 → Commander-adjusted `{4}` PASS, and all four frozen Mountain sources are now semantically matchable/activatable. Both fail only after source activation with `ROGRAKH_POST_CAST_HISTORY_NOT_THREE`.

## Current Blocker — Native Mana Pool Commit Stage

The two cast Tax records now activate the exact four contract-declared Mountain mana abilities successfully. The runner then exits its payment helper immediately and checks Commander history. XMage has not yet completed the mana-cost transaction: with automatic mana disabled, the generated red mana remains in XMage's native mana pool and the provider exposes subsequent `mana_payment` decisions for committing that pool mana to the `{4}` cost.

The watcher correctly remains at historical count 2 until the cast transaction is actually committed. This is not a Commander-tax/history defect.

Correct bounded remediation:
- keep requiring the exact four contract-declared Mountain semantic source IDs and activate each exactly once;
- after those source activations, continue only through provider-offered `mana_payment` options of type `mana_pool` with native mana type red and positive availability;
- fail closed on any other payment-stage decision or ambiguous match;
- stop only when XMage leaves `mana_payment` and then require the native Commander watcher count to be 3 plus all four exact Mountains tapped.

No auto-payment, first/random/default selection or harness cost calculation is permitted.

## 107-Requalification Preparation

- Exact denominator families: player_count 4; pilot_boundary 17; pilot_boundary_negative 7; hidden_information 20; replay_rng 5; micro_rules 17; CARD_02 1; multiplayer_commander 36.
- Fresh exact WS-32 analysis yields 63 unique native operation names across 50 ordered operation sets for the 107 records.
- Historical WS-36 remaining rows are `NOT_RUN_AFTER_STOP_CONDITION`, not setup/runtime PASS, and cannot be imported.
- Existing true executor provenance: player-count/natural start, PILOT_MULLIGAN, PILOT_PRIORITY, PILOT_TARGET, WS05-CMD-MULL-2/4, HIDDEN_01/02, MICRO_STACK, MICRO_REPLACEMENT, WS05-MP-COMBAT-4, plus current Tax-3. All v1.0.2 credit must still be fresh.
- Special frozen setup dimensions requiring bounded native support include combat state, library positions, face-down state, owner/controller splits, counters, attachments, extra turns, elimination triggers, commander damage, zone-move events and commander identity outside the command zone.

## Quality

- Security and core Python tests/mypy/compile remain green on the latest fully observed PR-CI predecessor.
- Repository-wide Ruff lint/format contains inherited historical qualification debt.
- WS-39-local formatting must be explicitly clean under unchanged configuration before terminal closure.

## Exact Next Action

1. Extend `run_tax3.py` payment execution to finish XMage's explicit native mana-pool commit stage after activating the exact four frozen Mountain sources; accept only a unique provider-offered red `mana_pool` option at each such step.
2. Re-run dedicated exact Tax-3; require Tax-3 = 3/3 fresh PASS and checkpoint immediately.
3. Then materialize and execute the exact fresh 107-record v1.0.2 requalification, adding only XMage-native setup/transaction support required by frozen records and failing closed otherwise.
4. Close WS-39-local quality, seal final evidence/checksums, write `WS39_FINAL_HANDOFF.md`, and terminally update this state.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: mandatory Tax-3 is 1/3 fresh PASS; Tax-2/Tax-4 are blocked only by the remaining explicit native mana-pool commit stage. Fresh 107/107 has not yet been executed.
