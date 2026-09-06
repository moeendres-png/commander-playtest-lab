# COMMANDER SIMULATION FOUNDRY

# WORKSTREAM CONTRACT — WS-45 FORGE v1.0.4 SUCCESSOR PROVIDER QUALIFICATION

## Objective

Take the repaired Forge Rules-Core/provider implementation preserved by WS-40 and execute a complete fresh provider qualification against immutable WS-44 `commander-lab.semantic-fixture-materialization/1.0.4`, starting from zero historical successor-runtime credit. Close the independent no-request-echo defect before granting construction credit, then continue through complete native construction and behavior runtime until Forge qualifies or a genuinely terminal blocker is proven.

## Inputs

1. `candidate-qualification/ws45-forge-v1.0.4/WS45_COORDINATOR_INPUT_WS44.md`.
2. WS-44 terminal handoff and exact immutable freeze.
3. WS-40 terminal handoff and provider/engine implementation provenance.
4. Forge engine baseline `moeendres-png/forge@f83b77aa75e4f90852bef9243f3c5b32c37dc7e0` / tree `e2f124f30d55e43f838615a969af4e09e7009471` unless fresh live verification proves a later intentionally equivalent in-scope remediation lock is authoritative.

## Authority

Source Truth order follows project policy. The provider-neutral semantic execution authority is exact WS-44 freeze:

- commit `12940248497a8795991cbbd2eedef72945528cfe`
- tree `cd83c973b269711106d08ab5be2d7672f05bcb7c`
- namespace `qualification/ws44`
- namespace tree `6579e119605b90248426a3121a47c487b2bb13cd`
- contract `commander-lab.semantic-fixture-materialization/1.0.4`
- bundle digest `77b911195525c2fe8aff37f6c9573e5772f358b25646d0be5919314ed5e23b54`
- materialization SHA-256 `9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35`
- exact provider denominator `107`.

Current MTG Comprehensive Rules / Oracle authority outranks Forge behavior if a rules dispute appears.

## In Scope

- fresh verification of all source/build/contract identities;
- independent reconstruction of the exact 107-record denominator and requested-state digests;
- v1.0.3 -> v1.0.4 provider-impact diff, especially all 9 changed fixtures / 11 representation repairs;
- strict no-request-echo remediation and proof;
- Forge-native state construction/readback;
- complete 107-record construction from record 1;
- complete 107-record fresh behavior runtime after construction gate;
- AF04/AF05/AF06/AF08/AF09 fresh aggregation;
- CARD_02 fresh runtime qualification;
- hidden-information verification;
- deterministic Rules RNG/replay verification;
- Forge/provider defects discovered during qualification and technically remediable within scope;
- GPL Forge changes only on the isolated Forge side where Rules-Core remediation is required;
- persistent machine-readable checkpoints, CI evidence, checksums and final handoff.

## Out of Scope

- editing immutable WS-44 v1.0.4;
- XMage work;
- WS-37 Actual-Card 283 runtime;
- AF07;
- Architecture Freeze;
- importing historical provider PASS;
- merging Draft PRs without explicit authorization.

## Dependencies

Upstream contract dependency is satisfied by WS-44. Forge engine remediation is reusable implementation provenance at the exact locked tree, subject to fresh verification. Full provider qualification depends on closing strict no-request-echo.

## Required Deliverables

At minimum persist:

1. exact source-lock verification;
2. v1.0.4 denominator manifest and per-record digest binding;
3. v1.0.3 -> v1.0.4 provider-impact reconciliation;
4. no-request-echo design/remediation evidence;
5. no-request-echo adversarial tests proving Rules-state-bearing fields are independently observed rather than copied from request materialization;
6. complete native construction results for all 107 records;
7. complete fresh behavior-runtime results for all 107 records;
8. AF04/05/06/08/09 aggregate evidence;
9. CARD_02 evidence;
10. hidden-information evidence;
11. RNG/replay evidence;
12. unsupported-decision/fallback audit;
13. exact workflow run/job/artifact/checksum identities;
14. `WS45_FINAL_HANDOFF.md`.

## Hard Gates

No provider qualification unless all applicable mandatory gates PASS.

- exact WS-44 lock: PASS;
- exact provider denominator: 107;
- historical successor-runtime credit imported: 0;
- Forge source/build lock verified;
- strict no-request-echo: PASS;
- requested state vs independently normalized constructed native state: exact equality for every admitted record;
- construction: 107/107 PASS;
- fresh behavior runtime: 107/107 PASS;
- AF04: expected 24/24, but reconstruct exact v1.0.4 membership before asserting count;
- AF05: expected 20/20, reconstruct exact membership;
- AF06: expected 17/17, reconstruct exact membership;
- AF08: expected 36/36, reconstruct exact membership;
- AF09: expected 5/5, reconstruct exact membership;
- CARD_02: PASS;
- unsupported production-reachable decision paths: 0;
- forbidden pilot/GUI/AI/default fallback paths: 0;
- hidden-information leakage gate: PASS;
- deterministic replay/RNG gate: PASS.

Construction-only evidence is not behavior PASS. UNKNOWN/PARTIAL/NOT_RUN are not PASS.

## Evidence Requirements

For every material gate record exact repository/commit/tree/build identities, workflow run/job, artifacts and SHA-256. Persist intermediate checkpoints before continuing. Distinguish CODE_DERIVED from RUNTIME_VERIFIED. No requested semantic state may be copied back as purported constructed-state evidence.

## Rules-Core / Pilot Boundary

Forge Rules Core exclusively owns legality: legal actions, costs, mana, stack, priority, targets, combat, triggers, replacement/prevention, continuous effects/layers, SBAs, zones, copy/control, Commander, multiplayer and Rules RNG.

Pilot/controller code chooses only among legal options exposed by Rules Core.

Forbidden production fallbacks include first option, random option, default yes/no, internal Forge AI legality fallback, GUI default, silent skip and parent-class fallback. Unsupported production-reachable paths fail closed.

## No-Request-Echo Requirement

The WS-40 defect is binding provenance. At minimum independently observe/derive from Forge/native execution rather than request payload:

- `knowledge_state`;
- `rules_randomness`;
- `extra_turn_creation`;
- `elimination_trigger`;
- `zone_move_event`;

and any additional Rules-state-bearing field discovered by complete audit.

Transport hashing, canonical serialization, or comparing a request-derived normalized object to itself does not satisfy this gate.

## Stop Conditions

Do not stop at an intermediate technically remediable failure. Stop fail-closed only if a mandatory record proves a genuine non-remediable contract defect, authority contradiction, Forge Rules-Core defect requiring architecture outside WS-45, provider capability defect that cannot be safely repaired, hidden-information failure that cannot be closed, or deterministic replay failure that cannot be closed.

## Success Condition

Only after all hard gates pass:

`WS45 = COMPLETE / PASS_FORGE_V1_0_4_SUCCESSOR_PROVIDER_QUALIFICATION`

`FORGE_SUCCESSOR_PROVIDER_QUALIFIED = TRUE`

This grants no AF07 and no Architecture Freeze.

## Final Handoff

The terminal handoff must include Source Lock, Work Completed, New Findings, Changes, Tests / Evidence, PASS / FAIL / UNKNOWN, Remaining Blockers, Outputs, Dependencies Unblocked and Exact Next Action.
