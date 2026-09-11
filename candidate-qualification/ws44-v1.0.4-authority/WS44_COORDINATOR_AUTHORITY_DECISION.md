# WS-44 COORDINATOR AUTHORITY DECISION — WS-41 PREDECESSOR IMMUTABILITY SCOPE

## Decision

The Coordinator selects **Option 2**, with a strict detached-source interpretation.

The immutable v1.0.3 predecessor authority remains exactly:

- repository: `moeendres-png/commander-playtest-lab`
- commit: `24152acf36b5a560c23ccacfed3f31d3039537eb`
- tree: `428bbe58b2ea7b869200521092a8768108029b47`
- namespace at that commit: `qualification/ws41`
- namespace tree: `af8a26e7e74a859d5f4a983b69e4ff108e7123f4`
- contract: `commander-lab.semantic-fixture-materialization/1.0.3`
- canonical materialization bundle digest: `545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b`
- materialization SHA-256: `8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5`
- provider denominator: `107`

No later WS-41 commit is promoted to predecessor authority.

## Why WS-43 G43-01 failed

WS-43 correctly proved that its inherited working-tree copy of `qualification/ws41` was not byte-identical to the exact predecessor namespace at `24152acf...`:

- same path set: 18/18;
- matching blobs: 13/18;
- changed blobs: 5/18.

The five changed paths are:

1. `qualification/ws41/WS41_BUNDLE_MANIFEST_v1_0_3.json`
2. `qualification/ws41/WS41_EVIDENCE_INDEX.json`
3. `qualification/ws41/WS41_FINAL_HANDOFF.md`
4. `qualification/ws41/WS41_SHA256SUMS`
5. `qualification/ws41/WS41_VALIDATION.json`

Those changes came from later WS-41 terminal-attestation work. They changed evidence/attestation packaging, including the evidence-bundle digest, but did not change the canonical semantic materialization bytes.

## Binding interpretation

### 1. The predecessor is a detached immutable Git source, not the descendant working-tree copy

All v1.0.4 successor derivation MUST read v1.0.3 predecessor authority from the exact Git object at commit `24152acf...`, e.g. via exact commit checkout, `git show`, detached worktree, or equivalent byte-exact mechanism.

The inherited descendant branch copy of `qualification/ws41` is NOT predecessor authority and MUST NOT be used as a substitute merely because it is present in the working tree.

### 2. Semantic continuity across later WS-41 attestation commits

Later WS-41 terminal-attestation commits are permitted to differ only outside the immutable semantic payload defined below.

They do not replace the predecessor lock.

They may be used only as later evidence/attestation provenance.

### 3. Immutable semantic payload

For predecessor semantic-continuity checking, the following 13 files constitute the immutable v1.0.3 semantic/support payload and must be byte-identical to the exact `24152acf...` versions whenever a later WS-41 state is inspected:

1. `SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json`
2. `SEMANTIC_FIXTURE_SCHEMA_v1_0_3.json`
3. `SUPERSEDES_v1_0_2.json`
4. `WS41_DIGEST_LINEAGE.json`
5. `WS41_PILOT_CHOICE_SUPERSESSION_PROOF.json`
6. `WS41_PROVIDER_DENOMINATOR_107.json`
7. `WS41_REMAINING_DEFECTS_2.json`
8. `WS41_SEMANTIC_EXECUTABILITY_REPORT_135.json`
9. `WS41_SEMANTIC_LINTER_RULES.json`
10. `WS41_SOURCE_LOCK.json`
11. `WS41_TARGETED_STACK_STATE_AUDIT_135.json`
12. `WS41_WS32_CONTENT_INTEGRITY_COMPARISON.json`
13. `WS41_WS39_CONTRADICTION_REPRODUCTION.json`

Paths are relative to `qualification/ws41/`.

The following five files are explicitly classified as mutable terminal-attestation/evidence packaging relative to the pinned predecessor source and therefore are NOT required to remain byte-identical across later WS-41 attestation commits:

1. `WS41_BUNDLE_MANIFEST_v1_0_3.json`
2. `WS41_EVIDENCE_INDEX.json`
3. `WS41_FINAL_HANDOFF.md`
4. `WS41_SHA256SUMS`
5. `WS41_VALIDATION.json`

This is not permission to edit the pinned predecessor commit. It is only a classification of later descendant attestation drift.

### 4. Canonical semantic identity remains unchanged

The canonical v1.0.3 semantic materialization remains:

- Git blob: `a05106d42ff3e51fe68acf45bb03aa356784142c`
- SHA-256: `8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5`
- canonical materialization bundle digest: `545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b`

The later evidence-bundle digest `706e8e...` is terminal evidence packaging and is NOT the downstream semantic source-lock identity.

### 5. WS-41 itself supports this interpretation

Later WS-41 `WS41_VALIDATION.json` explicitly records a `successor_contract_source_lock` pointing downstream back to exact commit `24152acf...` / tree `428bbe58...` and states that later terminal WS-41 attestation commits may not alter canonical semantic materialization bytes.

Therefore no later WS-41 commit is silently promoted.

## Supersession of WS-43 gate semantics

WS-43 remains terminal and is not reopened.

Its finding `G43-01 = FAIL` was correct under the then-binding requirement that the descendant working-tree `qualification/ws41` namespace itself remain 18/18 byte-identical.

WS-44 supersedes only that gate definition.

WS-44 MUST NOT claim that G43-01 was PASS.

Instead WS-44 introduces a new predecessor-integrity gate that requires:

1. exact retrieval of the pinned predecessor commit/tree;
2. complete byte verification of the pinned namespace at that commit;
3. byte equality of the 13-file immutable semantic/support payload if later WS-41 attestation state is compared;
4. later drift restricted exactly to the five allowlisted attestation/evidence files;
5. canonical semantic materialization identity unchanged;
6. all v1.0.4 derivation performed from the pinned predecessor bytes, not descendant copies.

## Forbidden interpretations

WS-44 may not:

- reconstruct or rewrite WS-41 in place;
- promote `de478cf...` or another later WS-41 commit to predecessor authority;
- treat evidence-bundle digest changes as semantic contract changes;
- consume the descendant working-tree `qualification/ws41` namespace without verifying it against the pinned source;
- relax semantic/materialization equality beyond the explicit five-file attestation allowlist;
- import Forge/XMage provider PASS.

## Downstream consequence

Because no v1.0.4 schema/materialization/freeze was ever emitted by WS-43, version `commander-lab.semantic-fixture-materialization/1.0.4` remains available for the next successful successor freeze.

WS-44 owns the authority reconciliation plus complete v1.0.4 repair/freeze attempt.

No provider runtime, AF07, or Architecture Freeze is granted by this decision.
