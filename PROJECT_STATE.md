# COMMANDER SIMULATION FOUNDRY — WS-40 CURRENT PROJECT STATE

## Current Status

- `WS40_WORKSTREAM_TERMINAL = NO`
- `TASK_COMPLETE = NO`
- `Completion Status = V1_0_3_CONSTRUCTION_REMEDIATION_IN_PROGRESS`
- `FORGE_SUCCESSOR_PROVIDER_QUALIFIED = NO`
- `ARCHITECTURE_FREEZE = NO`
- `HISTORICAL_V1_0_3_RUNTIME_CREDIT_IMPORTED = 0`

WS-41 is terminally complete and its immutable provider-neutral v1.0.3 source lock remains binding. WS-40 is executing fresh Forge successor qualification from record 1 with zero historical successor-runtime credit.

## Binding WS-41 v1.0.3 Source Lock

- commit: `24152acf36b5a560c23ccacfed3f31d3039537eb`
- tree: `428bbe58b2ea7b869200521092a8768108029b47`
- schema: `commander-lab.semantic-fixture-materialization/1.0.3`
- canonical bundle digest: `545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b`
- materialization SHA-256: `8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5`
- exact provider denominator: `107`
- independently recomputed requested-state digests: `107/107 PASS`
- historical runtime credit imported: `0`

## Current Forge Source Lock

- commit: `f83b77aa75e4f90852bef9243f3c5b32c37dc7e0`
- tree: `e2f124f30d55e43f838615a969af4e09e7009471`
- version: `2.0.15-SNAPSHOT`
- process boundary: separate GPL JVM

## Completed Identity Remediation Gates

The v1.0.3 target-identity corpus audit and exact-record adjudication established one permitted frozen lineage bridge for `PILOT_REPLACEMENT_EFFECT` and two unresolved MICRO target identifiers that must remain fail-closed unless separately proven.

The refined stack-observer identity adjudication is persistent at:

- report: `candidate-qualification/ws40-forge/WS40_V1_0_3_IDENTITY_NORMALIZATION_ADJUDICATION.json`
- report commit: `d9f3a9847c65d561cc03e7afd0435943ec4cc128`
- workflow run: `33928239753`
- job: `101201304912`
- artifact: `9957582538`
- ZIP SHA-256: `296c06279b975156a85996a5bc60c08570de2b536a9461266ef79983a8b1939c`

Adjudication result:

- stack target refs checked: `21`
- resolved/player refs: `19`
- projection breaks: `0`
- ambiguous refs: `0`
- duplicate lineage suffix groups: `0`
- unresolved refs retained fail-closed: `2`
- changed projection rows: `1`
- `safe_for_observer_stack_card_identity_projection = true`

The authorized observer rule is stack-card-target-only: preserve current semantic id unless the uniquely bound frozen `card_lineage_id` suffix itself begins with `obj:`. No requested-target dependency, case folding, card-name matching, owner/controller guessing, combat/attachment/global `semanticOf` changes, or unresolved-target inference is authorized.

## Construction Attempt #25

Persistent evidence:

- file: `candidate-qualification/ws40-forge/WS40_V1_0_3_CONSTRUCTION_ATTEMPT_25.json`
- evidence commit: `0648c6d2bfc3170b92a5a39a0de4f266891706dc`
- workflow head: `31a9924de95932a0756de7299375cc04df90e5f3`
- workflow tree: `1509497da25430431dba8cfe793954b75de60e83`
- run: `33928737307`
- job: `101202788507`
- artifact: `9957798178`
- artifact ZIP SHA-256: `4f4e181e94b64dc9286cbd82eed8b18e928de93cf308685a830984d51352bfe0`

Freshly verified in Attempt #25:

- immutable WS41 lock: PASS
- requested-state digests: `107/107 PASS`
- Forge source lock: PASS
- Forge build: PASS
- isolated provider compile: PASS
- lineage resolver patch: PASS
- adjudicated stack observer identity patch: PASS
- records 1–19: `19/19 PASS`
- `PILOT_CHOICE`: PASS
- `PILOT_REPLACEMENT_EFFECT`: PASS

Record 20 is `PILOT_DECLARE_ATTACKER` per the exact WS41 denominator. Construction stops fail-closed before requested/native equality with:

