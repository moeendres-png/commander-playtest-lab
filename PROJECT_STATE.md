# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed, uses XMage as Rules authority, and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when the exact WS-32 v1.0.2 XMage denominator is freshly runtime-qualified: mandatory Tax-3 = 3/3 PASS; total = 107/107 PASS; fail/unknown/not_run/mismatch = 0; historical PASS imported = 0; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; privacy/hidden-information PASS; RNG/replay PASS; unsupported production-reachable decision paths = 0; exact source locks/checksums/evidence exist; WS-39-modified quality surfaces are clean under unchanged configuration; `WS39_FINAL_HANDOFF.md` and this file are terminal. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-F`

## Source Lock

- XMage repo/branch: `moeendres-png/mage` / `foundry/ws39-commander-history-state-restore`
- XMage exact WS-39 head: `7bde812727817723616c575759f39bfc4cda4607`
- XMage exact tree: `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
- XMage retained base: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c` / tree `f0a028b265f9c008ea0aedc4cec6b8f14500b69f`
- Commander Lab repo/branch: `moeendres-png/commander-playtest-lab` / `ws39/xmage-engine-remediation-requalification`
- Latest runtime-evidenced Commander Lab head: `7e4a5c2f72817a4c2bd7d03d889dbeb89b3d1160`
- Latest runtime-evidenced Commander Lab tree: `fb502358391448ab44893c65f95f6447e8b367d8`
- Draft PR: `#153`
- WS32 contract: `commander-lab.semantic-fixture-materialization/1.0.2`
- WS32 freeze commit/tree: `038d0f38635eecee4e331c99af41f148de267a26` / `0d160128119f2bad30b220a17c43419b50b7edbe`
- Canonical materialization digest: `ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23`
- Materialization file SHA256: `0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261`
- Exact denominator: 107 unique records.

## Work Completed / Verified

1. **Native XMage Commander-history restoration is implemented and repeatedly runtime-verified.**
   - Native state object/API: `CommanderPlaysCountState` + `CommanderPlaysCountWatcher.restoreStateForGameLoad(...)`.
   - Focused `CommanderPlaysCountStateRestoreTest` is green at exact WS-39 XMage head.
   - No synthetic historical cast events are used.

2. **Commander Lab exact runtime prerequisites are closed.**
   - Python repository import path repaired.
   - Declared Commander Lab dependencies installed in exact CI (`pip install -e .`).
   - Qualification bridge runtime classpath materializes Maven runtime dependencies.
   - Tax-3 stdout/stderr/exit are persisted on failure.
   - Tax-3 result binds the actual checked-out provider commit/tree rather than PR merge-ref SHA.

3. **Qualification bootstrap deck is now separated from frozen semantic state.**
   - Commit `7e4a5c2f72817a4c2bd7d03d889dbeb89b3d1160` uses a legal inert `Wastes`-only bootstrap mainboard sized to `100 - commander_count`.
   - Frozen semantic objects are not placed into the import deck.
   - They remain materialized as real XMage cards by the qualification state-loader (`CardRepository` + `Game.loadCards`) and validated against the frozen requested state.
   - This closed both earlier bootstrap failures: undersized decks and Commander color-identity rejection.

4. **Latest exact build chain is fresh green up to Tax-3.**
   - CI run `33767708301`, exact job `100690078341`.
   - PASS: exact checkouts/source locks, dependency install, contract probe, native history test, all current WS-39 overlays, exact XMage build, bridge verify, runtime classpath materialization, evidence sealing/upload.
   - Security job `100690078356`: SUCCESS.
   - Quality job: Mypy/pytest/compile/secret scan/wheel green except inherited repository-wide Ruff lint/format debt.

5. **Latest Tax-3 artifact is complete and exact.**
   - Artifact name: `ws39-exact-engine-contract-7e4a5c2f72817a4c2bd7d03d889dbeb89b3d1160`
   - Artifact id: `9898574242`
   - Artifact digest: `sha256:c528f4ed34ae19ed258825e99d1ec48c7df631b4cbe5eb1e4d8a08625b37d49d`
   - Contains provider/XMage commit+tree, contract probe, overlay patch, focused surefire report, Tax-3 stdout/stderr/exit/results and SHA256SUMS.

## New Finding — Current Tax-3 Blocker

Mandatory Tax-3 remains **0/3 credited**, but all three records now pass deck import and fail at the next common pre-state-load infrastructure boundary:

