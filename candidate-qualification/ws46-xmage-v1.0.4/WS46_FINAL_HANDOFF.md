# WS-46 FINAL HANDOFF — SUPERSEDED BY IMMUTABLE v1.0.5

## Terminal Classification

```ini
WS46 = COMPLETE / SUPERSEDED_BY_IMMUTABLE_V1_0_5_CONTRACT
XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE
HISTORICAL_SUCCESSOR_RUNTIME_CREDIT_IMPORTED = 0
AF07_GRANTED = FALSE
ARCHITECTURE_FREEZE = FALSE
TASK_COMPLETE = YES
```

`TASK_COMPLETE = YES` means only that the WS-46 administrative closeout is complete. It does **not** grant XMage provider qualification or any Architecture-Freeze gate.

## Source Lock

### Commander Lab — substantive WS-46 provenance before supersession

- repository: `moeendres-png/commander-playtest-lab`
- branch: `ws46/xmage-v1.0.4-successor-qualification`
- substantive pre-supersession commit: `d599449faa4ceda17315c5db87ec783a241e20aa`
- substantive pre-supersession tree: `b86edceb0cb9316f4c565ce9f89fc9f8c91c15f4`
- binding coordinator notice commit: `b32c3de2a323a4b1bc5ad1880008372af01b7a52`
- notice commit tree: `5353181734587ec55ac86926a5941111890d244c`

The notice commit is a direct child of the substantive provenance commit.

### XMage implementation provenance

- repository: `moeendres-png/mage`
- branch provenance: `foundry/ws39-commander-history-state-restore`
- commit: `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
- tree: `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`

### Superseded WS-44 authority

WS-46 executed only against immutable WS-44 v1.0.4:

- freeze commit: `12940248497a8795991cbbd2eedef72945528cfe`
- root tree: `cd83c973b269711106d08ab5be2d7672f05bcb7c`
- namespace: `qualification/ws44`
- namespace tree: `6579e119605b90248426a3121a47c487b2bb13cd`
- contract: `commander-lab.semantic-fixture-materialization/1.0.4`
- materialization SHA-256: `9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35`
- canonical bundle digest: `77b911195525c2fe8aff37f6c9573e5772f358b25646d0be5919314ed5e23b54`
- provider denominator: `107`

WS-44 was not modified by WS-46.

### New immutable authority — WS-47 v1.0.5

Fresh live verification at terminal closeout confirmed:

- freeze commit: `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8`
- root tree: `f596c54d2cb229b9827c6c94a278175e8312c65c`
- namespace: `qualification/ws47`
- namespace tree: `12af73695c801a42a0193ee895d5fc0843d16b0c`
- contract: `commander-lab.semantic-fixture-materialization/1.0.5`
- materialization SHA-256: `0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3`
- canonical bundle digest: `631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01`
- provider denominator: `107`

The dedicated WS-47 post-freeze attestation also passed on the exact freeze commit:

- workflow: `WS47 v1.0.5 postfreeze attestation`
- run: `34235080565`
- job: `102090586149`
- conclusion: `success`
- artifact id: `10059468815`
- artifact digest: `sha256:77f6f758a5b432e9cafa0f3b6d802c8b634a941d8a10fb2dc3653368e0a9ae2e`
- post-freeze result: `G47_14 = PASS`, `G47_15 = PASS_POSTFREEZE_REGENERATION`, `regeneration_diff = PASS_BYTE_IDENTICAL`, `independent_validation = PASS`, `terminal_status = PASS`

The coordinator notice states that v1.0.5 repairs the incomplete requested blocker surface of `WS05-MP-BLOCK-4`, changes exactly that requested-state record, and changes zero obligations.

### PR state at closeout

PR `#160` is retained as provenance only and must remain:

- OPEN
- DRAFT
- UNMERGED

## Work Completed

1. Reconciled immutable WS-44 v1.0.4 against the inherited WS-42/WS-39 implementation provenance without importing historical runtime PASS.
2. Freshly source-locked and built XMage commit `0c1f455e...` and runtime-verified the native Commander cast-history and Commander-damage restoration APIs.
3. Added and exercised WS-46 v1.0.4 construction plumbing, including genuine `NATURAL_GAME_START` admission at the first external decision boundary.
4. Executed the complete 107-record fresh v1.0.4 construction diagnostic with zero deferred records.
5. Sealed the exact 19 current failure identities and audited their immutable WS-44 shapes.
6. Preserved source-proven remediation information without granting construction or behavior PASS.
7. Read and accepted the binding coordinator supersession notice and ceased all broad v1.0.4 runtime/remediation work.
8. Freshly verified the immutable WS-47 v1.0.5 authority and its successful post-freeze regeneration attestation.
9. Closed WS-46 administratively as superseded, not qualified.

