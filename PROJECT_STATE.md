# COMMANDER SIMULATION FOUNDRY — WS-43 CURRENT PROJECT STATE

## Current Assignment
WS-43 — supersede immutable WS-41 v1.0.3 with a provider-neutral v1.0.4 contract repairing the WS-40-proven MICRO target referential-integrity defect and adding complete referential-integrity linting.

## Current Status
- `WS43_WORKSTREAM_TERMINAL = NO`
- `TASK_COMPLETE = NO`
- `Completion Status = READY_FOR_V1_0_4_CONTRACT_REPAIR_AND_FREEZE`
- `SUCCESSOR_CONTRACT_FROZEN = NO`
- `PROVIDER_RUNTIME_EXECUTED = FALSE`
- `PROVIDER_PASS_IMPORTED = FALSE`
- `AF07_GRANTED = FALSE`
- `ARCHITECTURE_FREEZE = NO`

## Immutable Predecessor
Consume WS-41 v1.0.3 exactly from:
- commit `24152acf36b5a560c23ccacfed3f31d3039537eb`
- tree `428bbe58b2ea7b869200521092a8768108029b47`
- namespace `qualification/ws41`
- schema `commander-lab.semantic-fixture-materialization/1.0.3`
- bundle digest `545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b`
- materialization SHA-256 `8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5`
- provider denominator `107`

The WS-41 terminal evidence head `de478cf084529067776866aefb04d5c92efafeea` is branch ancestry/tooling provenance only. v1.0.3 must not be edited in place.

## New Terminal Input — WS-40
WS-40 is COMPLETE as terminal adjudication, not provider qualification.

Terminal branch head/tree:
- `87b0a571cb3f9d18378150e3546fbe8fac4b6366`
- `9cefce77f1421a4f2f6b6ff4673fca377f030a40`

Atomic terminal evidence commit/tree:
- `fbb4b9c8534b11b8daf70a162fdb081d34ac2ab7`
- `0697ea0c6821f4590290823b86a1f62b52947379`

Classification:
`TERMINAL_IMMUTABLE_CONTRACT_DEFECT`

Exact first failure:
- attempt `26`
- workflow run `33935065462`
- job `101221261106`
- artifact `9959955219`
- artifact ZIP SHA-256 `32704c208c54455902091aec043a9bb6a5a49017694102661c893a993d3ca104`
- record index `56`
- fixture `MICRO_PRIORITY`
- error `WS40_STATE_TARGET_UNBOUND:obj:P2-bears`

`MICRO_PRIORITY` and `MICRO_STACK` request `obj:P2-bears`, which has no exact record-local semantic referent. Two distinct P2 Grizzly Bears exist (`obj:p2-bears`, `obj:micro-target`), while the frozen native procedure explicitly names `obj:micro-target`. Provider-side case folding/name/controller guessing is forbidden.

## Consequence for WS-42
WS-42 currently targets the now-defective v1.0.3 contract. No further v1.0.3 provider qualification can earn terminal successor credit. WS-42 should be stopped fail-closed after independently binding this upstream contract defect and preserving any implementation-only remediation as provenance. Do not discard useful XMage implementation work, but do not claim v1.0.3 qualification.

## Required Execution
Follow `candidate-qualification/ws43-successor-v1.0.4/WS43_WORKSTREAM_CONTRACT.md`.

Core sequence:
1. independently reproduce the WS-40 defect from immutable v1.0.3 bytes;
2. prove the intended MICRO referent provider-neutrally;
3. repair representation only if obligation-preserving;
4. add complete case-sensitive referential-integrity linting over all 135 records;
5. revalidate `135/135` semantic executability;
6. preserve exact family/AF mappings and expected denominator `107`;
7. recompute all dependent digests;
8. deterministic double materialization;
9. prove v1.0.3 byte immutability;
10. persist immutable v1.0.4 freeze plus complete evidence/handoff;
11. Draft PR only; no merge.

## Exact Next Action
Begin WS-43 from the live branch, verify all source locks, reproduce the two MICRO dangling target references, and continue automatically through every remediable contract/linter/materialization issue until a genuine immutable v1.0.4 freeze exists or a terminal obligation contradiction is proven.