`CANONICAL_SETUP_UNSUPPORTED_PROVIDER:COMBAT_LEGAL_SURFACE_NATIVE_OBSERVATION_UNAVAILABLE:eligible_attackers`

Current classification:

`PROVIDER_NATIVE_COMBAT_LEGAL_SURFACE_OBSERVATION_GAP`

This is not a contract defect. It is not permission to compute attacker legality in Python or the pilot.

## Native Combat Legal-Surface Capability Audit

Persistent evidence:

- file: `candidate-qualification/ws40-forge/WS40_V1_0_3_NATIVE_COMBAT_LEGAL_SURFACE_AUDIT.json`
- Commander Lab audited base: `8b92849f8142e616fc738c944770a11c353439f8` / tree `29df2763726b28bebab70d1bab6735b2c0cc7a50`
- Forge audited source: `f83b77aa75e4f90852bef9243f3c5b32c37dc7e0` / tree `e2f124f30d55e43f838615a969af4e09e7009471`
- exact record: `PILOT_DECLARE_ATTACKER`
- requested-state digest: `836a2232c59d0594b34cd326b72c3870449604cf4271143b184136ccc679f896`

Source adjudication:

- `CombatUtil.getPossibleAttackers(Player)` is a Forge-native Rules-Core observer for the broad eligible-attacker card surface.
- It delegates to Forge `canAttack` legality, including creature status, tapped/phased state, summoning sickness/control history, timing/defender legality, goad and static cant-attack restrictions.
- Forge `validateAttackers(Combat)` remains the authority for complete declaration legality; the observer bridge does not replace it.
- Record 20 has one requested eligible attacker, `obj:p1-bears`, an untapped P1 Grizzly Bears with explicit continuous-control eligibility, and no attack-tax/must-attack complication.
- The Attempt-25 failure is therefore a technically remediable provider observation gap, not a Forge Rules defect and not a contract defect.
- No Forge-core source change is required for this exact construction gate.
- Authorized remediation: the GPL-side provider may emit `eligible_attackers` only from `CombatUtil` native observation and project the resulting native Card through the existing semantic binding. The Python normalizer may consume that raw native field but may not calculate attacker legality or use requested eligible-attacker values.

Status:

`NATIVE_COMBAT_ELIGIBLE_ATTACKER_AUDIT = PASS_REMEDIATION_AUTHORIZED`

Implementation/runtime verification is still pending at this checkpoint.

## Gate Matrix

| Gate | Status |
|---|---|
| WS41 immutable v1.0.3 lock | PASS |
| Provider denominator | PASS — 107 |
| Requested-state digests | PASS — 107/107 |
| Historical v1.0.3 runtime credit | PASS — 0 |
| Forge source/build | PASS |
| Isolated provider compile | PASS |
| Identity target audit/adjudication | PASS / COMPLETE |
| Native eligible-attacker source/callgraph audit | PASS / REMEDIATION AUTHORIZED |
| Construction records 1–19 | PASS |
| Construction record 20 `PILOT_DECLARE_ATTACKER` | FAIL CLOSED — observer implementation pending |
| Complete construction 107/107 | NOT_GRANTED |
| Fresh behavior runtime 0→107 | NOT_RUN |
| Forge successor provider qualified | NO |
| AF07 | OUT_OF_SCOPE |
| Architecture Freeze | NO |

`UNKNOWN`, `PARTIAL`, `NOT_RUN`, historical results and diagnostic results are not PASS.

## Exact Resume Sequence

1. Freshly verify this branch HEAD and the unchanged Forge source lock.
2. Implement the narrow GPL-side native `eligible_attackers` observer bridge using `CombatUtil.getPossibleAttackers(Player)`; do not compute legality in Python or pilot code.
3. Patch the construction normalizer to consume only the raw native `eligible_attackers` field and retain fail-closed handling for unsupported combat legal-surface dimensions.
4. Rerun exact v1.0.3 construction from record 1 with zero historical credit and persist the next attempt.
5. Continue record-by-record through all technically remediable provider-native blockers.
6. If records 56/57 later fail on unresolved `obj:P2-bears`, do not alias/guess; adjudicate against frozen predecessor/authority evidence.
7. Require exact `107/107` construction PASS before any fresh behavior-runtime credit.
8. Only after construction PASS execute the complete v1.0.3 behavior denominator from record 1, then final audits/evidence/PR metadata/handoff without merging.
