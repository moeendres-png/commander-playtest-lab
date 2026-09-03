# COMMANDER SIMULATION FOUNDRY — WS-40 PROJECT STATE

## Current Assignment

Complete WS-40 Forge AF04 Rules-Core remediation successor requalification from the immutable WS-32 v1.0.2 denominator through:

`IMPLEMENT_NATIVE_FORGE_STATE_CONSTRUCTOR_OBSERVER -> CONSTRUCTION_EQUALITY_107/107 -> FRESH_NATIVE_RUNTIME_107/107 -> FINAL_EVIDENCE_FREEZE -> DRAFT_PRS -> WS40_FINAL_HANDOFF`

Do not work on XMage. Do not modify WS-32/WS-33/WS-37/WS-38 except to read immutable evidence/provenance. Do not execute the WS-37 Actual-Card 283-scenario corpus. Draft PRs only; no merges.

WS-40 is currently **BLOCKED by a source-proven immutable successor CONTRACT_DEFECT in PILOT_CHOICE**. No Forge or provider change may bypass that defect without weakening Rules Correctness or violating requested-state construction equality / no-request-echo.

## Target State

WS-40 can be SUCCESS only when all of the following are runtime/evidence verified at final locks:

- final Forge remediation source frozen, build/tests/raw-bypass/patch-reproducibility PASS;
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

A source-proven immutable contract contradiction is a fail-closed stop condition. It does not convert missing mandatory PASS gates into success.

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
- materialization Git blob: `926e9f9769f91137b1e6d26f1d83ba42ce3b2719`
- Forge denominator: 107

### Current WS-40 Commander-Lab branch

- branch: `ws40/forge-core-remediation-requalification`
- recovery checkpoint commit: `c9ccf6a667b1cedfe4fa2846548a23dc4852666f`
- recovery checkpoint tree: `41cec9b326debbd5e64fc15dee47bedb8d68a8ca`
- contract-defect evidence commit immediately before this checkpoint: `91ab728225b20d4d83202eb9053f9b6d73833bad`
- evidence tree: `437f4c960f2004395ee09df85b63de2c01181c5f`
- implementation head validated by latest construction run: `42288dad011473ddbea5d150e4687ec2af1c3e75`
- implementation tree: `e256f1e1fd437be27e48095704c3b894cf7b3200`
- checkpoint/evidence commits after `42288dad...` do not modify the executable provider/constructor used by run `33742627946`.
- no WS-40 Draft PR was found in Commander Lab at the recovery checkpoint.
- no WS-40 Draft PR was found in the Forge fork at the recovery checkpoint.

## Completed Work Packages

### WP-00 — Continuation recovery / persistent authority reconstruction

Status: **VERIFIED**

Fresh recovery on 2026-09-03 established live branch heads, the canonical root checkpoint, the latest WS-40 construction workflow and the exact job log rather than relying on chat history. The latest construction workflow remains run `33742627946`; no later construction run existed at the recovery checkpoint.

The earlier PROJECT_STATE had two evidence transcription errors for run `33742627946`. The authoritative job log proved the exact first-ten PASS order and artifact identity recorded below; those corrected values are canonical.

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

Prior failure `PILOT_CHOOSE_OBJECT` required active player P2 with priority P1, while the provider snapshot showed priority P2. Exact Forge source proves `PhaseHandler` exposes native priority state through `setPriority(Player)` / `getPriorityPlayer()`.

Root cause: WS40 set requested native priority before stack/combat construction; later native construction could change it.

Fix at implementation commit `42288dad011473ddbea5d150e4687ec2af1c3e75`:

- run native `applyStack(game)`;
- run native `applyCombat(game)`;
- reassert final requested holder through `game.getPhaseHandler().setPriority(nativePlayer)`;
- only then emit the native snapshot.

Classification: **FORGE_PROVIDER_DEFECT — FIXED**.

Validation: construction run `33742627946` passes `PILOT_CHOOSE_OBJECT` and continues beyond it.

### WP-04B — Native construction equality / no-request-echo gate

Status: **BLOCKED — SOURCE-PROVEN CONTRACT_DEFECT AT RECORD 11**

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
- first failing record: `PILOT_CHOICE`.
- exact failure: `AssertionError: native stack object missing obj:utopia`
- artifact ID: `9888376535`
- artifact ZIP SHA256: `be42770259f33bdf86a604647ab8a8878dc9d03af16e3b73510109a5f23b6a0c`
- artifact size: `72339` bytes.

#### Source-proven root cause

The immutable v1.0.2 `PILOT_CHOICE` record requests:

- `obj:utopia` = `Utopia Sprawl` in zone `stack`;
- `stack_state.cast_complete = true`;
- `stack_state.costs_paid = true`;
- `stack_state.targets = []`;
- later native resolution procedure `details.attached_to = obj:forest`.

Exact record identity:

- materialization digest: `f255fb5e8aaa115c659442bd60d617a8ba5128b2df945e3b013c5c6c3a2f90ba`
- requested-state digest: `4c1c8ab42c351281cd9f0d34a770ea65eaff7ab8c909ad57b989671842456044`.

