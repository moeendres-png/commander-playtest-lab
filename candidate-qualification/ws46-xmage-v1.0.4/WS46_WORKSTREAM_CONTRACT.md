# COMMANDER SIMULATION FOUNDRY

# WORKSTREAM CONTRACT — WS-46 XMAGE v1.0.4 SUCCESSOR PROVIDER QUALIFICATION

## Objective

Take the newest technically valid XMage implementation provenance preserved by WS-42/WS-39 and execute a complete fresh provider qualification against immutable WS-44 `commander-lab.semantic-fixture-materialization/1.0.4`, starting from zero historical successor-runtime credit. Revalidate all preserved implementation remediations against the new contract, then continue through complete native construction and behavior runtime until XMage qualifies or a genuinely terminal blocker is proven.

## Inputs

1. `candidate-qualification/ws46-xmage-v1.0.4/WS46_COORDINATOR_INPUT_WS44.md`.
2. WS-44 terminal handoff and exact immutable freeze.
3. WS-42 terminal handoff and implementation provenance.
4. XMage engine baseline `moeendres-png/mage@7bde812727817723616c575759f39bfc4cda4607` / tree `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`, unless fresh verification proves a later intentional in-scope remediation lock is authoritative.
5. Newest substantive WS-42 provider implementation checkpoint `0087dd4b7b11ed9c54249363bf5c751e3063befb` / tree `63039ba3ef9f3d25cc18761e324fae8a00eaf31e` as implementation provenance only.

## Authority

Provider-neutral semantic execution authority is exact WS-44 freeze:

- commit `12940248497a8795991cbbd2eedef72945528cfe`
- tree `cd83c973b269711106d08ab5be2d7672f05bcb7c`
- namespace `qualification/ws44`
- namespace tree `6579e119605b90248426a3121a47c487b2bb13cd`
- contract `commander-lab.semantic-fixture-materialization/1.0.4`
- bundle digest `77b911195525c2fe8aff37f6c9573e5772f358b25646d0be5919314ed5e23b54`
- materialization SHA-256 `9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35`
- exact provider denominator `107`.

Current MTG Comprehensive Rules / official Oracle and rulings authority outrank XMage behavior if a rules dispute appears.

## In Scope

- fresh verification of all source/build/contract identities;
- independent reconstruction of exact 107-record denominator and requested-state digests;
- v1.0.3 -> v1.0.4 provider-impact diff, including all 9 changed fixtures / 11 representation repairs;
- fresh validation/adaptation of native non-echo construction/readback;
- native Commander-history restore use where contract state requires it;
- native revealed-state semantics;
- hidden-information/opaque-identity security remediation;
- deterministic replay alias canonicalization;
- complete 107-record native construction from record 1;
- complete 107-record fresh behavior runtime after construction gate;
- AF04/AF05/AF06/AF08/AF09 fresh aggregation;
- CARD_02 fresh runtime qualification;
- hidden-information/adversarial leakage verification;
- deterministic Rules RNG/replay verification;
- XMage provider/native engine defects discovered during qualification and technically remediable within scope;
- persistent machine-readable checkpoints, CI evidence, checksums and final handoff.

## Out of Scope

- editing immutable WS-44 v1.0.4;
- Forge work;
- WS-37 Actual-Card 283 runtime;
- AF07;
- Architecture Freeze;
- importing historical provider PASS;
- merging Draft PRs without explicit authorization.

## Dependencies

Upstream contract dependency is satisfied by WS-44. XMage Commander-history restoration and later WS-42 provider/security remediations are implementation provenance only and must be freshly source-/runtime-validated against v1.0.4.

## Required Deliverables

At minimum persist:

1. exact source-lock verification;
2. v1.0.4 denominator manifest and per-record digest binding;
3. v1.0.3 -> v1.0.4 provider-impact reconciliation;
4. fresh validation of non-echo native construction/readback;
5. complete native construction results for all 107 records;
6. complete fresh behavior-runtime results for all 107 records;
7. AF04/05/06/08/09 aggregate evidence;
8. CARD_02 evidence;
9. hidden-information and hidden-identity adversarial evidence;
10. RNG/replay evidence;
11. unsupported-decision/fallback audit;
12. exact workflow run/job/artifact/checksum identities;
13. `WS46_FINAL_HANDOFF.md`.

