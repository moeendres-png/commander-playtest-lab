# COMMANDER SIMULATION FOUNDRY
# WS-42 — XMAGE v1.0.3 SUCCESSOR PROVIDER QUALIFICATION

## WORKSTREAM CONTRACT

### Objective

Take the repaired XMage implementation state produced by WS-39 and perform a complete fresh successor-provider qualification against the immutable WS-41 `commander-lab.semantic-fixture-materialization/1.0.3` contract.

The goal is to determine, from zero historical successor-runtime credit, whether XMage can satisfy the exact frozen 107-record provider denominator and close the non-Actual-Card provider gates required before downstream Actual-Card execution.

### Inputs

#### Immutable successor contract

- repository: `moeendres-png/commander-playtest-lab`
- commit: `24152acf36b5a560c23ccacfed3f31d3039537eb`
- tree: `428bbe58b2ea7b869200521092a8768108029b47`
- namespace: `qualification/ws41`
- contract: `commander-lab.semantic-fixture-materialization/1.0.3`
- canonical bundle digest: `545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b`
- materialization SHA-256: `8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5`
- provider denominator: `107`

#### XMage engine baseline

- repository: `moeendres-png/mage`
- branch: `foundry/ws39-commander-history-state-restore`
- commit: `7bde812727817723616c575759f39bfc4cda4607`
- tree: `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`

#### Commander Lab baseline

- WS-42 branch: `ws42/xmage-v1.0.3-successor-qualification`
- derived from restored WS-39 terminal content head: `c1e30d18c3312c4a8c77d15572ac6f0d2b4c3f51`

WS-39 is historical provenance only. It is not reopened.

### Authority

Conflict order:

1. newest direct user instruction;
2. freshly verified repository/branch/commit state;
3. current official Magic Comprehensive Rules / official Oracle and rulings;
4. exact native XMage source/runtime behavior;
5. completed handoffs as provenance.

WS-41 v1.0.3 is the sole execution-authoritative successor materialization for this workstream.

### In Scope

- exact WS-41 source-lock verification;
- exact 107-record denominator reconstruction;
- v1.0.3 requested-state digest verification;
- adaptation of WS-39 provider/construction/runtime tooling to v1.0.3;
- complete native construction from record 1;
- provider-native remediation where required;
- XMage engine remediation only when a newly exposed genuine native capability/Rules defect requires it and the change preserves architecture;
- complete fresh behavior runtime after construction admission;
- AF04, AF05, AF06, AF08, AF09 and `CARD_02` fresh evidence;
- hidden-information safety;
- deterministic replay / Rules RNG;
- exact evidence sealing and terminal handoff.

### Out of Scope

- Forge work;
- modification of WS-41 or WS-32 contracts;
- WS-37 Actual-Card-283 runtime;
- AF07 grant;
- Architecture Freeze grant;
- importing historical provider PASS;
- pilot-side legality or semantic emulation.

### Dependencies

Binding upstream:

- WS-41 COMPLETE / `PASS_SUCCESSOR_CONTRACT_V1_0_3_FREEZE`.

Implementation provenance:

- WS-39 native Commander-history restoration and provider remediations.

Downstream:

- same-record Forge/XMage differential if both providers qualify;
- WS-37 Actual-Card runtime only after at least one provider qualifies.

### Required Deliverables

At minimum:

1. exact source-lock evidence;
2. exact 107-record denominator manifest;
3. requested-state digest verification;
4. complete construction results for all 107 records;
5. complete behavior-runtime results for all admitted records;
6. AF04/05/06/08/09 result matrix;
7. `CARD_02` result;
8. hidden-information evidence;
9. RNG/replay evidence;
10. provider/Rules/contract defect register;
11. run/job/artifact/checksum evidence;
12. Draft PR;
13. self-contained `WS42_FINAL_HANDOFF.md`.

### Hard Gates

- `UNKNOWN != PASS`
- `PARTIAL != FULL`
- `NOT_RUN != PASS`
- `CODE_DERIVED != RUNTIME_VERIFIED`
- historical PASS import = forbidden
- v1.0.2 provider PASS import = forbidden
- WS-34/36/39 provider PASS import = forbidden
- requested semantic state digest must match normalized constructed native state digest before behavior credit
- construction success is not behavior success
- no fake historical Rules events
- no reflection/private-state mutation unless it is part of a deliberately designed native XMage API and proven safe
- no pilot legality
- no silent fallback
- unsupported production-reachable discretionary paths fail closed
- hidden information must remain actor-entitled
- Rules randomness must remain deterministic/replayable under the qualified execution topology.

### Evidence Requirements

A record receives fresh v1.0.3 PASS only if:

1. the exact frozen WS-41 record and digest are identified;
2. native construction matches the requested semantic state;
3. the tested Rules/decision path is reached natively;
4. the external pilot supplies only discretionary choices from native legal options;
5. postconditions and semantic event/state evidence pass;
6. exact source/build identities are sealed.

### Stop Conditions

WS-42 stops only when either:

#### Success

- exact `107/107` fresh successor runtime PASS;
- AF04 `24/24` PASS;
- AF05 `20/20` PASS;
- AF06 `17/17` PASS;
- AF08 `36/36` PASS;
- AF09 `5/5` PASS;
- `CARD_02` PASS;
- `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = YES`.

or:

#### Genuine terminal blocker

A mandatory path is proven non-remediable within scope because of an exact:

- XMage Rules defect requiring a broader architecture change;
- XMage provider capability defect not safely repairable in scope;
- new immutable contract defect;
- current authority contradiction;
- hidden-information or deterministic replay failure that cannot be closed without violating the architecture contract.

Do not stop at an intermediate technically remediable failure.

## Execution Order

1. fresh exact source lock;
2. reconstruct 107 denominator;
3. verify all v1.0.3 digests;
4. update WS-39 tooling to v1.0.3;
5. full native construction 107;
6. remediate construction/provider gaps;
7. full behavior runtime;
8. remediate genuine provider/native Rules gaps;
9. aggregate AF04/05/06/08/09 + CARD_02;
10. seal evidence and handoff.

## Non-Grants

Even successful WS-42 grants:

- no AF07;
- no Architecture Freeze by itself;
- no Actual-Card runtime PASS.

**END WORKSTREAM CONTRACT**