The frozen WS-32 builder sets completed stack rows from `stack_state.targets` and contains no `PILOT_CHOICE` target override. Its procedure ordering requires `NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE` before the later transaction. Therefore the later `attached_to` procedure datum cannot legally be used to mutate or reinterpret the requested initial stack target state.

Current official Wizards Aura semantics require choosing the object/player an Aura spell will enchant as that spell's target when it is cast. Authority checked 2026-09-03 at `https://magic.wizards.com/en/keyword-glossary`.

At the exact Forge pin:

- `forge-gui/res/cardsfolder/u/utopia_sprawl.txt` identifies Utopia Sprawl as `Enchantment Aura` with `K:Enchant:Forest`;
- blob: `b1a0b4e41d8dd732a566c8236b85fa7cacabad4f`;
- `forge-game/src/main/java/forge/game/zone/MagicStack.java` blob `af8a8ccc5e21755cfaca63b87dd96e2c9787a8ca` returns without `push(...)` for a non-copied SpellAbility when `hasLegalTargeting(sp)` is false.

This explains the native observation: Forge can move the card into the Stack zone during `addAndUnfreeze`, but rejects the targetless Aura SpellAbility before the native stack instance is pushed.

Classification: **CONTRACT_DEFECT**.

This is not a Forge Rules defect, Forge headless API defect, or Forge provider defect. The headless provider is fail-closing on a requested rules state that cannot exist under current Magic rules.

Machine-readable evidence:

- `candidate-qualification/ws40-forge/WS40_CONTRACT_DEFECT_PILOT_CHOICE.json`
- evidence commit: `91ab728225b20d4d83202eb9053f9b6d73833bad`.

#### Forbidden repairs

WS-40 MUST NOT:

- synthesize `obj:forest` as a hidden target in Python/provider logic;
- derive target legality outside Forge Core;
- add a native target and then conceal it from normalization to preserve the old digest;
- weaken Forge to allow a targetless Aura spell onto the stack;
- modify immutable WS-32 v1.0.2.

Any of those would violate Rules Correctness, the Rules-Core/pilot boundary, requested-state equality, no-request-echo, or the immutable source contract.

#### Credit effect

- `PILOT_CHOICE` construction credit: **NO_RUNTIME_CREDIT**
- complete construction equality: **BLOCKED, 10/107 sequential PASS before immutable contract contradiction**
- no-request-echo complete gate: **NOT_GRANTED**
- fresh runtime 107: **BLOCKED_BY_CONSTRUCTION_GATE**
- Forge successor qualification: **NO**

A rerun against unchanged v1.0.2 cannot convert this gate to PASS without violating one of the mandatory correctness contracts, so no rerun is justified until the successor contract is repaired and re-frozen.

## Important Decisions

1. Construction equality must be derived from native Forge objects/configuration and actor-safe provider state. Requested-state echo is forbidden.
2. Unsupported construction fields fail closed; they are not synthesized as Rules state in Python.
3. Generic Forge `GameState` combat restoration is not used for canonical multi-defender Commander combat because its helper is 1v1-only.
4. Rules legality stays exclusively in Forge Core. Commander-Lab Python may parse/bind/normalize state but must not calculate Magic legality.
5. Historical WS-25/WS-33 PASS credit is not imported into the 107 successor denominator.
6. `UNKNOWN`, `PARTIAL`, `NOT_RUN`, and `CODE_DERIVED` are never promoted to PASS.
7. Provider identity mappings may retain opaque semantic/native identity bindings; they may not manufacture Rules legality or echo requested state as constructed-state proof.
8. Source presence or constructor code presence does not earn construction/runtime credit; exact native equality and fresh runtime are mandatory.
9. A frozen requested-state contradiction with current canonical Rules Authority is classified `CONTRACT_DEFECT`; provider/engine code must not be altered to make the contradiction appear constructible.
10. `native_procedure` data executed after construction cannot be used as hidden input that changes the frozen requested construction state.

## Relevant Evidence

- Forge stable native Core run: `33686520297` — PASS.
- WS40 provider smoke exact pin run: `33686910851` — PASS.
- WS40 contract audit run: `33685671398` — PASS, denominator 107.
- requested-digest reconstruction run: `33688583497` — PASS, 107/107 digest reproduction.
- native construction run `33734935926` — PARTIAL, first six records PASS before priority-provider mismatch.
- native construction run `33742627946` — PARTIAL/BLOCKED, priority fix VERIFIED; first ten records PASS; first mismatch `PILOT_CHOICE`.
- `candidate-qualification/ws40-forge/WS40_CONTRACT_DEFECT_PILOT_CHOICE.json` — source-locked CONTRACT_DEFECT proof.
- current Wizards Aura authority checked 2026-09-03.
- exact Forge `Utopia Sprawl` and `MagicStack` sources checked at `3f53c7c...`.

## Changed Files on WS-40 Commander-Lab Branch

Material WS-40 files include:

