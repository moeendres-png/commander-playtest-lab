# COMMANDER SIMULATION FOUNDRY

# WORKSTREAM WS-44 — PREDECESSOR AUTHORITY RECONCILIATION + v1.0.4 REFERENTIAL-INTEGRITY FREEZE

## Objective

Resolve the predecessor-integrity contradiction that terminalized WS-43, preserve exact WS-41 v1.0.3 semantic authority without rewriting it, then complete the provider-neutral v1.0.4 successor-contract repair and immutable freeze required by the WS-40/WS-42 MICRO target identity defect.

Target terminal success:

`WS44 = COMPLETE / PASS_SUCCESSOR_CONTRACT_V1_0_4_FREEZE`

`SUCCESSOR_CONTRACT_FROZEN = TRUE`

## Inputs

### Binding Coordinator Authority

`candidate-qualification/ws44-v1.0.4-authority/WS44_COORDINATOR_AUTHORITY_DECISION.md`

### Immutable WS-41 predecessor

- repository `moeendres-png/commander-playtest-lab`
- commit `24152acf36b5a560c23ccacfed3f31d3039537eb`
- tree `428bbe58b2ea7b869200521092a8768108029b47`
- namespace tree `af8a26e7e74a859d5f4a983b69e4ff108e7123f4`
- contract `commander-lab.semantic-fixture-materialization/1.0.3`
- canonical materialization bundle digest `545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b`
- materialization SHA-256 `8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5`
- provider denominator `107`

### WS-40 terminal provider-neutral defect evidence

- terminal head `87b0a571cb3f9d18378150e3546fbe8fac4b6366`
- atomic evidence `fbb4b9c8534b11b8daf70a162fdb081d34ac2ab7`
- classification `TERMINAL_IMMUTABLE_CONTRACT_DEFECT`
- first failure `WS40_STATE_TARGET_UNBOUND:obj:P2-bears`
- affected mandatory records `MICRO_PRIORITY`, `MICRO_STACK`

### WS-42 corroboration

- terminal commit `a455f596389fde2d61703a0e6918415db2fd18c2`
- tree `af62bcea93c5416289264492fbc066a1dbd5b2d0`
- classification `COMPLETE / BLOCKED_BY_IMMUTABLE_V1_0_3_CONTRACT_DEFECT`
- `XMAGE_RULES_CORE_FAILURE = FALSE`

### WS-43 terminal authority defect evidence

- terminal commit `a96f0db9a4d2cb8ef646281ab5bf0ee351d0a52e`
- tree `cafdbcd9e08bbd1da64a8ef4dcd50f1e63e44f2e`
- classification `COMPLETE / TERMINAL_FAIL_DIGEST_INTEGRITY_DEFECT`
- no v1.0.4 schema/materialization/freeze emitted

## Authority

Source Truth order remains:

1. newest direct user instruction;
2. freshly verified GitHub state;
3. current canonical MTG authority where rules meaning is involved;
4. persisted workstream evidence.

WS-44 does not retroactively alter WS-43. WS-43 remains terminal FAIL under its own gate definition.

WS-44 introduces a new predecessor-integrity definition from the Coordinator Authority Decision.

## In Scope

- exact detached retrieval and byte verification of predecessor commit `24152acf...`;
- proof that later WS-41 drift is limited to the five classified attestation/evidence files;
- proof that the 13-file immutable semantic/support payload remains byte-identical;
- independent reproduction of the MICRO dangling-reference defect;
- provider-neutral identity adjudication for `MICRO_PRIORITY` and `MICRO_STACK`;
- v1.0.4 representation repair only if obligations remain unchanged;
- complete typed, case-sensitive referential-integrity field inventory;
- complete referential-integrity linter across all 135 records;
- negative and positive regression tests;
- inherited WS-41 semantic lint preservation;
- complete 135/135 semantic executability revalidation;
- provider denominator reconstruction;
- digest lineage;
- deterministic double materialization;
- persistent immutable v1.0.4 Git freeze;
- independent regeneration/checked-in-byte validation;
- terminal evidence bundle and self-contained handoff.

## Out of Scope

- Forge provider runtime;
- XMage provider runtime;
- Forge or XMage engine implementation changes;
- WS-37 Actual-Card runtime;
- AF07 grant;
- Architecture Freeze;
- edits to immutable WS-41 v1.0.3;
- reopening WS-40, WS-41, WS-42 or WS-43.

## Dependencies

Upstream dependencies are complete enough for execution:

- WS-40 terminal defect proof: available;
- WS-42 independent corroboration: available;
- WS-43 predecessor-integrity failure proof: available;
- Coordinator authority reconciliation: persisted in WS-44.

Downstream remains blocked until successful v1.0.4 freeze:

- new Forge successor qualification;
- new XMage successor qualification;
- provider differential;
- Actual-Card runtime.

## Required Deliverables

At minimum:

