# #458 Forge AF05 hidden information: current-boundary classification

Workstream `FORGE-AF05-HIDDEN-INFORMATION-CAMPAIGN-20261003` (parent #255). Forge is
measured against the same 20 mandatory AF05 HIDDEN rows as XMage
(`knowledge_projection.ROWS`), under the same privacy standard. Forge itself is not
modified, and no second Lab permission model or scenario translator is added.

**Result: 20 / 20 `PROVIDER_ADAPTER_GAP`. Forge AF05 stays UNKNOWN.** A provider that
cannot construct or expose a row's state has demonstrated no leak, so the verdict is
not FAIL. A classified row has executed nothing, so it is not PASS either. No receipt
exists, and nothing promotes credit.

`FORGE_AF05_MATRIX.json` is written by `scripts/run_forge_hidden_census.py`. It is bound
to the canonical Forge bridge commit (`bridge_launcher.canonical_forge_authority`) and
to the effective contract (`contract_id`, `canonical_bundle_digest`).

## How a row is classified

`commander_lab.qualification.current_boundary.forge_hidden_information`:

1. **Construction.** The record goes through the Forge scenario lane's own model
   (`forge_scenario_lane.model_requested_state`), so there is no second translation. Its
   unsupported dimensions are split into two groups:
   - **provider gaps:** dimensions the pinned bridge has no field for (face-down objects,
     an exact library, knowledge state);
   - **Lab gaps:** the lane implements no execution for the decision families or cost
     state, although the engine offers its own frames.
2. **Observation.** Each obligation kind needs a set of principal-facing channels.
   Every channel is asserted against the pinned bridge source blobs, read with
   `git show <bridge_commit>:<path>`. A blob that loses an asserted fragment, or a
   bootstrap that gains a construction field, raises `HiddenChannelDrift`, so no
   classification silently survives a source change.

The runner (`scripts/run_current_boundary_qualification.py`) gives every Forge HIDDEN
row this exact reason, replacing the generic "Protocol-2 state projection" text. Each
row stays UNKNOWN.

## Channels at the pinned bridge

| Channel | Status | Source evidence |
|---|---|---|
| principal-scoped state | supported | `StateProjection.gameState(session, observerPlayerId)` |
| face-down redaction | supported | `CardView.canBeShownTo` gates every face-down name |
| library contents | absent | every library projects as `[]` with `library_size` only |
| event log | absent | `export_event_log` and `get_event_log` fail closed (`EVENT_LOG_UNSUPPORTED`; `event_log_supported = false`) |
| reveal and look audience | absent | reveals and looks reach only the bridge's internal audit (`session.audit("cards_revealed", ...)`) |
| replay or transcript | absent | `export_replay` is unsupported |
| face-down construction | absent | `ScenarioBootstrap` has no face-down field |
| library-order construction | absent | `ScenarioBootstrap` cannot place a library in a requested order |
| knowledge construction | absent | `ScenarioBootstrap` has no knowledge or permission field |

## Per-row matrix

All 20 rows request a face-down permanent and an exact library order, which the
bootstrap cannot construct. The remaining columns name what each row would need next.

| Row | Obligation | Absent principal channels | Lab execution gaps |
|---|---|---|---|
| HIDDEN_01 | opponent_hand | none | none |
| HIDDEN_02 | opponent_library | none | none |
| HIDDEN_03 | public_exile | none | none |
| HIDDEN_04 | face_down_controller | none | none |
| HIDDEN_05 | exile_permission_persists | event log | cast, targets, choose object, cost |
| HIDDEN_06 | exile_permission_invalidates | event log | cast, target, choose object, cost |
| HIDDEN_07 | reveal_audience | reveal/look audience, event log | cast, cost |
| HIDDEN_08 | look_audience | reveal/look audience, event log | cast, target, cost |
| HIDDEN_09 | search_inspection | library contents, event log | cast, target, cost |
| HIDDEN_10 | scry_knowledge | library contents, event log | cast, targets, choose object, cost |
| HIDDEN_11 | shuffle_invalidates_order | library contents, event log | cast, target, cost |
| HIDDEN_12 | controlled_player_authority | event log | cast, target, cost |
| HIDDEN_13 | pile_metadata | library contents, event log | cast, target, choose objects, pile, cost |
| HIDDEN_14 | target_metadata | none | cast, face-down target, cost |
| HIDDEN_15 | source_metadata | none | cast, mode, face-down target, yes/no, cost |
| HIDDEN_16 | ability_metadata | none | cast, mode, face-down target, yes/no, cost |
| HIDDEN_17 | copy_face_down | none | cast, yes/no, face-down choice, cost |
| HIDDEN_18 | transcript_privacy | replay/transcript, event log | cast, target, cost |
| HIDDEN_19 | no_omniscient_api | none | none |
| HIDDEN_HONEYCARD_SENTINEL | honey_sentinel | event log, replay/transcript | none |

HIDDEN_03 to HIDDEN_13 and HIDDEN_18 also request knowledge state, which the
bootstrap cannot construct.

## What would move Forge AF05

In dependency order, all outside this Lab workstream:

1. Provider construction: a face-down field with an explicit face-down type, an exact
   top-to-bottom library, and knowledge state in `ScenarioBootstrap` (a Forge bridge
   change, which needs its own authorized issue).
2. Provider observation: a principal-scoped event log, a reveal and look audience
   channel, and library contents for an entitled principal.
3. Lab execution: the shared mid-game selector surface on the Forge scenario lane
   (#459) for the scripted decision families.

The pure projection rows (HIDDEN_01–04, HIDDEN_19) need only step 1.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`