## New Findings

### Binding supersession

WS-47 v1.0.5 is the sole successor-contract authority for the next XMage provider qualification cycle. No v1.0.4 runtime result is portable as v1.0.5 runtime credit.

### Exact WS-46 construction state at supersession

```ini
NATIVE_CONSTRUCTION_DIAGNOSTIC = 88/107 PASS
FAIL = 19
DEFERRED = 0
CONSTRUCTION_PASS = NOT_GRANTED
INDEPENDENT_NORMALIZATION = NOT_RUN / NOT_GRANTED
BEHAVIOR = 0/107
HISTORICAL_SUCCESSOR_RUNTIME_CREDIT_IMPORTED = 0
```

### Exact 19 failure shapes preserved as implementation provenance

**Natural start — 7**

- `PLAYER_COUNT_2P`
- `PLAYER_COUNT_3P`
- `PLAYER_COUNT_4P`
- `PLAYER_COUNT_5P`
- `PILOT_MULLIGAN`
- `WS05-CMD-MULL-2`
- `WS05-CMD-MULL-4`

Observed failure: `INVALID_SCENARIO: text natural_library_card_name`.

Immutable shape: actual Commander deck template with `Rograkh, Son of Rohgahh`, library template `{ "card_identity": "Mountain", "count": 99 }`, opening hand size 7, and genuine `NATURAL_GAME_START`.

**Face-down exile / hidden information — 2**

- `HIDDEN_05`
- `HIDDEN_06`

Observed failure: `INVALID_SCENARIO: face_down only applies to battlefield`.

Immutable shape: `obj:hidden-hand` is `Demonic Tutor`, owned/controlled by P2, in exile, `face_down: true`; P1 has a temporary native knowledge permission. HIDDEN_06 additionally requires invalidation on new-object/zone-change semantics.

**Known library range — 2**

- `HIDDEN_10`
- `HIDDEN_11`

Observed failures: `WS46_KNOWLEDGE_LIBRARY_RANGE_INVALID:P1:0:2` and `...:P2:0:2`.

Immutable shape uses zero-based `start: 0`, `count: 2`, ordered ranges; HIDDEN_11 carries `before_event: "shuffle"` and therefore an invalidation obligation.

**Extra-turn creation — 2**

- `WS05-MP-TURN-3`
- `WS05-MP-TURN-5`

Observed failure: `WS46_JSON_INTEGER_REQUIRED:resolution_sequence`.

Immutable shape uses `sequence` and `source`, not `resolution_sequence` / `source_object`. Terminal source audit also confirmed that `candidate-qualification/ws46-xmage-v1.0.4/apply_ws46_native_class_fixes.py` rewrites the otherwise correct WS46 native-class implementation back to the stale key names during CI overlay application. This is preserved as remediation provenance only; no v1.0.4 patch or rerun was performed after supersession.

**Elimination — 6**

- `WS05-MP-ELIM-OWNED-3`
- `WS05-MP-ELIM-CONTROL-3`
- `WS05-MP-ELIM-STACK-3`
- `WS05-MP-ELIM-PRIO-3`
- `WS05-MP-ELIM-TURN-3`
- `WS05-MP-ELIM-5`

Observed failure: `WS46_JSON_STRING_REQUIRED:condition`.

Immutable shape is `{ "player": <Pi>, "reason": "life_total_0" }`; the construction boundary has native life 0 while `lost` / `eliminated` remain false before SBA execution.

## Changes

### Material implementation provenance preserved

Relevant WS-46 files include:

- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs46NativeConstructionState.java`
- `candidate-qualification/ws46-xmage-v1.0.4/canonical_v104.py`
- `candidate-qualification/ws46-xmage-v1.0.4/run_full107_construction_probe_v104.py`
- `candidate-qualification/ws46-xmage-v1.0.4/apply_ws46_v104_construction_overlay.py`
- `candidate-qualification/ws46-xmage-v1.0.4/apply_ws46_native_class_fixes.py`
- WS-46 reconciliation/build/construction/failure-shape checkpoints through `WS46_CHECKPOINT_03K_IMMUTABLE_FAILURE_SHAPES.md`

### Terminal closeout changes

No additional v1.0.4 rules/provider remediation and no additional broad v1.0.4 runtime were performed after the supersession notice.

Terminal administrative persistence adds/updates only:

- `candidate-qualification/ws46-xmage-v1.0.4/WS46_FINAL_HANDOFF.md`
- `PROJECT_STATE.md`
- PR #160 metadata/body as provenance closeout

## Tests / Evidence

### WS-46 v1.0.4 reconciliation

- workflow: `WS46 XMage v1.0.4 Contract Reconciliation`
- run: `34069232685`
- job: `101583387934`
- conclusion: `success`
- artifact id: `9999907632`
- artifact digest: `sha256:be181654ffdd1a46d68bbdb06e276a093181efb5e7cbcb241de7b0eecce6e6aa`

### Fresh exact XMage build / native restore

- Commander-Lab execution commit: `e79283df3c9f0530cf0fb0115ca42f2d668da977`
- execution tree: `9d9dc2b1e13ea0b88f8edbe9566172ec250fec13`
- workflow: `WS46 XMage v1.0.4 Build + Native Restore`
- run: `34165017452`
- job: `101874241201`
- artifact id: `10033919163`
- artifact digest: `sha256:d7d4c4e8822340f7856025bcd070e898f85deae5000a01702f71930af94c613c`
- runtime tests: `9`, failures `0`, errors `0`, skipped `0`
  - Commander cast-history restore: `7`
  - Commander-damage restore: `2`

### Full107 v1.0.4 construction diagnostic

- workflow: `WS46 XMage v1.0.4 Full107 Construction v2`
- run: `34221583745`
- tested head: `d5f534f7014e78b272983b0548e3c5ce266fde35`
- job: `102045705813`
- artifact id: `10054580582`
- artifact name: `ws46-v104-construction-v2-d5f534f7014e78b272983b0548e3c5ce266fde35`
- artifact digest: `sha256:a355642467116934642344b95e29de5cdcca5e73a899e001cccc64e5b0a196a1`
- probe SHA-256: `79867549f065e8f2c457b93c90fac56e3e9ac38aa88cc2c83da2dea602328061`
- result: `88 PASS / 19 FAIL / 0 DEFERRED`
- imported historical runtime credit: `0`

### Immutable failure-shape audit

- workflow: `WS46 XMage v1.0.4 Current Failure Shape Audit`
- run: `34230112246`
- job: `102073817884`
- tested head: `e4557fb73046a3a81c2219d1cadf844f3da65083`
- artifact id: `10057443340`
- artifact digest: `sha256:5928a5f1e0012f393bf66958ae77afad59020b9b6ef33913e765088dd980c8dc`
- `WS46_CURRENT_FAILURE_SHAPES.json` SHA-256: `5b3690daecdb5a330a7631a2c5ee2cf03d842f0dbb3f6c7936bc19e2fc6d1787`
- result: exact 19 failing fixture shapes source-locked against WS-44

### WS-47 post-freeze authority attestation

- workflow: `WS47 v1.0.5 postfreeze attestation`
- run: `34235080565`
- job: `102090586149`
- artifact id: `10059468815`
- artifact digest: `sha256:77f6f758a5b432e9cafa0f3b6d802c8b634a941d8a10fb2dc3653368e0a9ae2e`
- result: `PASS`
- byte-identical regeneration: `PASS`
- independent validation: `PASS`
- `G47_15 = PASS_POSTFREEZE_REGENERATION`
- provider runtime executed by WS-47: `false`
- provider PASS imported by WS-47: `false`

## Gate Matrix

| WS-46 gate | Status | Terminal evidence |
|---|---|---|
| Reconciliation | PASS | Fresh v1.0.4 reconciliation run passed |
| Exact WS-44 source lock | PASS | Immutable commit/tree/namespace/digests verified |
| Exact XMage source/build lock | PASS | Fresh exact build on pinned commit/tree |
| Native restore APIs runtime | PASS | 9/9 restore tests passed |
| Native construction 107/107 | FAIL | 88/107; 19 failures; 0 deferred |
| Independent native-readback normalization 107/107 | UNKNOWN | Not executed because construction never closed before supersession |
| Request echo exclusion in construction diagnostic | PASS | Historical/whole-request echo not accepted as proof; imported runtime credit 0 |
| Behavior 107/107 | UNKNOWN | 0/107 executed |
| AF04 | UNKNOWN | Not freshly closed for v1.0.4 |
| AF05 | UNKNOWN | Not freshly closed for v1.0.4 |
| AF06 | UNKNOWN | Not freshly closed for v1.0.4 |
| AF08 | UNKNOWN | Not freshly closed for v1.0.4 |
| AF09 | UNKNOWN | Not freshly closed for v1.0.4 |
| CARD_02 overall | UNKNOWN | Full behavior gate not executed |
| Hidden-information adversarial | UNKNOWN | Not freshly closed for v1.0.4 |
| Opaque-handle adversarial | UNKNOWN | Not freshly closed for v1.0.4 |
| Replay/RNG | UNKNOWN | Not freshly closed for v1.0.4 |
| Strict pilot fail-closed | UNKNOWN | Not freshly closed for v1.0.4 |
| Unsupported production decision paths = 0 | UNKNOWN | Not freshly proven for v1.0.4 |
| XMage successor provider qualification | FAIL | Required success gates incomplete; provider qualification not granted |
| WS-46 terminal administrative supersession | PASS | Binding coordinator notice + fresh WS-47 authority verification |

UNKNOWN is not PASS. No incomplete provider gate is promoted by this closeout.

## Remaining Blockers

### WS-46 administrative closeout

None. WS-46 is terminal because its governing v1.0.4 contract was superseded by immutable v1.0.5 before provider qualification completed.

### Preserved technical blockers / provenance

The 19 v1.0.4 construction failures and their source-proven shapes remain preserved for implementation provenance. They are not actionable inside WS-46 after supersession and must be freshly impact-diffed against v1.0.5 before reuse.

### Global / out-of-scope gates

```ini
AF07 = NOT GRANTED
ARCHITECTURE_FREEZE = NOT GRANTED
WS37_ACTUAL_CARD_RUNTIME = NOT EXECUTED
FORGE = UNTOUCHED
WS44 = IMMUTABLE / UNMODIFIED
WS47 = IMMUTABLE AUTHORITY
PR160 = DRAFT / OPEN / UNMERGED
```

## Outputs

Terminal and preserved outputs include:

- `candidate-qualification/ws46-xmage-v1.0.4/WS46_FINAL_HANDOFF.md`
- `candidate-qualification/ws46-xmage-v1.0.4/WS46_COORDINATOR_V1_0_4_SUPERSESSION_NOTICE.md`
- `candidate-qualification/ws46-xmage-v1.0.4/WS46_CHECKPOINT_03K_IMMUTABLE_FAILURE_SHAPES.md`
- `candidate-qualification/ws46-xmage-v1.0.4/WS46_CHECKPOINT_03J_CURRENT_ARTIFACT_CONTENT_LOCK.md`
- all earlier WS-46 checkpoints and implementation overlays on PR #160
- `PROJECT_STATE.md`

## Dependencies Unblocked

The coordinator may now treat WS-46 as terminal provenance and start the next XMage provider qualification against immutable WS-47 v1.0.5.

Reusable material is limited to implementation/remediation provenance. The next workstream must begin with:

```ini
HISTORICAL_SUCCESSOR_RUNTIME_CREDIT = 0
```

and must freshly impact-diff v1.0.5 before deciding which WS-46 implementation paths remain valid.

## Exact Next Action

Coordinator: initiate the new XMage v1.0.5 provider qualification against immutable WS-47, starting at zero successor-runtime credit, using WS-46 code/failure-shape work only as provenance. Keep PR #160 Draft/open/unmerged as the terminal WS-46 record.

## Terminal Strings

```ini
WS46 = COMPLETE / SUPERSEDED_BY_IMMUTABLE_V1_0_5_CONTRACT
XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE
HISTORICAL_SUCCESSOR_RUNTIME_CREDIT_IMPORTED = 0
AF07_GRANTED = FALSE
ARCHITECTURE_FREEZE = FALSE
WS37_ACTUAL_CARD_RUNTIME = NOT_EXECUTED
FORGE = UNTOUCHED
WS44 = IMMUTABLE / UNMODIFIED
PR160 = DRAFT / OPEN / UNMERGED
TASK_COMPLETE = YES
```
