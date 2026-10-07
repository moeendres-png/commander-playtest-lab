# E-B2: face-down construction (Forge bridge + Lab lane)

Status: implemented in the Forge half (PR #34, head `31cbae1264`) and repinned on the Lab
branch in this revision. Evidence class: `CODE_DERIVED` plus real-engine unit evidence in
the Forge bridge module, plus the regenerated AF05 census bound to the pinned head. No
qualification row was executed, no receipt exists, and no row verdict changed
(`UNKNOWN != PASS`). The pinned head is the PR #34 head, not a merge commit; the final pin
follows forge#34's merge commit with its own lock update.

## Authority

- CR 708.2: whether a permanent is face down is public game state, so the Forge projection
  emits `face_down` to every observer.
- CR 701.34 (manifest): the supported kind is `MANIFESTED`; a manifested face-down
  permanent is a 2/2 with no name or abilities (CR 708.2a face-down characteristics).
- Engine precedent for the state setup: `forge-game/src/main/java/forge/game/GameState.java`
  lines 1310-1313 (`FaceDown` / `Manifested` branch): `turnFaceDown(true)` then
  `setManifested(new SpellAbility.EmptySa(ApiType.Manifest, card))`.
- Rules-Core principle: the Lab never chooses for a player. Construction only sets state;
  the controller-only look permission is not constructed here (E-B3).

## Forge (`forge-protocol2-bridge`, PR #34 head `31cbae1264` on `hardening/forge-eb2-face-down-20261007`)

- `ScenarioBootstrap.Placement`: `faceDown` (default false) and `faceDownType`.
  Parse rejections: `face_down must be a boolean`; `face_down_type unsupported: X` (missing
  or not `MANIFESTED`); `face_down placement cannot be attached`.
- `placeBattlefield`: right after the card enters the controller's battlefield,
  `turnFaceDown(true)`, `setManifested(new SpellAbility.EmptySa(ApiType.Manifest, card))`,
  `updateStateForView()`; fail closed if `turnFaceDown` returns false and the card is not face
  down; audit `scenario_placed_face_down` (card, controller, type). Counters are unchanged.
- Deviation from the bare precedent (found by the real-engine test): `updateStateForView()`
  reads `getManifestedSA().getCardState()` for the face-down image key and the engine's bare
  `EmptySa` leaves it null (NPE). The bridge records the true Original state on the
  manifest ability before the view refresh. `GameState` itself never refreshes the view there.
- Post-untap hook (`applyPostUntap` -> `verifyRequestedFaceDown`): throws if a requested
  face-down card left the battlefield, is no longer face down, or is no longer manifested.
- Review P3 (6039789823): the failed-placement `IllegalStateException` chains its cause
  (`throw new IllegalStateException("face-down placement failed", t)`) instead of dropping
  it, so a real NPE in the state setup is distinguishable from a placement failure.
- `StateProjection.battlefieldDetails`: `face_down` (boolean, every observer);
  `face_down_type` (`MANIFESTED` / `CLOAKED` / `FACE_DOWN`) only when the observer's shown
  name is not a redacted marker, otherwise JSON null. Name/power/toughness redaction untouched.

## Lab (`hardening/forge-eb2-face-down-lab-20261007`)

- `forge_scenario_lane.py`: emits `face_down: true` and `face_down_type` for a true record
  object; `_SUPPORTED_FIELD_ASSERTIONS["battlefield.face_down"]` (three exact fragments of the
  new Java); `face_down` removed from `_UNOBSERVABLE_RECORD_DIMENSIONS`.
  `semantic_objects.face_down` stays a hard unsupported dimension only for what the bridge
  cannot build (non-`MANIFESTED` kind, missing kind, non-battlefield zone, attached).
- Checkpoint (`_face_down_verdicts`): `face_down` compared with `is True` / `is False`, no
  `bool()` coercion; `face_down_type` compared from the controller-observer readback when the
  record states one; a face-down placement is located in the controller's own seat view (an
  opponent sees `<face-down>`). A missing or non-bool/non-string readback is `UNKNOWN`
  (new `CHECKPOINT_UNKNOWN`, result `CHECKPOINT_READBACK_UNKNOWN`), never EXACT, never
  credit-eligible.
- Look permission is **not** closed: a face-down record object whose structured
  `knowledge_state.viewer_states[*].face_down_look_permissions` (or, additionally, whose
  `construction_notes`) grant a look permission adds the hard unsupported dimension
  `knowledge_state.face_down_look_permissions` (mapped to `knowledge_construction`, E-B3).
  The generic non-empty `knowledge_state` still yields `knowledge_state`.
- AF05 census (`forge_hidden_information.py`): `face_down_construction` is now `SUPPORTED`
  (fragments from the new Java), `BOOTSTRAP_FIELDS` gains `face_down`, `face_down_type`.
  `forge_residuals.py`: gap text for the remaining face-down kinds.

## Repin (this revision)

