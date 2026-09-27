# COMMANDER SIMULATION FOUNDRY

# WORKSTREAM CONTRACT — WS-47 SUCCESSOR CONTRACT v1.0.5 REPAIR + IMMUTABLE FREEZE

## Objective

Supersede immutable WS-44 `commander-lab.semantic-fixture-materialization/1.0.4` with a new provider-neutral successor contract that repairs the WS-45-runtime-proven `WS05-MP-BLOCK-4` legal-blocker materialization defect without weakening its frozen multiplayer/defender-partition obligation, adds a regression/lint gate for the same defect class, revalidates the complete 135-record semantic materialization, preserves the exact provider denominator unless fresh semantic evidence requires otherwise, and freezes a new immutable source lock for fresh Forge/XMage qualification.

Target successor schema identity:

`commander-lab.semantic-fixture-materialization/1.0.5`

This is a NEW provider-neutral contract workstream. It does not reopen WS-44 and does not continue WS-45 provider remediation.

## Inputs

1. Immutable WS-44 freeze:
   - commit `12940248497a8795991cbbd2eedef72945528cfe`
   - tree `cd83c973b269711106d08ab5be2d7672f05bcb7c`
   - namespace `qualification/ws44`
   - namespace tree `6579e119605b90248426a3121a47c487b2bb13cd`
   - contract `commander-lab.semantic-fixture-materialization/1.0.4`
   - canonical bundle digest `77b911195525c2fe8aff37f6c9573e5772f358b25646d0be5919314ed5e23b54`
   - materialization SHA-256 `9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35`
   - exact provider denominator `107`.
2. WS-45 terminal provider-neutral defect proof:
   - terminal Commander-Lab handoff commit `9e43341f6f0e41bc1216f97e36b60bab895b0b67`
   - terminal runtime source `0038fa1974051a780243d01116706aafaeda57bd`
   - runtime `34222473068` / job `102048601313` / artifact `10054440299`
   - artifact SHA-256 `280f87b8aa01ae6400e32c1f19df2dbfe4af0aaddc871e3d5c191a645bed55e4`
   - terminal finding: exact Forge Rules-Core blocker legality for P2 is `obj:P2-bears` plus `obj:mp-p2-blocker`, while immutable WS44 requested `eligible_blockers` contains only `obj:mp-p2-blocker`.
3. Current official Magic Comprehensive Rules authority applicable to blocking and multiplayer combat.
4. Live WS-46 status only as cross-provider defect-discovery input. No WS-46 provider result is semantic authority. At WS47 start, WS-46 has no terminally proven additional v1.0.4 contract defect; its remaining 19 construction failures are unresolved provider/native-lifecycle surfaces and are not imported as contract changes.

## Authority

Source Truth follows project policy:

1. newest direct user instruction;
2. freshly verified repository/runtime state;
3. current canonical MTG rules / official Oracle and rulings;
4. immutable predecessor contract evidence;
5. historical reports only as provenance.

Provider behavior is never semantic authority by itself. A provider disagreement becomes contract evidence only after adjudication against current Magic authority and the frozen obligation.

WS-44 remains immutable. WS47 may only supersede it in a new namespace/version.

## In Scope

- exact predecessor lock and byte-integrity verification;
- exact reconstruction of WS44 135-record materialization and 107-record provider denominator;
- fresh authority adjudication of `WS05-MP-BLOCK-4`;
- repair of the provider-neutral requested semantic state for that fixture, including all directly dependent digests/lineage/manifest data;
- preservation of the frozen semantic obligation (`Defender/blocker partition`) unless current authority proves the obligation itself wrong;
- a blocker-surface semantic-executability lint/regression that rejects an `eligible_blockers` projection which omits an otherwise legal in-scope blocker represented by the same requested state;
- complete referential-integrity and semantic-executability validation for all 135 records;
- deterministic double materialization / byte equality;
- schema/version update to v1.0.5;
- exact v1.0.4 -> v1.0.5 supersession manifest;
- exact provider-denominator reconstruction;
- immutable digest/freeze evidence and self-contained final handoff;
- read-only consideration of WS46 findings solely to avoid freezing a successor while another already-proven provider-neutral WS44 defect is known.

## Out of Scope

- editing any file in immutable `qualification/ws44`;
- Forge implementation or runtime;
- XMage implementation or runtime;
- continuing WS45 or WS46 provider qualification;
- WS37 Actual-Card runtime;
- AF07;
- Architecture Freeze;
- importing provider PASS/FAIL as semantic truth without authority adjudication;
- changing unrelated obligations merely to make a provider pass;
- merging any Draft PR.

## Dependencies

- WS44 immutable freeze: satisfied.
- WS45 terminal authority contradiction: satisfied and binding input.
- Current official Rules authority: must be freshly verified before freeze.
- WS46 cross-check: must confirm no additional terminally proven provider-neutral WS44 defect exists at the freeze point; unresolved provider-capability failures do not block WS47 unless they become authority-adjudicated contract defects before freeze.

## Required Deliverables

