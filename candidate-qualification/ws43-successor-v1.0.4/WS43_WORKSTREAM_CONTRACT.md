# WS-43 — SUCCESSOR CONTRACT v1.0.4 REFERENTIAL-INTEGRITY REPAIR + IMMUTABLE FREEZE

## Objective
Supersede immutable WS-41 `commander-lab.semantic-fixture-materialization/1.0.3` with a new provider-neutral successor contract that repairs the WS-40-proven MICRO target identity defect without changing the frozen semantic obligations, adds complete referential-integrity linting over all semantic object references, revalidates the complete 135-record corpus, and freezes a new immutable source lock for fresh Forge and XMage qualification.

## Inputs
### WS-41 immutable predecessor
- repo `moeendres-png/commander-playtest-lab`
- commit `24152acf36b5a560c23ccacfed3f31d3039537eb`
- tree `428bbe58b2ea7b869200521092a8768108029b47`
- namespace `qualification/ws41`
- schema `commander-lab.semantic-fixture-materialization/1.0.3`
- bundle digest `545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b`
- materialization SHA-256 `8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5`
- provider denominator `107`

### WS-40 terminal defect authority
- terminal branch head `87b0a571cb3f9d18378150e3546fbe8fac4b6366`
- terminal evidence commit/tree `fbb4b9c8534b11b8daf70a162fdb081d34ac2ab7` / `0697ea0c6821f4590290823b86a1f62b52947379`
- classification `TERMINAL_IMMUTABLE_CONTRACT_DEFECT`
- first failing record `MICRO_PRIORITY`, record index 56
- failure `WS40_STATE_TARGET_UNBOUND:obj:P2-bears`
- runtime run/job/artifact `33935065462` / `101221261106` / `9959955219`
- artifact ZIP SHA-256 `32704c208c54455902091aec043a9bb6a5a49017694102661c893a993d3ca104`

## Authority
1. newest direct user instruction;
2. fresh repository/runtime evidence;
3. current canonical MTG authority for rules semantics;
4. frozen predecessor obligations as semantic provenance;
5. provider behavior only as implementation evidence, never semantic authority.

## In Scope
- reproduce the WS-40 MICRO identity defect from the immutable v1.0.3 bytes;
- determine the exact intended record-local referent for `MICRO_PRIORITY` and `MICRO_STACK` without provider-specific heuristics;
- repair only representation/identity if the frozen obligation is preserved;
- create `commander-lab.semantic-fixture-materialization/1.0.4`;
- add global exact referential-integrity linting over all 135 records;
- preserve v1.0.3 byte-for-byte as immutable provenance;
- recompute all dependent requested-state, record, bundle, manifest and lineage digests;
- deterministic double materialization;
- complete 135/135 semantic-executability validation;
- exact provider denominator reconciliation, expected 107;
- persist an immutable freeze and complete evidence/handoff.

## Out of Scope
- Forge implementation or runtime qualification;
- XMage implementation or runtime qualification;
- WS-37 Actual-Card runtime;
- AF07;
- Architecture Freeze;
- editing WS-41 v1.0.3 in place;
- importing provider PASS from any predecessor contract.

## Required MICRO Repair Adjudication
The known records contain requested target identifier `obj:P2-bears`, but no exact record-local semantic object with that ID. Two distinct P2-controlled Grizzly Bears exist: `obj:p2-bears` and `obj:micro-target`; the frozen native procedure explicitly names `obj:micro-target`.

Do not assume case folding, card-name matching, controller matching, lineage guessing, or provider-native identity is authoritative.

Independently prove from the record-local semantic obligation, procedure, predecessor provenance and current rules meaning which exact semantic object is intended. The working hypothesis is `obj:micro-target`, but it must be proven rather than assumed.

If the correction changes the actual obligation rather than repairing its referential representation, fail closed with `OBLIGATION_CONTRADICTION`.

## Global Referential-Integrity Linter
Add fail-closed lint coverage over every semantic reference field in every record, including at minimum:
- stack targets and target groups;
- attachment/enchant/equip references;
- combat attacker/blocker/defender references;
- damage recipients and prevention/replacement object references;
- source/object/controller/owner references where encoded as semantic object IDs;
- trigger/replacement/copied-object references;
- transaction/procedure action object references;
- zone-transition object references;
- decision bindings and legal-option object references;
- explicit lineage/alias mappings.

