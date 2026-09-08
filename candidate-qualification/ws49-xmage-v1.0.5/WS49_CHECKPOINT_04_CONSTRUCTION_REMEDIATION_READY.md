# WS-49 CHECKPOINT 04 — CONSTRUCTION REMEDIATION READY FOR FRESH FULL107

Status: **PERSISTED / NO PASS CREDIT GRANTED**

## Source basis

Immutable WS-47 remains locked to:

- commit `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8`
- tree `f596c54d2cb229b9827c6c94a278175e8312c65c`
- namespace tree `12af73695c801a42a0193ee895d5fc0843d16b0c`
- materialization `commander-lab.semantic-fixture-materialization/1.0.5`
- materialization SHA-256 `0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3`
- denominator `107`

XMage remains locked to:

- commit `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
- tree `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`

Historical successor runtime credit imported: **0**.

## Fresh failure evidence being remediated

The last complete fresh construction sequence before this remediation was:

- provider head `d77881eae09feaebbedd77a4250131e7bc5c83a7`
- workflow run `34261504195`
- job `102180316335`
- result `92/107 NATIVE_SETUP_PASS_AWAITING_INDEPENDENT_NORMALIZATION`
- result `15/107 FAIL_CLOSED_NATIVE_CONSTRUCTION`
- artifact `10071590222`
- artifact ZIP SHA-256 `89d22f2514bee7cfcb7a67c98f79160aa5ba751ea788f1707b1390e4b943c6f5`

That run also proved:

- XMage reactor build `40/40` modules BUILD SUCCESS;
- bridge `60/60` tests PASS;
- exact source locks and denominator reconstruction PASS.

The exact 15 failures were:

### Natural start — 7

- `PLAYER_COUNT_2P`
- `PLAYER_COUNT_3P`
- `PLAYER_COUNT_4P`
- `PLAYER_COUNT_5P`
- `PILOT_MULLIGAN`
- `WS05-CMD-MULL-2`
- `WS05-CMD-MULL-4`

Failure shape: v1.0.5 `deck_state` is a list, while the WS49 adapter still expected the superseded object shape.

### Hidden library range — 2

- `HIDDEN_10`
- `HIDDEN_11`

Failure shape: `WS46_KNOWLEDGE_LIBRARY_RANGE_INVALID:<player>:0:2`. The native state-load path had cleared the imported inert library and materialized no physical cards for a top-2 knowledge range that intentionally has no semantic card identities.

### Elimination cleanup — 6

- `WS05-MP-ELIM-OWNED-3`
- `WS05-MP-ELIM-CONTROL-3`
- `WS05-MP-ELIM-STACK-3`
- `WS05-MP-ELIM-PRIO-3`
- `WS05-MP-ELIM-TURN-3`
- `WS05-MP-ELIM-5`

Failure shape: post-SBA `WS39_COMMANDER_NATIVE_MAPPING_NOT_UNIQUE:<commander>:matches=0` after XMage had already correctly removed the eliminated player's live Commander object.

## Persisted bounded remediation

1. `canonical_v105.py`
   - parses the immutable v1.0.5 `deck_state[]` shape;
   - resolves `commander_ids` against `commander_state.commanders`;
   - requires exact `Mountain x99`, opening hand size `7`, and per-player `library_shuffle:<P#>` channel binding;
   - removes inherited provider filler from NATURAL_GAME_START decks.

2. `apply_ws49_native_remediation.py`
   - retains only enough unbound imported native library cards to satisfy required top-N knowledge ranges, without assigning fabricated semantic identities;
   - preserves strict native `LookedAt` knowledge application;
   - recognizes only the exact configured eliminated player after native loss and proves its Commander is absent rather than demanding a stale live mapping;
   - retains the previously source-audited v1.0.5 `reason` field, exact combat attacking-player binding, and face-down exile support.

3. `apply_ws49_compile_guard.py`
   - fail-closed replacement of a WS49-introduced nonexistent helper reference after inherited overlays;
   - no game-state mutation.

4. `apply_ws49_readback_evidence_overlay.py`
   - adds request-independent native natural-deck readback from XMage `Deck.getCards/Deck.getSideboard`;
   - adds native `Card.isFaceDown(game)` to the privileged semantic setup snapshot;
   - read-only evidence plumbing only, for later independent G49-08 normalization.

5. `audit_prior19_v105.py`
   - audits the real v1.0.5 list/reference natural-deck shape rather than the superseded shape.

## Authority / safety invariants

The remediation does **not**:

- modify WS-47;
- calculate Magic legality in Commander Lab;
- introduce first/random/default/AI/GUI/silent/parent fallback behavior;
- fabricate semantic card identities for HIDDEN_10/11;
- fabricate historical game actions;
- import any historical runtime PASS;
- grant behavior credit, AF07, or Architecture Freeze.

## Required next evidence

A new exact-head sequence must now prove, from record 1 through record 107:

1. bootstrap/impact/source-lock PASS;
2. XMage and bridge build PASS;
3. all `107/107` rows reach `NATIVE_SETUP_PASS_AWAITING_INDEPENDENT_NORMALIZATION`;
4. unsupported dimension count remains zero;
5. no construction PASS is granted until the separate G49-08 normalizer passes all 107.

Until that fresh sequence succeeds:

`G49-07 = FAIL / NOT_CLOSED`

`G49-08 = NOT_RUN`

`WS49 = INCOMPLETE`
