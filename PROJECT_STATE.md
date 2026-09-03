# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed, uses XMage as Rules authority, and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when the exact WS-32 v1.0.2 XMage denominator is freshly runtime-qualified: mandatory Tax-3 = 3/3 PASS; total = 107/107 PASS; fail/unknown/not_run/mismatch = 0; historical PASS imported = 0; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; privacy/hidden-information PASS; RNG/replay PASS; unsupported production-reachable decision paths = 0; exact source locks/checksums/evidence exist; WS-39-modified quality surfaces are clean under unchanged configuration; `WS39_FINAL_HANDOFF.md` and this file are terminal. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-G`

## Source Lock

- XMage repo/branch: `moeendres-png/mage` / `foundry/ws39-commander-history-state-restore`
- XMage exact WS-39 head/tree: `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
- XMage retained base: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c` / tree `f0a028b265f9c008ea0aedc4cec6b8f14500b69f`
- Commander Lab repo/branch: `moeendres-png/commander-playtest-lab` / `ws39/xmage-engine-remediation-requalification`
- Latest runtime-evidenced Commander Lab head/tree: `a9a52e4c7ee7150bb2cfe747b75cef9b2a273a52` / `71d4ea3a1a2802da25139125186d0075bea657aa`
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
   - Python project install, source locks, legal Wastes-only Commander bootstrap, Maven runtime classpath and fail-safe Tax-3 diagnostics are all closed.
   - Exact-head WS-39 Rules-RNG instrumentation is implemented and bound into both the PR-CI and dedicated push runtime build.
   - The transform is exact-locked to XMage `7bde8127...`, carries the seven attributable WS-26 RandomUtil/shuffle transforms, fails closed on source-anchor drift, and emits a machine-readable transform report plus patch.
   - Dedicated push run `33769541156`, job `100695932914`: source locks PASS, native history test PASS, runtime overlays PASS, instrumented XMage build PASS, bridge build PASS, runtime classpath PASS.
   - Therefore prior blocker `XMAGE_RULES_RNG_TAPE_UNAVAILABLE` is CLOSED.

3. **Latest Tax-3 evidence — 1/3 fresh PASS, 2/3 fail closed after correct native construction/tax enumeration.**
   - Run: `33769541156`
   - Job: `100695932914`
   - Artifact: `ws39-engine-runtime-a9a52e4c7ee7150bb2cfe747b75cef9b2a273a52`
   - Artifact id: `9899195792`
   - Artifact digest: `sha256:6eca90ff64ec186b388aacbb59fb3fcdd7b12c90be29e23554fef6ed805a3a21`
   - `historical_pass_imported = false`.
   - Exact result SHA256: `fa11111624cbd3d0d6372191d2fe8cff1a7b4aef3f9ea494b70b76a1d50685f9`.
   - RNG transform report SHA256: `769789a6034d31288632e82cc90497ddebdea52ae6c71a4c421e6265125fe8f8`.
   - RNG patch SHA256: `9e3f913e3a57cdbda7717ec332eb3a0a96b56f56ad5133cbb0cc63adb2dff2f7`.

4. **Tax-3 semantic findings from the latest fresh runtime.**
   - `WS05-CMD-PARTNER-TAX`: **PASS / FRESH_WS39_RUNTIME_PASS**.
     - P1 Rograkh restored cast history = 2.
     - Native base mana = 0; native Commander-adjusted mana = `{4}` via `Card.commanderCost`.
     - P1 Kediss restored cast history = 0.
     - Kediss native adjusted cost equals native base cost `{1}{R}`.
   - `WS05-CMD-TAX-2`: native requested-state construction PASS and exact digest equality PASS; restored P1 Rograkh history = 2; native tax enumeration base 0 → adjusted `{4}` PASS; transaction then fails closed at exact payment-source evidence selection: `SEMANTIC_MATCH_NOT_UNIQUE:MANA_SOURCE:obj:tax-mountain-0:matches=0`.
   - `WS05-CMD-TAX-4`: same result and same payment-source evidence blocker.
   - Thus Commander-history restoration and Commander-tax calculation are positively runtime-verified for all mandatory scenarios. The remaining blocker is not a Magic Rules failure.

