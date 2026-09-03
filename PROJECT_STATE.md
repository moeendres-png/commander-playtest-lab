# COMMANDER SIMULATION FOUNDRY — WS-40 PROJECT STATE

## Current Assignment

Complete WS-40 Forge AF04 Rules-Core remediation successor requalification from the immutable WS-32 v1.0.2 denominator through:

`IMPLEMENT_NATIVE_FORGE_STATE_CONSTRUCTOR_OBSERVER -> CONSTRUCTION_EQUALITY_107/107 -> FRESH_NATIVE_RUNTIME_107/107 -> FINAL_EVIDENCE_FREEZE -> DRAFT_PRS -> WS40_FINAL_HANDOFF`

Do not work on XMage. Do not modify WS-32/WS-33/WS-38. Do not execute the WS-37 Actual-Card 283-scenario corpus. Draft PRs only; no merges.

## Target State

WS-40 is COMPLETE only when all of the following are runtime/evidence verified at the final locks:

- native Forge construction equality: 107/107;
- fresh native successor runtime: 107/107;
- AF04: 24/24;
- AF05: 20/20;
- AF06: 17/17;
- AF08: 36/36;
- AF09: 5/5;
- player-count: 4/4;
- CARD_02: PASS;
- final evidence freeze materialized and checksummed;
- Forge Draft PR exists;
- Commander-Lab Draft PR exists;
- `WS40_FINAL_HANDOFF.md` is terminal and self-contained;
- `FORGE_SUCCESSOR_PROVIDER_QUALIFIED` is set only if every mandatory successor gate passes.

## Source Locks

### Forge repaired engine

- repository: `moeendres-png/forge`
- branch: `foundry/ws40-af04-core-remediation`
- commit: `3f53c7c4e93c011e781680ae2a0c195dd71414c0`
- tree: `481d3ee3b4798b78b4f00a93cc8e2cb54d05391f`
- version: `2.0.15-SNAPSHOT`
- stable acceptance workflow run: `33686520297`
- native WS40 combat/amount-distribution matrix: 15/15 PASS

### Immutable WS-32 successor contract

- repository: `moeendres-png/commander-playtest-lab`
- commit: `038d0f38635eecee4e331c99af41f148de267a26`
- tree: `0d160128119f2bad30b220a17c43419b50b7edbe`
- schema: `commander-lab.semantic-fixture-materialization/1.0.2`
- canonical bundle digest: `ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23`
- Forge denominator: 107

### Current WS-40 Commander-Lab branch

- branch: `ws40/forge-core-remediation-requalification`
- last confirmed checkpoint head before this state file: `8ba2529ef51a88099ea6dc094551666fe2b4a4a3`
- tree: `318b5b5522d26376697fe7a67bd16327e8b9774e`

## Completed Work Packages

### WP-01 — Forge AF04 Core remediation

Status: **VERIFIED**

- Core-owned legal combat-damage and amount-distribution decision surfaces implemented.
- Core revalidation before mutation implemented.
- shared staged same-step combat assignment validation implemented.
- trample/deathtouch/first-strike/legacy isolation tests implemented.
- AI/GUI/raw bypass paths removed from qualified surface.
- 15/15 native test matrix PASS.
- isolated provider smoke PASS.

### WP-02 — Immutable WS-32 contract reconstruction

Status: **VERIFIED**

- exact 107 denominator reconstructed.
- exact WS-32 requested-state digest canonicalization verified.
- absent projection keys are omitted rather than encoded as JSON null.
- corrected construction-requirements audit run `33688583497`: SUCCESS.
- requested digest reproduction: 107/107 PASS.

### WP-03 — Native Forge successor state-loader/provider compilation

Status: **VERIFIED**

- qualification-only GPL-side `Ws40SuccessorState` constructor/observer path exists.
- isolated provider compiles without Forge AI/GUI dependencies.
- native `GameState` application made synchronous in the initialization hook.
- semantic card identity binding supports indistinguishable duplicate physical cards through provider identity mapping rather than Rules duplication.
- stack construction order, counter observation and natural Commander configuration binding fixes applied.

### WP-04 — Construction no-request-echo hardening

Status: **PARTIAL / VERIFIED THROUGH FIRST FAILING RECORD**

Current workflow: `WS40 Native Construction 107`.

Most recent run at checkpoint head `8ba2529e...`:

- run: `33734935926`
- job: `100583176323`
- result: FAILURE at exact construction equality gate.
- Build exact Forge game: PASS.
- isolated provider compilation: PASS.
- immutable WS-32 verification: PASS.
- construction records 1-6: PASS:
  - `PLAYER_COUNT_2P`
  - `PLAYER_COUNT_3P`
  - `PLAYER_COUNT_4P`
  - `PLAYER_COUNT_5P`
  - `PILOT_PRIORITY`
  - `PILOT_TARGET`
- first failing record: `PILOT_CHOOSE_OBJECT`.

The failure is a construction-state mismatch only:

- requested `temporal_state.priority_player = P1`;
- native observed `temporal_state.priority_player = P2`;
- all other shown requested/normalized fields for this record match.

Classification: **FORGE_HEADLESS_API_DEFECT or FORGE_PROVIDER_DEFECT pending exact source proof**. It is not currently a Rules defect and must not be patched by request echo.

