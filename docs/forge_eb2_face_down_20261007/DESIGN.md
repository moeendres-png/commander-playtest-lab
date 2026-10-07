# E-B2: face-down construction (Forge bridge + Lab lane)

Status: implemented locally in two repos, **not pushed, not repinned**. Evidence class:
`CODE_DERIVED` plus real-engine unit evidence in the Forge bridge module. No qualification
row was executed, no receipt exists, and no row verdict changed (`UNKNOWN != PASS`).

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

## Forge (`forge-protocol2-bridge`, commit c3a025fa94 on `hardening/forge-eb2-face-down-20261007`)

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
- Look permission is **not** closed: a face-down record object whose `construction_notes`
  grant a look permission adds the hard unsupported dimension
  `knowledge_state.face_down_look_permissions` (mapped to `knowledge_construction`, E-B3).
  `knowledge_state.face_down_look_permissions` in `viewer_states` still yields `knowledge_state`.
- AF05 census (`forge_hidden_information.py`): `face_down_construction` is now `SUPPORTED`
  (fragments from the new Java), `BOOTSTRAP_FIELDS` gains `face_down`, `face_down_type`.
  `forge_residuals.py`: gap text for the remaining face-down kinds.

## Repin dependency (not repinned, by instruction)

`config/rules_engines.json` pins the bridge at `ee37e4a5` (`ASSERTED_BRIDGE_COMMIT` mirrors it).
That blob predates E-B2. Consequences until the Forge commit is pushed and the pin moved:

1. Against the pinned blob, `derive_capability_matrix` raises `ScenarioCapabilityDrift` for
   `battlefield.face_down`, and the AF05 channel assertion `face_down_construction` drifts.
   This is the intended fail-closed state: no row credit before the repin. No unit test reads
   the real blob; the synthetic `_SCENARIO_SOURCE` fixture was updated to carry the fragments.
2. `tests/qualification/test_forge_hidden_information.py::test_the_committed_matrix_is_current`
   is **expected red** until the repin: `docs/forge_af05_hidden_20261003/FORGE_AF05_MATRIX.json`
   cannot be regenerated honestly (its `bridge_commit` and blob ids are the pin's), so it
   still lists the old gaps. Marked with a comment in the test. Not skipped or deleted.
3. At repin: set the pin, `ASSERTED_BRIDGE_COMMIT`, run `scripts/run_forge_hidden_census.py`
   with `--forge-root`, commit the regenerated matrix.
   `scripts/run_forge_residual_census.py` is source-independent and was re-run: no change.

Census computed in scratch against the local commit (`ASSERTED_BRIDGE_COMMIT` patched
in-process only; channel assertions passed on the new source):

| | before (pinned) | after (local commit) |
|---|---|---|
| rows / classification | 20 / 20 PROVIDER_ADAPTER_GAP | 20 / 20 PROVIDER_ADAPTER_GAP |
| `face_down_construction` gaps | 20 | 0 |
| `knowledge_construction` gaps | 12 | 32 (12 + 20 look-permission, E-B3) |
| `library_construction` / `cost_state_construction` | 20 / 14 | 20 / 14 |
| verdict changes | | none; AF05 stays UNKNOWN, pass 0 |

All 20 rows request a battlefield `MANIFESTED` face-down permanent.

## Red/green evidence

Lab, `tests/qualification/test_forge_eb2_face_down.py` (27 cases): on a pristine `origin/main`
tree 20 fail and 7 pass; the 7 are controls that must stay true (face-up emits nothing, the
five unconstructible kinds stay unsupported, a stated `knowledge_state` look permission stays
unsupported). On the E-B2 tree all 27 pass. The red set covers request emission, strict bool
comparison (1, 0, "true", "false", None, [], {}), missing readback -> UNKNOWN, kind
mismatch -> MISMATCH and the look-permission gap staying open.

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