- `.github/workflows/ws40-native-construction-107.yml`
- `.github/workflows/ws40-successor-state-loader-compile.yml`
- `.github/workflows/ws40-forge-provider-smoke.yml`
- `candidate-qualification/ws40-forge/run_native_construction_107.py`
- `candidate-qualification/ws40-forge/audit_native_construction_requirements.py`
- `candidate-qualification/ws40-forge/audit_successor_contract.py`
- `candidate-qualification/ws40-forge/WS40_CONSTRUCTION_COVERAGE_PLAN.json`
- `candidate-qualification/ws40-forge/WS40_CONTRACT_DEFECT_PILOT_CHOICE.json`
- `qualification/providers/forge/gpl/Ws40SuccessorState.java`
- `scripts/ws40_apply_successor_state_overlay.py`
- `scripts/ws40_fix_successor_state_java.py`
- `scripts/ws40_fix_construction_runner.py`
- `scripts/ws40_fix_construction_runner_natural_objects.py`
- `scripts/ws40_generate_forge_provider.py`
- `PROJECT_STATE.md`

## Tests / Gates

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
| `PILOT_CHOICE` authority/contract adjudication | VERIFIED `CONTRACT_DEFECT` |
| native construction equality | BLOCKED: 10/107 sequential PASS before immutable contract contradiction |
| complete no-request-echo gate | NOT_GRANTED |
| fresh native runtime 107 | BLOCKED_BY_CONSTRUCTION_GATE |
| Forge patch reproducibility final gate | OPEN / independently reachable, but cannot yield successor qualification while contract is blocked |
| final success evidence freeze | BLOCKED |
| Draft PRs | OPEN; not sufficient for qualification |
| final success handoff | BLOCKED |

## Known Errors / Blockers

### BLOCKER-01 — immutable `PILOT_CHOICE` targetless Aura state

Status: **PROVEN `CONTRACT_DEFECT`**.

The immutable v1.0.2 contract requires a completed Utopia Sprawl Aura spell on the stack with `targets: []`. Current canonical Magic Aura semantics require the Aura spell's enchanted object/player to be its target when cast. Forge correctly rejects the targetless spell before native stack push.

The exact proof is frozen in `candidate-qualification/ws40-forge/WS40_CONTRACT_DEFECT_PILOT_CHOICE.json`.

Required resolution owner: **successor-contract authority, outside WS-40 Forge remediation**.

Minimum semantic repair: issue a new immutable successor contract version whose `PILOT_CHOICE` requested `stack_state` includes the legal `obj:forest` target, or redesign the scenario to another rules-legal native initial state; regenerate requested-state/materialization/bundle digests and then requalify providers from zero against the new lock.

WS-40 must not modify WS-32 v1.0.2.

### BLOCKER-02 — complete construction denominator

Blocked by BLOCKER-01. No unchanged-v1.0.2 rerun is credited or useful.

### BLOCKER-03 — fresh native successor runtime

Blocked by the mandatory construction gate. No successor runtime credit is allowed before complete construction equality.

### OPEN-04 — Forge tooling reproducibility cleanup

Historical duplicate `tools/ws40_apply_core_remediation.py` and canonical `.github/ws40/apply_ws40_core_patch.py` still require final reconciliation if/when WS-40 resumes toward a successful successor qualification. This independent cleanup cannot cure BLOCKER-01.

### OPEN-05 — final evidence / Draft PRs / terminal success handoff

Success evidence checksums, both required Draft PRs and successful terminal `WS40_FINAL_HANDOFF.md` remain unearned while the immutable contract blocker exists.

## Stop Condition

A technically sound in-scope Forge/provider remediation for BLOCKER-01 does not exist: every apparent workaround changes the requested semantics, hides native state, computes legality outside Forge Core, weakens Forge rules, or mutates immutable WS-32.

Therefore WS-40 must fail closed at the successor construction gate until an authoritative successor-contract revision supersedes v1.0.2 for this qualification cycle.

## Exact Next Action

Outside WS-40, successor-contract authority must:

1. supersede v1.0.2 with a new immutable contract version;
2. repair `PILOT_CHOICE` to a rules-legal Aura stack state (minimum: `targets: ["obj:forest"]`) or redesign the scenario without changing its intended decision obligation;
3. regenerate and freeze all affected requested-state, materialization, bundle, ledger and checksum identities;
4. hand the new immutable source lock back to WS-40.

On receipt of that new lock, WS-40 resumes with a fresh denominator/contract audit, then reruns native construction from record 1. It must not import 107/107 credit from the blocked v1.0.2 run.

## Completion Status

- `LAST_CONFIRMED_CHECKPOINT = WS40-CONTRACT-DEFECT-PILOT-CHOICE-AURA-TARGET-PROVEN`
- `TASK_COMPLETE = NO`
- `WS40_STATUS = BLOCKED_CONTRACT_DEFECT`
- `Completion Status = BLOCKED`
- `FORGE_SUCCESSOR_PROVIDER_QUALIFIED = NO`
- `ARCHITECTURE_FREEZE = NO`
