# WS-43 FINAL HANDOFF — TERMINAL PREDECESSOR-IMMUTABILITY FAILURE

## Source Lock

WS-43 executed on repository `moeendres-png/commander-playtest-lab`, branch `ws43/successor-contract-v1.0.4-freeze`.

Freshly observed WS-43 start state before any WS-43 execution change:
- commit `6dae51bf6554f34466552f1c331e4347641a1a11`
- tree `c619e65ff6c5f6153c9601d9a5e9c9189e39718e`

Binding immutable WS-41 predecessor from the WS-43 contract:
- commit `24152acf36b5a560c23ccacfed3f31d3039537eb`
- tree `428bbe58b2ea7b869200521092a8768108029b47`
- namespace `qualification/ws41`
- pinned namespace tree `af8a26e7e74a859d5f4a983b69e4ff108e7123f4`
- contract `commander-lab.semantic-fixture-materialization/1.0.3`
- canonical materialization bundle digest `545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b`
- materialization SHA-256 `8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5`
- materialization Git blob `a05106d42ff3e51fe68acf45bb03aa356784142c`
- materialization bytes `1334098`
- provider denominator `107`

Persistent WS-43 evidence checkpoint:
- commit `e3ed92b2a677a2957390c40ac24625139e7cbd6e`
- tree `e434038ff463f4fbe68a63842af46968018b3c7c`

## WS40 Defect Reproduction

`NOT_RUN_DUE_TERMINAL_G43_01`.

The WS-43 contract requires G43-01 predecessor immutability before continuing. WS-40 terminal defect evidence remains binding input, but WS-43 did not create successor-runtime or successor-materialization evidence after G43-01 failed.

Known terminal input remains:
- first failing fixture `MICRO_PRIORITY`
- record index `56`
- error `WS40_STATE_TARGET_UNBOUND:obj:P2-bears`
- WS-40 terminal head `87b0a571cb3f9d18378150e3546fbe8fac4b6366`
- terminal evidence commit/tree `fbb4b9c8534b11b8daf70a162fdb081d34ac2ab7` / `0697ea0c6821f4590290823b86a1f62b52947379`

## MICRO Identity Adjudication

`NOT_RUN_DUE_TERMINAL_G43_01`.

No representation repair was attempted. No semantic obligation was changed. No provider-side case folding, name/controller/owner matching, alias inference, request echo, or other heuristic identity repair was introduced.

## v1.0.3 Preservation

### Required gate

G43-01 requires: `WS-41 v1.0.3 namespace preserved byte-for-byte`.

The WS-43 contract directly pins commit/tree `24152acf...` / `428bbe58...` and requires byte-level predecessor immutability proof over the complete `qualification/ws41` path set.

### Complete path-set comparison

Pinned predecessor `qualification/ws41`:
- namespace tree `af8a26e7e74a859d5f4a983b69e4ff108e7123f4`
- file count `18`

WS-43 start branch `qualification/ws41`:
- namespace tree `cf40fe6157d4681dda31c1fe2b2aacb9cecbb374`
- file count `18`

Path set is identical, but blob identity is not.

Exact result:
- `13/18` paths are byte-identical by Git blob identity and size.
- `5/18` paths differ.

Mismatching paths:
1. `qualification/ws41/WS41_BUNDLE_MANIFEST_v1_0_3.json`
   - pinned blob `c4b3a41f63f07d7989ab4af0ca419cc7438841a7`
   - observed blob `50adf0c5bb17dd0b37724c7aef8f6d6941a569bb`
2. `qualification/ws41/WS41_EVIDENCE_INDEX.json`
   - pinned blob `3f28f637883dc0e792c17927ef28d562a12d7f6e`
   - observed blob `b7cc4e26f8bef7aeba75f9bfc4f483c875491a65`
3. `qualification/ws41/WS41_FINAL_HANDOFF.md`
   - pinned blob `b6f19995c20f831332e121defaeffb7b424ebcb3`
   - observed blob `043b5de16e0594de116876bc993460778b1631bb`
4. `qualification/ws41/WS41_SHA256SUMS`
   - pinned blob `949755700bf8a324559518a665bf76bacd4257f4`
   - observed blob `94a12e47701f9b8e3ccbdd27a80465f5bf3cb8ae`
5. `qualification/ws41/WS41_VALIDATION.json`
   - pinned blob `51e8e5fee09e2ce800490eede95898747b679c26`
   - observed blob `41b7e26861e628fd810a04e35e798e0bc91056d3`

The canonical semantic materialization itself is unchanged:
- pinned and observed blob `a05106d42ff3e51fe68acf45bb03aa356784142c`
- SHA-256 `8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5`

Repository history explains the divergence. After the explicitly pinned source-lock commit, commit `a5f6d4bdfa47634e16f1f8b8aa6647e9ffe6c1d3` added downstream source-lock attestation, followed by bot regeneration commit `e83e6998aa16cdb4cb422ceecab6c517043ab742`. Those changes were evidence/attestation-oriented and preserved the canonical materialization bytes, but they changed files inside the exact namespace that the current WS-43 contract requires to be byte-identical to the earlier pinned commit.