`config/rules_engines.json` pins the bridge at the forge#34 head
`31cbae12640e6066499aa7f17c9bf2dba6a30da6` (tree `b5c19c19`, PR #34 on
`hardening/forge-eb2-face-down-20261007`; `ASSERTED_BRIDGE_COMMIT`, `CURRENT_BRIDGE(_TREE)`
and `CANONICAL_FORGE_BRIDGE_COMMIT` mirror it). The head is E-B2 plus the P3 cause chaining,
merged onto the forge#35 successor line `d9e356aa`; over `d9e356aa` only the three
`forge-protocol2-bridge/` files changed (0 Rules-Core, 0 card-data).

1. `docs/forge_af05_hidden_20261003/FORGE_AF05_MATRIX.json` was regenerated with
   `scripts/run_forge_hidden_census.py --forge-root <forge checkout>` at the pinned head:
   20 rows, 20 `PROVIDER_ADAPTER_GAP`, pass 0, UNKNOWN.
2. `tests/qualification/test_forge_hidden_information.py::test_the_committed_matrix_is_current`
   is green on the regenerated matrix; the expected-red comment is removed.
3. `qualification/forge-bridge-g1r1-turnbegan-20261006/SUCCESSOR_SOURCE_LOCK.json` records the
   new source, its ancestry and its exact-head CI: Test build push run `37634912575` completed
   **success** (Java 17/21; the pull_request run `37634922429` mirrors it) and the iOS
   compatibility gate push run `37634912612` plus pull-request run `37634922406` completed
   success. No prior run id is reused; PB-03 stays PENDING.
4. `scripts/run_forge_residual_census.py` was re-run: no change (source-independent).

The census is bound to the pinned blobs, not computed in scratch:

| | before (`ee37e4a5` base) | at the pinned head |
|---|---|---|
| rows / classification | 20 / 20 PROVIDER_ADAPTER_GAP | 20 / 20 PROVIDER_ADAPTER_GAP |
| `face_down_construction` gaps | 20 | 0 |
| `knowledge_construction` gaps | 12 | 32 (12 + 20 look-permission, E-B3) |
| `library_construction` / `cost_state_construction` | 20 / 14 | 20 / 14 |
| verdict changes | | none; AF05 stays UNKNOWN, pass 0 |

All 20 rows request a battlefield `MANIFESTED` face-down permanent, and all 20 still carry
the `knowledge_state.face_down_look_permissions` -> `knowledge_construction` gap.

## Review P2 fixes (6039789823)

- `probe_row`'s UNKNOWN classification branch is now exercised by a real test:
  `test_an_unknown_readback_reports_its_own_result_not_a_mismatch` drives the full
  `probe_row` pipeline with a fake bridge and a missing `face_down` readback, asserting
  `RESULT_CHECKPOINT_UNKNOWN` (mutant `result = RESULT_CHECKPOINT_MISMATCH` is killed).
- `_states_look_permission` now reads the record's structured
  `knowledge_state.viewer_states[*].face_down_look_permissions` first (the field
  `knowledge_projection` reads) and keeps the free-text construction note only as an
  additional trigger, never the only one. A record phrased "controller may look at
  obj:p1-fd" without the phrase "look permission" still yields the gap; a structured
  permission naming another object does not. The regenerated census confirms 20/20.

## Red/green evidence

Lab, `tests/qualification/test_forge_eb2_face_down.py` (29 cases): on a pristine `origin/main`
tree the E-B2 cases fail and the controls pass (face-up emits nothing, the five
unconstructible kinds stay unsupported, a stated `knowledge_state` look permission stays
unsupported). On the E-B2 tree all 29 pass. The red set covers request emission, strict bool
comparison (1, 0, "true", "false", None, [], {}), missing readback -> UNKNOWN (through
`probe_row`), kind mismatch -> MISMATCH, the structured look-permission gap, and the
wrong-object control.

Forge, `G1R1TurnBeganBootstrapTest`: 7 new tests (4 parse, real-engine no-leak, counters,
post-untap verification); 32/32 pass.

## Forge mutation table (hand-made, `G1R1TurnBeganBootstrapTest`)

| Mutant | Killed by |
|---|---|
| (a) drop `turnFaceDown` | `manifestedFaceDownPlacementIsEngineStateAndNoLeak`, `faceDownPlacementKeepsCounters`, `postUntapVerificationFailsClosedWhenNotFaceDown` (the post-untap verification fails the session closed) |
| (b) drop `setManifested` | the same three (post-untap verification: not manifested) |
| (c) emit `face_down_type` to every observer | `manifestedFaceDownPlacementIsEngineStateAndNoLeak` (p2 readback must carry null) |
| (d) accept an unsupported type | `faceDownParseRejectsMissingOrUnsupportedType` |

## Not done / open

- E-B3: the controller-only look permission (`face_down_look_permissions`).
- Other kinds (CLOAKED, MORPHED, ...), face-down exile, attached face-down: unsupported.
- No row was executed against a real engine; nothing here is runtime qualification.
