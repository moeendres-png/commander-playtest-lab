# COMMANDER SIMULATION FOUNDRY — WS-40 PROJECT STATE

## Current Assignment

Complete WS-40 Forge AF04 Rules-Core remediation successor requalification from the immutable WS-32 v1.0.2 denominator through:

`IMPLEMENT_NATIVE_FORGE_STATE_CONSTRUCTOR_OBSERVER -> CONSTRUCTION_EQUALITY_107/107 -> FRESH_NATIVE_RUNTIME_107/107 -> FINAL_EVIDENCE_FREEZE -> DRAFT_PRS -> WS40_FINAL_HANDOFF`

Do not work on XMage. Do not modify WS-32/WS-33/WS-37/WS-38 except to read immutable evidence/provenance. Do not execute the WS-37 Actual-Card 283-scenario corpus. Draft PRs only; no merges.

## Target State

WS-40 is COMPLETE only when all of the following are runtime/evidence verified at the final locks:

- final Forge remediation source frozen, build/tests/raw bypass/patch reproducibility PASS;
- native Forge construction equality: 107/107;
- no-request-echo audit: PASS;
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
- raw materialization SHA256: `0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261`
- Forge denominator: 107

### Current WS-40 Commander-Lab branch

- branch: `ws40/forge-core-remediation-requalification`
- branch head before this recovery checkpoint: `67070bcd174f3d68455987b6cd81c03b77f97fe0`
- branch tree before this recovery checkpoint: `eaacc342c0dbe3a98ba44de4f3ecffa126287660`
- implementation head validated by latest construction run: `42288dad011473ddbea5d150e4687ec2af1c3e75`
- implementation tree: `e256f1e1fd437be27e48095704c3b894cf7b3200`
- the checkpoint-only commits after `42288dad...` do not change executable qualification code and therefore do not invalidate that runtime evidence.
- no WS-40 Draft PR was found in Commander Lab at this recovery checkpoint.
- no WS-40 Draft PR was found in the Forge fork at this recovery checkpoint.

## Completed Work Packages

### WP-00 — Continuation recovery / persistent authority reconstruction

Status: **VERIFIED**

Fresh recovery on 2026-09-03 established the live branch heads, canonical checkpoint, latest WS-40 workflow and exact job log rather than relying on chat history. The latest construction workflow remains run `33742627946`; no later construction run exists at this checkpoint.

The prior PROJECT_STATE contained two evidence transcription errors for run `33742627946`. The authoritative job log proves the exact first-ten PASS order and the artifact identity recorded under WP-04B below. Those values supersede the prior transcription.

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

### WP-04A — Exact native priority-holder restoration

Status: **VERIFIED**

Prior failure `PILOT_CHOOSE_OBJECT` required active player P2 with priority P1, while the provider snapshot showed priority P2. Exact Forge source proves `PhaseHandler` exposes native public priority state through `setPriority(Player)` / `getPriorityPlayer()`.

Root cause: WS40 set requested native priority before stack/combat construction; later native construction could change it.

Fix at implementation commit `42288dad011473ddbea5d150e4687ec2af1c3e75`:

- run native `applyStack(game)`;
- run native `applyCombat(game)`;
- reassert final requested holder through `game.getPhaseHandler().setPriority(nativePlayer)`;
- only then emit the native snapshot.

Classification: **FORGE_PROVIDER_DEFECT — FIXED**.

Validation: construction run `33742627946` passes `PILOT_CHOOSE_OBJECT` and continues beyond it.

### WP-04B — Construction no-request-echo hardening

Status: **PARTIAL / VERIFIED THROUGH FIRST CURRENT FAILING RECORD**

Current workflow: `WS40 Native Construction 107`.

Latest run on implementation head `42288dad011473ddbea5d150e4687ec2af1c3e75`:

- run: `33742627946`
- job: `100607801377`
- immutable WS-32 verification: PASS
- exact repaired Forge lock verification: PASS
- Forge game build: PASS
- isolated WS40 provider compile: PASS
- sequential construction records 1-10: PASS:
  1. `PLAYER_COUNT_2P`
  2. `PLAYER_COUNT_3P`
  3. `PLAYER_COUNT_4P`
  4. `PLAYER_COUNT_5P`
  5. `PILOT_PRIORITY`
  6. `PILOT_TARGET`
  7. `PILOT_CHOOSE_OBJECT`
  8. `PILOT_TARGET_AMOUNT`
  9. `PILOT_MULLIGAN`
  10. `PILOT_CHOOSE_USE`
- first current failing record: `PILOT_CHOICE`.

Exact failure from the job log:

`AssertionError: native stack object missing obj:utopia`

The constructor created the requested Utopia Sprawl stack SpellAbility and the observer fail-closed because no matching native stack instance remained discoverable.

Fresh Forge source audit at the exact engine lock establishes:

- stack implementation is `forge.game.zone.MagicStack`;
- `addAndUnfreeze(sa)` calls `add(sa)` after moving an ordinary spell host to the native stack zone;
- ordinary spells are not copied by the activated-ability fresh-instance path;
- `getInstanceMatchingSpellAbilityID(sa)` compares `sa.getId()` against the native stack instance SpellAbility ID;
- `MagicStack.add` can reject a non-copied SpellAbility before `push(...)` when `hasLegalTargeting(sp)` is false.