Therefore:
- `G43-01 = FAIL`
- classification `DIGEST_INTEGRITY_DEFECT`
- the explicit WS-43 stop condition `predecessor immutability cannot be proven` is met.

WS-43 did not repair this by restoring the five files because the binding scope explicitly forbids editing WS-41 v1.0.3 in place.

WS-43 also did not silently promote a later attestation commit to predecessor authority because the current direct contract explicitly pins `24152acf...` / `428bbe58...`.

## v1.0.4 Changes

None.

No `commander-lab.semantic-fixture-materialization/1.0.4` bytes were emitted, checked in, or frozen.

## Referential-Integrity Model

`NOT_RUN_DUE_TERMINAL_G43_01`.

No successor linter implementation, alias model, schema change, or referential-integrity rule was committed after the hard-gate failure.

## Complete 135 Audit

`NOT_RUN_DUE_TERMINAL_G43_01`.

## Semantic Executability

`NOT_RUN_DUE_TERMINAL_G43_01`.

No claim of `135/135 PASS` is made.

## Provider Denominator

The predecessor authority remains `107`. No v1.0.4 denominator was materialized or granted successor credit.

## Digest Lineage

No v1.0.3 -> v1.0.4 digest lineage was generated because no successor bytes were permitted after G43-01 failed.

The predecessor namespace integrity evidence is persisted at:
`candidate-qualification/ws43-successor-v1.0.4/WS43_WS41_PREDECESSOR_NAMESPACE_INTEGRITY.json`.

## Determinism

`NOT_RUN_DUE_TERMINAL_G43_01` for v1.0.4.

The unchanged predecessor materialization blob remains exactly identified, but this does not satisfy the stricter complete-namespace G43-01 requirement.

## Tests / Evidence

Persisted WS-43 evidence:
- `candidate-qualification/ws43-successor-v1.0.4/WS43_SOURCE_LOCK.json`
- `candidate-qualification/ws43-successor-v1.0.4/WS43_WS41_PREDECESSOR_NAMESPACE_INTEGRITY.json`
- `candidate-qualification/ws43-successor-v1.0.4/WS43_VALIDATION.json`
- `candidate-qualification/ws43-successor-v1.0.4/WS43_EVIDENCE_INDEX.json`
- this handoff

No provider runtime was executed.
No provider PASS was imported.
No AF07 was granted.
No Architecture Freeze was granted.
PR #157 remains Draft and must not be merged as a successful successor freeze.

## PASS / FAIL / UNKNOWN

- G43-01 `FAIL`
- G43-02 through G43-13 `NOT_RUN_DUE_TERMINAL_G43_01`
- G43-14 `PASS`
- G43-15 `NOT_RUN_DUE_TERMINAL_G43_01`

Terminal workstream classification:

`WS43 = COMPLETE / TERMINAL_FAIL_DIGEST_INTEGRITY_DEFECT`

`SUCCESSOR_CONTRACT_FROZEN = FALSE`

This is a complete fail-closed adjudication, not a successful v1.0.4 freeze.

## Remaining Blockers

Exactly one authority/scope blocker remains:

The binding WS-43 contract simultaneously requires complete byte identity of `qualification/ws41` against pinned commit `24152acf...` and forbids WS-43 from editing WS-41 v1.0.3 in place, while the actual WS-43 branch ancestry already contains five post-lock evidence/attestation mutations inside that namespace.

The canonical semantic materialization is identical, but the hard gate is defined over the complete namespace, so semantic-materialization-only identity cannot be substituted for complete namespace identity without changing the contract.

## Outputs

Terminal outputs are stored under:
`candidate-qualification/ws43-successor-v1.0.4/`

No `qualification/ws43` successor freeze namespace was created because that would falsely imply successful completion of G43-01.

## Dependencies Unblocked

None of the intended successor-provider qualification dependencies are unblocked.

Forge and XMage must not start v1.0.4 successor qualification because there is no immutable v1.0.4 source lock.

Actual-Card runtime remains blocked.

## Exact Next Action

Coordinator authority must explicitly resolve the predecessor-integrity contradiction before a successor-freeze workstream can continue. One of the following must be made authoritative in a new direct contract/reconciliation step:

1. require the WS-43 working branch to contain the exact 18-file `qualification/ws41` subtree from pinned commit `24152acf...`, with explicit authorization for the necessary branch reconstruction/restoration; or
2. redefine predecessor immutability so the pinned commit remains detached immutable provenance while later WS-41 terminal-attestation files are explicitly permitted to differ, and state exactly which bytes constitute the immutable contract namespace; or
3. explicitly supersede the pinned predecessor lock with a later exact commit/tree and rebind all dependent source identities.

Until one of those authority choices is made explicitly, treating G43-01 as PASS would violate the current contract.