## Current Blocker — Qualification Semantic Source-ID Evidence

`run_tax3.py` requires each of the four contract-declared Mountain payment sources to be selected from the current XMage-offered `mana_payment` legal options by exact frozen WS-32 `semantic_id`.

The current WS-39 overlay populates `metadata.semantic_source_object_id` via:

`XmageDecisionOptionIdentity.visibleNativeToSemantic(game, actorView)`.

That method intentionally maps native XMage object IDs to **actor-visible Knowledge-Ledger object IDs / incarnation references**, not to frozen WS-32 scenario `semantic_id`s. The metadata field is therefore misnamed and cannot match `obj:tax-mountain-0` etc.

The correct frozen semantic mapping already exists natively in `XmageWs26Scenario.Applied.semanticObjectIds()`, created during the exact native state load. This mapping must be exposed only as qualification evidence metadata while preserving the ordinary actor-visible opaque option identity and all privacy behavior.

Classification: **qualification evidence-identity projection defect**, not legality, Commander-tax, history-restoration, hidden-information, or RNG defect.

## Important Decisions

- Do not weaken `run_tax3.py` to match Mountains by first occurrence, name-only ordering, UUID ordering, or random/default choice.
- Do not replace actor-visible option IDs with frozen semantic IDs in the normal protocol surface.
- Add the frozen `semantic_id` only as qualification-only evidence metadata sourced from the already-applied native scenario map.
- Rules RNG remains XMage-owned; no Python/harness RNG substitution.
- Tax-3 must reach 3/3 fresh PASS before full 107 runtime credit is unlocked.
- No AF07 or Architecture Freeze claim. No merge.

## 107-Requalification Preparation

- Frozen denominator families: player_count 4; pilot_boundary 17; pilot_boundary_negative 7; hidden_information 20; replay_rng 5; micro_rules 17; CARD_02 1; multiplayer_commander 36.
- Historical WS-36 remaining rows are `NOT_RUN_AFTER_STOP_CONDITION`, not setup/runtime PASS, and cannot be imported.
- Frozen native procedures reduce the later implementation surface to 63 reusable operation names across 47 recurring operation sets.
- Decision surface is 17 families, dominated by priority, target, choose_mode and mulligan.
- Existing v1.0.1 XMage executors/overlays remain implementation provenance only; every v1.0.2 row requires fresh native execution.
- Commander-outside-command-zone fixtures require preservation of native commander identity; the old v1.0.1 builder is insufficient for that family.

## Quality

- Security and core Python tests/mypy/compile remain green on the latest fully observed PR-CI predecessor.
- Repository-wide Ruff lint/format contains inherited historical qualification debt.
- WS-39-local formatting must be explicitly clean under unchanged configuration before terminal closure.

## Exact Next Action

1. Repair the WS-39 qualification-only ability metadata path so `semantic_source_object_id` comes from the exact applied scenario native-UUID→frozen-semantic-ID map, while actor-visible opaque identity remains separate and unchanged.
2. Re-run the dedicated exact push workflow and inspect Tax-2/Tax-4 transaction evidence.
3. Repeat bounded remediation until Tax-3 = 3/3 fresh PASS; checkpoint immediately.
4. Then implement/execute the exact fresh 107-record v1.0.2 requalification with native operation-family executors and zero historical PASS import.
5. Close WS-39-local quality, seal final evidence/checksums, write `WS39_FINAL_HANDOFF.md`, and terminally update this state.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: mandatory Tax-3 is 1/3 fresh PASS; the remaining two records are blocked only by qualification semantic payment-source ID projection. Fresh 107/107 has not yet been executed.