Therefore the previous hypothesis that ordinary spell copying alone changed the ID is not supported. The current open investigation is whether `PILOT_CHOICE` is being rejected by native target validation or otherwise removed before snapshot.

Current classification: **OPEN — FORGE_PROVIDER_DEFECT vs FORGE_HEADLESS_API_DEFECT pending focused native target/stack proof**. It is not a Forge Rules defect on current evidence.

Failure evidence, corrected from the authoritative job log:

- artifact ID: `9888376535`
- artifact ZIP SHA256: `be42770259f33bdf86a604647ab8a8878dc9d03af16e3b73510109a5f23b6a0c`
- artifact size: `72339` bytes

## Important Decisions

1. Construction equality must be derived from native Forge objects/configuration and actor-safe provider state. Requested-state echo is forbidden.
2. Unsupported construction fields fail closed; they are not synthesized as Rules state in Python.
3. Generic Forge `GameState` combat restoration is not used for canonical multi-defender Commander combat because its helper is 1v1-only.
4. Rules legality stays exclusively in Forge Core. Commander-Lab Python may parse/bind/normalize state but must not calculate Magic legality.
5. Historical WS-25/WS-33 PASS credit is not imported into the 107 successor denominator.
6. `UNKNOWN`, `PARTIAL`, `NOT_RUN`, and `CODE_DERIVED` are never promoted to PASS.
7. Provider identity mappings may retain opaque semantic/native identity bindings; they may not manufacture Rules legality or echo requested state as constructed-state proof.
8. Source presence or constructor code presence does not earn construction/runtime credit; exact native equality and fresh runtime are mandatory.

## Relevant Evidence

- Forge stable native Core run: `33686520297` — PASS.
- WS40 provider smoke exact pin run: `33686910851` — PASS.
- WS40 contract audit run: `33685671398` — PASS, denominator 107.
- requested-digest reconstruction run: `33688583497` — PASS, 107/107.
- native construction run `33734935926` — PARTIAL, first six records PASS before priority-provider mismatch.
- native construction run `33742627946` — PARTIAL, priority fix VERIFIED; exact first ten records above PASS; first current mismatch `PILOT_CHOICE` stack observation.

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
- `PROJECT_STATE.md`

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
| absent-key canonicalization | VERIFIED PASS |
| native priority-holder restoration | VERIFIED by run `33742627946` |
| native construction equality | PARTIAL: 10/107 sequential records PASS before first current mismatch |
| fresh native runtime 107 | NOT_RUN |
| Forge patch reproducibility final gate | OPEN |
| final evidence freeze | OPEN |
| Draft PRs | OPEN |
| final handoff | OPEN |

## Known Errors / Open Defects

### OPEN-01 — native stack construction/observation for `PILOT_CHOICE`

`PILOT_CHOICE` fails because the observer cannot find the native `obj:utopia` SpellAbility stack instance after `game.getStack().addAndUnfreeze(sa)`.

Source audit rules out the earlier unsupported assumption that an ordinary spell is necessarily copied to a different SpellAbility ID by `MagicStack.add`. The next proof must determine whether native target validation rejects the constructed Aura spell or another native operation removes it before the snapshot.

Any repair must use Forge-native state/stack APIs and independent observation. Request echo is forbidden.

### OPEN-02 — complete construction denominator

After OPEN-01 is fixed, rerun from the start and proceed to the next first mismatch until 107/107 construction equality is proven.

### OPEN-03 — fresh native successor runtime

No successor runtime credit until construction equality is 107/107. Then implement/execute exact native procedures and external decisions for all 107 records.

### OPEN-04 — Forge tooling reproducibility cleanup

Historical duplicate `tools/ws40_apply_core_remediation.py` and canonical `.github/ws40/apply_ws40_core_patch.py` must be reconciled. If engine source identity changes, rerun full native Core acceptance and update the provider pin before final qualification.

### OPEN-05 — final evidence / Draft PRs / terminal handoff

Final evidence checksums, both required Draft PRs and `WS40_FINAL_HANDOFF.md` remain open and receive no completion credit yet.

## Exact Next Action

1. Read immutable `PILOT_CHOICE` state and current constructor serialization to verify its target/stack binding.
2. Inspect exact Forge `MagicStack.hasLegalTargeting`, `SpellAbilityStackInstance`, Aura spell target semantics and the native stack/card-zone state after `addAndUnfreeze`.
3. Implement the minimum source-proven provider-side native stack fix or fail-closed diagnostic if required; do not compute Magic legality externally.
4. Run the focused state-loader compile workflow.
5. Run full `WS40 Native Construction 107` again.
6. Persist the new first-failure or 107/107 PASS result here before proceeding.

## Completion Status

- `LAST_CONFIRMED_CHECKPOINT = WS40-WP00-RECOVERED-RUN-33742627946-FIRST-MISMATCH-PILOT_CHOICE-CORRECTED-EVIDENCE`
- `TASK_COMPLETE = NO`
- `WS40_STATUS = PARTIAL`
- `Completion Status = PARTIAL`
- `FORGE_SUCCESSOR_PROVIDER_QUALIFIED = NO`
- `ARCHITECTURE_FREEZE = NO`