Requirements:
1. object IDs are case-sensitive exact identities;
2. every object reference resolves to exactly one record-local semantic object unless the schema explicitly declares a different typed namespace such as player ID;
3. no implicit case-folding;
4. no name/controller/owner inference;
5. no ambiguous alias;
6. any explicit alias must be one-to-one, declared, schema-valid and included in canonical serialization/digests;
7. procedure references and requested-state references must agree on identity unless an explicit semantic transition explains the difference;
8. dangling, multiply-resolved, wrong-namespace or ambiguous references are hard defects;
9. linter output must identify fixture ID, field path, referenced ID, candidate referents and defect classification.

Audit the complete 135-record corpus; do not limit the lint to MICRO records.

## Hard Gates
- G43-01: WS-41 v1.0.3 namespace preserved byte-for-byte.
- G43-02: WS-40 MICRO defect independently reproduced.
- G43-03: exact intended MICRO referent proven provider-neutrally.
- G43-04: MICRO_PRIORITY obligation unchanged.
- G43-05: MICRO_STACK obligation unchanged.
- G43-06: repaired MICRO references resolve exactly once.
- G43-07: global referential-integrity lint `0 defects`.
- G43-08: all inherited targeted-stack/cast-completion lint remains PASS.
- G43-09: complete semantic executability `135/135 PASS`.
- G43-10: family counts and AF mappings preserved.
- G43-11: provider denominator exactly `107` unless a separately proven contract-level reason requires otherwise.
- G43-12: all modified-content digests recomputed with explicit v1.0.3 -> v1.0.4 lineage.
- G43-13: deterministic double materialization byte-for-byte PASS.
- G43-14: no provider runtime/PASS imported; AF07 false; Architecture Freeze false.
- G43-15: persistent immutable v1.0.4 freeze exists in Git and is independently regenerated/verified by CI.

Any failed hard gate prevents freeze.

## Required Deliverables
At minimum:
1. `WS43_SOURCE_LOCK.json`
2. `WS43_WS40_MICRO_DEFECT_REPRODUCTION.json`
3. `WS43_MICRO_TARGET_IDENTITY_ADJUDICATION.json`
4. `WS43_REFERENTIAL_INTEGRITY_AUDIT_135.json`
5. `WS43_REFERENTIAL_INTEGRITY_LINTER_RULES.json`
6. successor linter implementation
7. `SEMANTIC_FIXTURE_SCHEMA_v1_0_4.json`
8. `SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_4.json`
9. `WS43_SEMANTIC_EXECUTABILITY_REPORT_135.json`
10. `WS43_PROVIDER_DENOMINATOR_107.json`
11. `WS43_DIGEST_LINEAGE.json`
12. `SUPERSEDES_v1_0_3.json`
13. `WS43_VALIDATION.json`
14. `WS43_EVIDENCE_INDEX.json`
15. `WS43_SHA256SUMS`
16. complete CI evidence artifact
17. `WS43_FINAL_HANDOFF.md`
18. Draft PR; do not merge.

## Evidence Requirements
- every material intermediate checkpoint persisted;
- no historical provider runtime credit;
- exact old/new field-level diff for every changed record;
- exact obligation digest comparison before/after;
- complete record-ID accounting;
- complete referential-integrity audit, not sampled;
- exact commit/tree/run/job/artifact/checksum identities;
- byte-level predecessor immutability proof;
- deterministic regeneration proof.

## Success Classification
`WS43 = COMPLETE / PASS_SUCCESSOR_CONTRACT_V1_0_4_FREEZE`

`SUCCESSOR_CONTRACT_FROZEN = TRUE`

This grants no Forge/XMage provider PASS, no AF07 and no Architecture Freeze.

## Stop Conditions
Stop fail-closed only if:
- the MICRO correction changes the semantic obligation;
- another unresolved contract/authority contradiction is found;
- referential integrity cannot be made globally deterministic without provider-specific semantics;
- deterministic materialization or predecessor immutability cannot be proven.

Do not stop at technically remediable linter/materialization defects.

## Exact Next Action After Success
Freshly qualify Forge and XMage from zero successor-runtime credit against the exact immutable v1.0.4 source lock. Do not resume v1.0.3 qualification and do not import v1.0.3 provider PASS.