Failure artifact:

- artifact ID: `9885383182`
- artifact ZIP SHA256: `701c4a6a4dbddf518b81bf756a402815b3ba5f8d613d05bd384f48055507e488`

## Important Decisions

1. Construction equality must be derived from native Forge objects/configuration and actor-safe provider state. Requested-state echo is forbidden.
2. Unsupported construction fields fail closed; they are not synthesized as Rules state in Python.
3. Generic Forge `GameState` combat restoration is not used for canonical multi-defender Commander combat because its helper is 1v1-only.
4. Rules legality stays exclusively in Forge Core. Commander-Lab Python may parse/bind/normalize state but must not calculate Magic legality.
5. Historical WS-33 PASS credit is not imported into the 107 successor denominator.
6. `UNKNOWN`, `PARTIAL`, `NOT_RUN`, and `CODE_DERIVED` are never promoted to PASS.

## Relevant Evidence

- Forge stable native Core run: `33686520297` — PASS.
- WS40 provider smoke exact pin run: `33686910851` — PASS.
- WS40 contract audit run: `33685671398` — PASS, denominator 107.
- requested-digest reconstruction run: `33688583497` — PASS, 107/107.
- native construction run `33734935926` — PARTIAL, first six records PASS, first mismatch at `PILOT_CHOOSE_OBJECT` priority holder.

## Changed Files on WS-40 Commander-Lab Branch

Material WS-40 files include:

- `.github/workflows/ws40-native-construction-107.yml`
- `.github/workflows/ws40-successor-state-loader-compile.yml`
- `.github/workflows/ws40-forge-provider-smoke.yml`
- `candidate-qualification/ws40-forge/run_native_construction_107.py`
- `candidate-qualification/ws40-forge/audit_native_construction_requirements.py`
- `candidate-qualification/ws40-forge/audit_successor_contract.py`
- `candidate-qualification/ws40-forge/WS40_CONSTRUCTION_COVERAGE_PLAN.json`
- `qualification/providers/forge/gpl/Ws40SuccessorState.java`
- `scripts/ws40_apply_successor_state_overlay.py`
- `scripts/ws40_fix_successor_state_java.py`
- `scripts/ws40_fix_construction_runner.py`
- `scripts/ws40_fix_construction_runner_natural_objects.py`
- `scripts/ws40_generate_forge_provider.py`

## Tests Already Executed

| Test / Gate | Status |
|---|---|
| Forge Core compile | VERIFIED PASS |
| existing relevant Forge tests | VERIFIED PASS |
| WS40 native Core matrix | VERIFIED 15/15 PASS |
| raw bypass audit | VERIFIED PASS |
| isolated provider smoke | VERIFIED PASS |
| WS-32 contract denominator audit | VERIFIED 107 records |
| requested digest reconstruction | VERIFIED 107/107 PASS |
| native construction equality | PARTIAL: 6/107 sequential records PASS before first mismatch |
| fresh native runtime 107 | NOT_RUN |
| final evidence freeze | OPEN |
| Draft PRs | OPEN |
| final handoff | OPEN |

## Known Errors / Open Defects

### OPEN-01 — exact native priority-holder restoration

`PILOT_CHOOSE_OBJECT` requires active player P2 with priority P1. Current native construction leaves priority with P2. Need locate a native Forge API or native procedure that establishes P1 priority without request echo or external legality emulation.

Required classification after source inspection:

- `FORGE_HEADLESS_API_DEFECT`, if Forge has no usable headless native setter/path;
- `FORGE_PROVIDER_DEFECT`, if a native Forge API exists and the provider is not using it correctly;
- never `FORGE_RULES_DEFECT` unless an exact native transaction contradicts current Magic authority.

### OPEN-02 — complete construction denominator

After OPEN-01 is fixed, rerun from the start and proceed to the next first mismatch until 107/107 construction equality is proven.

### OPEN-03 — fresh native successor runtime

No successor runtime credit until construction equality is 107/107. Then implement/execute exact native procedures and external decisions for all 107 records.

### OPEN-04 — Forge tooling reproducibility cleanup

Historical duplicate `tools/ws40_apply_core_remediation.py` and canonical `.github/ws40/apply_ws40_core_patch.py` must be reconciled. If engine source identity changes, rerun full native Core acceptance and update the provider pin before final qualification.

## Exact Next Action

1. Inspect exact Forge lock for native priority-holder ownership APIs/callgraph (`Game`, `PhaseHandler`, priority loop/controller callbacks).
2. Implement the minimum provider-side native priority restoration path in `Ws40SuccessorState` only if it uses Forge-native state/turn machinery and does not compute Magic legality.
3. Run the focused state-loader compile workflow.
4. Run full `WS40 Native Construction 107` again.
5. Persist the new first-failure or 107/107 PASS result here before proceeding.

## Completion Status

- `LAST_CONFIRMED_CHECKPOINT = WS40-WP04-RUN-33734935926-FIRST-MISMATCH-PILOT_CHOOSE_OBJECT`
- `TASK_COMPLETE = NO`
- `WS40_STATUS = PARTIAL`
- `FORGE_SUCCESSOR_PROVIDER_QUALIFIED = NO`
- `ARCHITECTURE_FREEZE = NO`
