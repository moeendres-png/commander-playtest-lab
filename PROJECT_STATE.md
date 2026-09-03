# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed, uses XMage as Rules authority, and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when the exact WS-32 v1.0.2 XMage denominator is freshly runtime-qualified: mandatory Tax-3 = 3/3 PASS; total = 107/107 PASS; fail/unknown/not_run/mismatch = 0; historical PASS imported = 0; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; privacy/hidden-information PASS; RNG/replay PASS; unsupported production-reachable decision paths = 0; exact source locks/checksums/evidence exist; WS-39-modified quality surfaces are clean under unchanged configuration; `WS39_FINAL_HANDOFF.md` and this file are terminal. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-I-TAX3-COMPLETE`

## Source Lock

- XMage repo/branch: `moeendres-png/mage` / `foundry/ws39-commander-history-state-restore`
- XMage exact WS-39 head/tree: `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
- XMage retained base: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c` / tree `f0a028b265f9c008ea0aedc4cec6b8f14500b69f`
- Commander Lab repo/branch: `moeendres-png/commander-playtest-lab` / `ws39/xmage-engine-remediation-requalification`
- Exact Tax-3 runtime head/tree: `c4b35c4c2a0017f3d3c57bc518a018c8049c456b` / `1ff6a5def7e2aa3751666002d56e585a6c937353`
- Draft PR: `#153`
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

2. **Exact runtime infrastructure through Rules-RNG — COMPLETE / VERIFIED.**
   - Exact source locks, legal Wastes-only Commander bootstrap, Python project installation, Maven runtime classpath, fail-safe diagnostics and exact-head qualification-only Rules-RNG instrumentation are closed.
   - Rules randomness remains XMage-owned; no harness RNG replacement.

3. **Qualification semantic source-ID evidence — COMPLETE / VERIFIED.**
   - Normal actor-visible Knowledge-Ledger IDs remain opaque and unchanged.
   - Frozen WS-32 `semantic_id` is exposed only as qualification-only metadata derived from the already-applied native scenario map.

4. **Mandatory Tax-3 — COMPLETE / 3-of-3 fresh PASS.**
   - Dedicated push workflow run: `33772428630`.
   - Exact runtime job: `100705752538`.
   - Workflow/job conclusion: SUCCESS.
   - Artifact: `ws39-engine-runtime-c4b35c4c2a0017f3d3c57bc518a018c8049c456b`.
   - Artifact id: `9900377069`.
   - Artifact digest: `sha256:5b76015f49bcbabd8482b9f978003d24057e1648fa2c755f1d2269d6ef733ad1`.
   - `WS39_TAX3_RESULTS.json` SHA256: `b3b89d32952402471a8800d80dfba8d5d9aa8f43db1db56d0926482c8b8d6a4b`.
   - Exit code: `0`.
   - `historical_pass_imported = false`.
   - `WS05-CMD-TAX-2`: FRESH_WS39_RUNTIME_PASS.
   - `WS05-CMD-TAX-4`: FRESH_WS39_RUNTIME_PASS.
   - `WS05-CMD-PARTNER-TAX`: FRESH_WS39_RUNTIME_PASS.
   - Tax-2 and Tax-4 each prove: requested/native state equality; restored P1 Rograkh history 2; native `Card.commanderCost` base 0 → adjusted `{4}`; four exact contract-declared Mountain mana abilities activated; four native red mana-pool commits; cast completes; watcher count becomes 3; all four exact Mountains are natively tapped.
   - Partner-Tax proves independent partner history and cost: Rograkh history 2 / adjusted `{4}`; Kediss history 0 / adjusted cost equals base `{1}{R}`.
   - RNG transform report SHA256: `769789a6034d31288632e82cc90497ddebdea52ae6c71a4c421e6265125fe8f8`.
   - RNG instrumentation patch SHA256: `9e3f913e3a57cdbda7717ec332eb3a0a96b56f56ad5133cbb0cc63adb2dff2f7`.
   - Native Commander-history surefire XML SHA256: `b788f557e3e9fc51d3c3f9916d4fe9f9d336e51d28096ac5be993d4cb7d9fed6`.

## Full-107 Gate — UNLOCKED

Mandatory Tax-3 is no longer a blocker. Fresh complete v1.0.2 successor requalification may now execute.

Exact frozen denominator families:
- player_count 4
- pilot_boundary 17
- pilot_boundary_negative 7
- hidden_information 20
- replay_rng 5
- micro_rules 17
- actual_card CARD_02 1
- multiplayer_commander 36
- total 107

Fresh exact WS-32 census work performed locally against the immutable freeze establishes:
- 63 unique native operation names;
- 50 unique ordered native-operation sets;
- historical results grant zero runtime credit.

Known reusable true-runtime provenance exists for natural start/player count, PILOT_MULLIGAN, PILOT_PRIORITY, PILOT_TARGET, WS05-CMD-MULL-2/4, HIDDEN_01/02, MICRO_STACK, MICRO_REPLACEMENT, WS05-MP-COMBAT-4, CARD_02 behavior attempt and Tax-3. Every v1.0.2 result must nevertheless be freshly re-executed.

Important construction rule: provider-emitted requested-state echo is not sufficient for full-107 credit. Each record needs native construction validation for every rules-relevant dimension it actually requests plus native transaction/postcondition evidence.

Special setup surfaces include combat state, stack state, zone order, face-down state, controlled-since-turn-began, owner/controller split, counters, attachments, extra-turn history, elimination trigger state, commander damage, commander zone-move state and commander identity outside the command zone.

## Quality

- Security and core Python tests/mypy/compile have fresh green evidence on predecessor heads.
- Repository-wide Ruff lint/format contains inherited historical qualification debt.
- WS-39-owned/modified files must be explicitly clean under unchanged configuration before terminal closure.

## Exact Next Action

1. Persist the exact 107-record census generator and machine-readable census, explicitly granting zero runtime credit.
2. Execute a fresh exact full-107 construction/executor coverage probe against the single WS-39 provider build; record every unsupported state/transaction family fail-closed rather than importing history.
3. Remediate missing native setup and transaction families in bounded reusable operation groups; rerun until fresh 107/107 PASS with fail/unknown/not_run/mismatch = 0.
4. Derive and verify AF04 24/24, AF05 20/20, AF06 17/17, AF08 36/36, AF09 5/5, CARD_02 PASS, hidden/privacy PASS, RNG/replay PASS and unsupported production decision paths = 0 from the fresh corpus.
5. Close WS-39-local quality, seal final evidence/checksums, write `WS39_FINAL_HANDOFF.md`, and terminally update this state.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: mandatory Tax-3 is COMPLETE 3/3 fresh PASS; fresh complete 107/107 successor requalification remains open.