## Hard Gates

No provider qualification unless all applicable mandatory gates PASS.

- exact WS-44 lock: PASS;
- exact provider denominator: 107;
- historical successor-runtime credit imported: 0;
- exact XMage engine/build lock verified;
- request-independent native construction/readback: PASS;
- requested state vs independently normalized constructed native state: exact equality for every admitted record;
- construction: 107/107 PASS;
- fresh behavior runtime: 107/107 PASS;
- AF04: expected 24/24, but reconstruct exact v1.0.4 membership before asserting count;
- AF05: expected 20/20, reconstruct exact membership;
- AF06: expected 17/17, reconstruct exact membership;
- AF08: expected 36/36, reconstruct exact membership;
- AF09: expected 5/5, reconstruct exact membership;
- CARD_02: PASS;
- hidden-information/opaque-identity adversarial gate: PASS;
- deterministic replay/RNG gate: PASS;
- unsupported production-reachable decision paths: 0;
- forbidden pilot/GUI/default/internal-AI fallback paths: 0.

Construction-only evidence is not behavior PASS. UNKNOWN/PARTIAL/NOT_RUN are not PASS.

## Evidence Requirements

For every material gate record exact repository/commit/tree/build identities, workflow run/job, artifacts and SHA-256. Persist intermediate checkpoints before continuing. Distinguish CODE_DERIVED from RUNTIME_VERIFIED. No requested semantic state may be copied back as purported constructed-state evidence.

## Rules-Core / Pilot Boundary

XMage Rules Core exclusively owns legality: legal actions, costs, mana, stack, priority, targets, combat, triggers, replacement/prevention, continuous effects/layers, SBAs, zones, copy/control, Commander, multiplayer and Rules RNG.

Pilot/controller code chooses only among legal options exposed by Rules Core.

Forbidden production fallbacks include first option, random option, default yes/no, internal engine AI, GUI default, silent skip and parent-class fallback. Unsupported production-reachable paths fail closed.

## Preserved Implementation Provenance Requiring Fresh Proof

### Native non-echo readback

Retain the WS-42 architecture only if fresh v1.0.4 evidence proves construction output originates from native state/readback rather than request echo.

### Native revealed-state semantics

`zone:revealed` must derive from native XMage reveal registry semantics (`GameState.getRevealed()` / `mage.game.Revealed`) rather than fabricated physical zones.

### Hidden physical identity

Opaque hidden-card physical handles must remain independent of card identity, deck fingerprint, seat, zone, occurrence, native card UUID and Rules RNG. Fresh AF05 adversarial proof is mandatory; historical `hidden_identity_security_credit=false` remains no credit.

### Replay alias canonicalization

Opaque observation identifiers may be canonicalized to stable deterministic encounter-order aliases for semantic replay comparison, but this must not expose hidden identity or alter Rules RNG.

### Commander-history restoration

Use native WS-39 restoration capability when canonical starting state requires Commander cast history. Do not synthesize historical casts/events.

## Stop Conditions

Do not stop at an intermediate technically remediable failure. Stop fail-closed only if a mandatory record proves a genuine non-remediable contract defect, authority contradiction, XMage Rules-Core defect requiring architecture outside WS-46, provider capability defect that cannot be safely repaired, hidden-information failure that cannot be closed, or deterministic replay failure that cannot be closed.

## Success Condition

Only after all hard gates pass:

`WS46 = COMPLETE / PASS_XMAGE_V1_0_4_SUCCESSOR_PROVIDER_QUALIFICATION`

`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = TRUE`

This grants no AF07 and no Architecture Freeze.

## Final Handoff

The terminal handoff must include Source Lock, Work Completed, New Findings, Changes, Tests / Evidence, PASS / FAIL / UNKNOWN, Remaining Blockers, Outputs, Dependencies Unblocked and Exact Next Action.