At minimum persist:

1. `WS47_SOURCE_LOCK.json`;
2. exact predecessor namespace-integrity comparison;
3. WS45 defect import/adjudication with exact runtime/artifact identities;
4. current-rules authority evidence for blocker legality/multiplayer defender partition;
5. repaired v1.0.5 schema and 135-record materialization;
6. `SUPERSEDES_v1_0_4.json` with exact changed-record and obligation-change accounting;
7. complete 135-record referential-integrity report;
8. complete 135-record semantic-executability/lint report including blocker-surface regression;
9. exact provider denominator manifest;
10. deterministic regeneration A/B evidence;
11. materialization SHA-256 and canonical bundle digest;
12. immutable freeze/terminal-gate result;
13. evidence index and SHA-256 manifest;
14. `WS47_FINAL_HANDOFF.md`.

## Hard Gates

No v1.0.5 freeze unless every gate below is PASS.

### G47-01 — Predecessor identity

Exact WS44 source lock and complete `qualification/ws44` namespace integrity are verified against the immutable predecessor.

### G47-02 — No in-place predecessor mutation

`qualification/ws44` remains byte-identical. All successor artifacts live under a new WS47 namespace.

### G47-03 — Authority closure

The `WS05-MP-BLOCK-4` repair is justified against current official Magic rules, not provider preference.

### G47-04 — Obligation preservation

The frozen semantic obligation remains unchanged unless authority proves it wrong. Representation repair must not weaken defender/blocker partition semantics.

### G47-05 — Exact change accounting

Every requested-state/digest change from v1.0.4 to v1.0.5 is enumerated. Unrelated records must remain byte/semantic-equivalent after only the required version/digest envelope updates.

### G47-06 — Complete denominator

Materialization remains exactly `135` records. Provider denominator remains exactly `107` unless a documented authority-backed semantic reason requires a different count; silent denominator drift is forbidden.

### G47-07 — Referential integrity

All typed semantic references across all 135 records resolve exactly; defects `0`.

### G47-08 — Semantic executability

All 135 records pass semantic-executability validation; UNKNOWN/PARTIAL are not PASS.

### G47-09 — Blocker-surface completeness regression

A dedicated lint/regression must prove that the repaired `WS05-MP-BLOCK-4` requested state does not omit another legal blocker represented by the same state. The lint must be provider-neutral and authority-derived; it may not query Forge/XMage for legality.

### G47-10 — Decision/pilot boundary preservation

No successor change moves Magic legality into pilot/controller metadata or introduces option-position/default/random/AI/GUI fallbacks.

### G47-11 — Hidden information preservation

No change broadens actor-visible hidden information or encodes provider-private identities into the semantic contract.

### G47-12 — RNG/replay preservation

Replay/RNG obligations and deterministic-token semantics remain unchanged unless directly required by an authority-backed repair.

### G47-13 — Actual-card preservation

All Actual-Card records and prior authority-curated obligations remain unchanged except for unavoidable global version/digest envelope changes.

### G47-14 — Deterministic materialization

Independent A/B regeneration is byte-identical.

### G47-15 — Freeze integrity

The final checked-in v1.0.5 materialization, schema, supersession manifest, validation artifacts, hashes and namespace tree are sealed and independently reproducible.

## Evidence Requirements

- Distinguish `CODE_DERIVED`, `AUTHORITY_VERIFIED`, and `RUNTIME_VERIFIED`.
- Provider runtime may be cited only as defect-discovery provenance; current official rules decide semantic truth.
- Record exact repository commit/tree, source blob, workflow run/job/artifact and SHA-256 where applicable.
- No historical provider runtime credit is imported.
- `UNKNOWN` is not PASS; `PARTIAL` is not FULL; `NOT_RUN` is not PASS.
- Persist each material checkpoint before continuing so the workstream is resumable after interruption.

## Stop Conditions

Stop fail-closed only if:

- current official authority cannot resolve the blocker semantics;
- the required repair would change a frozen obligation in a way not justified by authority;
- an additional already-proven provider-neutral WS44 defect appears and cannot be incorporated coherently before freeze;
- deterministic materialization or predecessor-integrity cannot be established;
- complete 135-record semantic executability cannot be restored without weakening obligations.

Do not stop at an intermediate technically remediable validation failure.

## Success Condition

Only after all hard gates pass:

`WS47 = COMPLETE / PASS_SUCCESSOR_CONTRACT_V1_0_5_FREEZE`

`SUCCESSOR_CONTRACT_FROZEN = TRUE`

This grants no Forge PASS, no XMage PASS, no AF07 and no Architecture Freeze.

## Final Handoff

The terminal handoff must be self-contained and include:

- Source Lock
- Work Completed
- New Findings
- Changes
- Tests / Evidence
- PASS / FAIL / UNKNOWN
- Remaining Blockers
- Outputs
- Dependencies Unblocked
- Exact Next Action

If v1.0.5 freezes successfully, the exact next provider action is fresh Forge and XMage qualification against the new immutable lock with zero imported successor-runtime credit.