1. `WS44_SOURCE_LOCK.json`
2. `WS44_PREDECESSOR_AUTHORITY_VERIFICATION.json`
3. `WS44_WS43_SCOPE_RECONCILIATION.json`
4. `WS44_WS40_MICRO_DEFECT_REPRODUCTION.json`
5. `WS44_MICRO_TARGET_IDENTITY_ADJUDICATION.json`
6. `WS44_REFERENCE_FIELD_INVENTORY.json`
7. `WS44_REFERENTIAL_INTEGRITY_LINTER_RULES.json`
8. linter implementation and regression tests
9. `WS44_REFERENTIAL_INTEGRITY_AUDIT_135.json`
10. `SEMANTIC_FIXTURE_SCHEMA_v1_0_4.json`
11. `SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_4.json`
12. `WS44_SEMANTIC_EXECUTABILITY_REPORT_135.json`
13. `WS44_PROVIDER_DENOMINATOR_107.json`
14. `WS44_DIGEST_LINEAGE.json`
15. `SUPERSEDES_v1_0_3.json`
16. `WS44_VALIDATION.json`
17. `WS44_EVIDENCE_INDEX.json`
18. `WS44_SHA256SUMS`
19. complete CI artifact
20. `WS44_FINAL_HANDOFF.md`

## Hard Gates

### G44-01 — Detached predecessor source authority

PASS only if exact predecessor commit/tree/namespace at `24152acf...` is retrieved and verified byte-exactly.

Do not compare the descendant working-tree namespace as if it were the predecessor source.

### G44-02 — Attestation drift classification

PASS only if comparison against later WS-41 terminal attestation proves:

- exactly the known five allowlisted attestation/evidence paths differ;
- the 13-file immutable semantic/support payload is byte-identical;
- no additional semantic payload drift exists;
- canonical materialization blob/SHA/digest are unchanged.

Any additional drift is FAIL.

### G44-03 — WS-40 defect reproduction

Reproduce `obj:P2-bears` dangling-reference defect directly from pinned predecessor bytes.

### G44-04 — MICRO_PRIORITY obligation preservation

Repair may change representation/requested-state digest but must not change frozen semantic obligation.

### G44-05 — MICRO_STACK obligation preservation

Same requirement.

### G44-06 — Exact target referential closure

Both repaired target references resolve exactly once using case-sensitive typed identity with no heuristic provider bridge.

### G44-07 — Global referential-integrity audit

All reference-bearing fields across all 135 records must be inventoried and validated.

Required result: `0 defects`.

### G44-08 — Inherited semantic lint

All WS-41 targeted-stack/cast-completion protections continue to PASS, including PILOT_CHOICE, CARD_13, CARD_22 semantics.

### G44-09 — Semantic executability

`135/135 PASS`.

### G44-10 — Corpus reconciliation

Record identities, family counts and AF mappings are reconciled.

### G44-11 — Provider denominator

Expected `107`; reconstruct independently.

### G44-12 — Digest lineage

Every changed requested-state/materialization/bundle identity is recomputed and lineage is internally consistent.

### G44-13 — Determinism

Complete builder executed twice from identical source lock with byte-identical outputs.

### G44-14 — No provider credit

- provider runtime executed `false`;
- provider PASS imported `false`;
- AF07 `false`;
- Architecture Freeze `false`.

### G44-15 — Persistent immutable freeze

A successful build is insufficient.

PASS only if v1.0.4 outputs are persisted in Git under a new canonical namespace, and a later independent CI run regenerates and byte-compares them successfully.

## Referential-Integrity Requirements

Semantic object IDs are exact and case-sensitive.

Every reference must resolve to exactly one valid target in its declared namespace/type.

Forbidden implicit resolution:

- case folding;
- card-name matching;
- owner/controller matching;
- first candidate;
- positional matching;
- provider-native identity guessing;
- request echo.

Any alias mechanism must be explicit, deterministic, one-to-one, scope-defined, schema-valid, included in canonical serialization and digest lineage, and cycle/ambiguity-free.

The exact WS-40 `obj:P2-bears` defect must become a permanent negative regression.

## MICRO Adjudication Requirement

The current working hypothesis is `obj:micro-target` because the native procedure names it, but this is not automatically authoritative.

Prove the intended referent provider-neutrally from record-local semantic relationships and provenance.

If obligation-preserving intended identity cannot be proven, fail closed as `AUTHORITY_UNRESOLVED` or `OBLIGATION_CONTRADICTION`.

Do not select an identity merely because Forge or XMage can execute it.

## Determinism / Freeze Rules

All v1.0.4 generation must consume predecessor bytes from the exact pinned commit, not the descendant working-tree WS-41 copy.

Do not edit `qualification/ws41`.

Create a new namespace, expected `qualification/ws44` unless implementation establishes an equally explicit canonical location.

Version remains `commander-lab.semantic-fixture-materialization/1.0.4` because WS-43 emitted no v1.0.4 successor artifact.

## Evidence Requirements

Every PASS claim must be backed by exact source locks, machine-readable outputs, workflow run/job IDs, artifact IDs and cryptographic checksums where applicable.

UNKNOWN, PARTIAL and NOT_RUN are not PASS.

## Stop Conditions

Stop fail-closed only if:

- detached predecessor bytes cannot be retrieved/verified;
- drift exceeds the explicit five-file attestation allowlist;
- intended MICRO identity cannot be proven without changing obligation;
- global referential integrity cannot be closed without semantic weakening;
- deterministic materialization fails;
- persistent freeze cannot be reproduced.

Do not stop at technically remediable implementation/linter/materializer failures.

## Success Effect

If all gates PASS:

`WS44 = COMPLETE / PASS_SUCCESSOR_CONTRACT_V1_0_4_FREEZE`

`SUCCESSOR_CONTRACT_FROZEN = TRUE`

This unblocks new Forge and XMage successor-provider workstreams from zero historical successor-runtime credit.

It grants no provider PASS, AF07 or Architecture Freeze.