`create_full_game failed: full_game_creation_failed: IllegalStateException: XMAGE_RULES_RNG_TAPE_UNAVAILABLE`

Affected exact records:
- `WS05-CMD-TAX-2` — digest `cdbc7107328befdd3189b70704e33f9aa6851b116b4bef0c345e470140bc5ebf`
- `WS05-CMD-TAX-4` — digest `9dab6dfef8e3c03b35a70196ec1f457697a1ddfd75f6d07de6e82f4cb833ed01`
- `WS05-CMD-PARTNER-TAX` — digest `95b16c730b203d945892fbed3cb23105627f6afa62156a50b625573dc2f55d4c`

`historical_pass_imported = false`.

### Root-cause classification

- `XmageWs26QualificationSession` calls `RandomUtil.setSeed(seed)` then `XmageWs26RulesRngTape.begin()` during `create_full_game`.
- `XmageWs26RulesRngTape.begin()` reflectively requires `RandomUtil.beginRulesRngTape()` and later `getRulesRngTape()`.
- Those methods come from the qualification-only WS-26 XMage RNG instrumentation transform.
- The current WS-39 exact workflow does **not** apply that transform before building exact WS-39 XMage.
- The historical transform is hard-locked to retained base commit `77d7646d...`, so it cannot simply be invoked against exact WS-39 XMage head `7bde8127...`.
- Exact WS-39 `RandomUtil.java` still matches the uninstrumented source shape, confirming the missing instrumentation rather than a semantic RNG disagreement.

Classification: **qualification instrumentation omission / pre-runtime infrastructure defect**. No Commander-tax, history-restoration, or Magic Rules defect is established by this failure.

## Important Decisions

- Rules RNG remains XMage-owned. The Python harness must never generate or substitute Rules randomness.
- The correct remediation is an exact-head WS-39 qualification-only source transform that instruments XMage `RandomUtil` and the previously identified `Collections.shuffle` call sites, with strict source-lock and anchor checks.
- No fallback RNG, first/random/default decision selection, synthetic history, or requested-state echo may receive runtime credit.
- Tax-3 must reach 3/3 fresh PASS before full 107 runtime credit is unlocked.
- No AF07 or Architecture Freeze claim may be made.
- No merge is authorized.

## 107-Requalification Preparation

- Frozen denominator families: player_count 4; pilot_boundary 17; pilot_boundary_negative 7; hidden_information 20; replay_rng 5; micro_rules 17; CARD_02 1; multiplayer_commander 36.
- Historical WS-36 stopped after the mandatory history blocker; its remaining rows cannot be imported as PASS.
- Frozen native procedures reduce the future implementation surface to 63 reusable operation names across 47 recurring operation sets.
- Decision surface is 17 families, dominated by priority, target, choose_mode and mulligan.
- Existing specialized v1.0.1 XMage executors/overlays (natural start, hidden HIDDEN_01/02, MICRO_STACK, MICRO_REPLACEMENT, WS05-MP-COMBAT-4) are implementation provenance only and must be freshly rebound/executed for v1.0.2.
- Commander-outside-command-zone fixtures require preservation of native commander identity; the old v1.0.1 builder is insufficient for that family.

## Quality

- WS-39-local Ruff lint previously had zero findings.
- Five WS-39 Python files were still Ruff-format dirty at the last complete local-slice audit; terminal closure must format/check all WS-39-modified Python files using the unchanged project Ruff configuration.
- Repository-wide historical qualification debt is not to be hidden by weakening configuration.

## Exact Next Action

1. Add `candidate-qualification/ws39-xmage-successor/apply_ws39_rng_instrumentation.py`, exact-locked to XMage head `7bde812727817723616c575759f39bfc4cda4607`, carrying forward the WS-26 RandomUtil recording and attributable-shuffle transforms with fail-closed anchors.
2. Apply it in the exact WS-39 CI overlay/build sequence before the XMage build; persist its transform report in WS-39 evidence.
3. Re-run exact Tax-3 and inspect the three fresh rows.
4. Repeat bounded remediation until Tax-3 = 3/3 fresh PASS; checkpoint immediately.
5. Then execute the exact fresh 107-record v1.0.2 successor requalification with native operation-family executors and no historical PASS import.
6. Close WS-39-local formatting, seal final evidence/checksums, write `WS39_FINAL_HANDOFF.md`, and terminally update this file.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: mandatory Tax-3 is 0/3 due the verified missing exact-head Rules-RNG instrumentation; fresh 107/107 has not yet been executed.
