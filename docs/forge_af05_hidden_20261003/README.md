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
to:
- the canonical Forge bridge commit (`bridge_launcher.canonical_forge_authority`) and
  each source blob id it read;
- the effective contract (`contract_id`, `canonical_bundle_digest`).

`test_the_committed_matrix_is_current` fails if any of these, or a row, goes stale.

## How a row is classified

`commander_lab.qualification.current_boundary.forge_hidden_information`:

1. **Construction.** The record goes through the Forge scenario lane's own model
   (`forge_scenario_lane.model_requested_state`), so there is no second translation. Its
   unsupported dimensions are split into two groups:
   - **provider gaps:** dimensions the pinned bridge has no field for (face-down objects,
     an exact library, knowledge state, mid-cast cost or payment state; the last is the
     lane's own finding, "mid-cast cost/payment state has no bootstrap field");
   - **Lab gaps:** the lane implements no execution for the decision families, although
     the engine offers its own frames.

   A lane finding with no mapping, or a row with no gap at all, raises instead of
   defaulting to a class.
2. **Observation.** Each obligation kind needs a set of principal-facing channels.
   Every channel is asserted against the pinned bridge source blobs, read with
   `git show <bridge_commit>:<path>`. Matching uses the code only: comments are
   stripped and whitespace is collapsed. `HiddenChannelDrift` is raised when:
   - a blob loses an asserted code fragment;
   - an absent token appears once the asserted fragments are removed;
   - the bootstrap reads a JSON field outside the closed set `BOOTSTRAP_FIELDS`.

   So no classification silently survives a source change. The table holds only for
   `ASSERTED_BRIDGE_COMMIT`. If the canonical pin moves, both the runner reason and the
   census raise until the channels are re-asserted.

The runner (`scripts/run_current_boundary_qualification.py`) gives every Forge HIDDEN
row this exact reason, replacing the generic "Protocol-2 state projection" text. Each
row stays UNKNOWN.

## Channels at the pinned bridge

| Channel | Status | Source evidence |
|---|---|---|
| principal-scoped state | supported | `StateProjection.gameState(session, observerPlayerId)` |
| face-down redaction | supported | a face-down card or stack source is named only when both `view.canBeShownTo(observerView)` and `view.canFaceDownBeShownTo(observerView)` hold; otherwise `"<face-down>"` |
| library contents | absent | every library projects as `[]` with `library_size` only; no other `zones.add("library", ...)` exists |
| event log | absent | `export_event_log` and `get_event_log` fail closed (`EVENT_LOG_UNSUPPORTED`; `event_log_supported = false`) |
| reveal and look audience | absent | both `reveal` overrides only call `auditReveal`, whose whole body writes the bridge's internal audit (`session.audit("cards_revealed", ...)`); no other reveal path exists |
| replay or transcript | absent | `export_replay` is unsupported and `replay_supported = false`. The bridge keeps an internal `SemanticReplay` and puts a `principal_observation_digest` in the state, but no replay or transcript is exported to a principal |
| face-down construction | absent | `ScenarioBootstrap` has no face-down field |
| library-order construction | absent | `ScenarioBootstrap` cannot place a library in a requested order |
| knowledge construction | absent | `ScenarioBootstrap` has no knowledge or permission field |
| cost-state construction | absent | `ScenarioBootstrap` has no mid-cast cost or payment field |

The four construction channels share one closed set: the bootstrap reads exactly these
JSON fields:
`attached_to`, `battlefield`, `card`, `commander_damage_taken`,
`continuous_effects_present`, `controller`, `counters`, `decision_script`, `hands`,
`id`, `life`, `owner`, `players`, `stack`, `tapped`.

## Per-row matrix

All 20 rows request a face-down permanent and an exact library order, which the
bootstrap cannot construct. Every row's readback also cannot prove the requested library
and exile zones. The remaining columns name what else each row needs.

| Row | Obligation | Other construction gaps | Absent principal channels | Lab execution gaps |
|---|---|---|---|---|
| HIDDEN_01 | opponent_hand | none | none | none |
| HIDDEN_02 | opponent_library | none | none | none |
| HIDDEN_03 | public_exile | knowledge | none | none |
| HIDDEN_04 | face_down_controller | knowledge | none | none |
| HIDDEN_05 | exile_permission_persists | cost state, knowledge | event log | cast, target player, choose object, target object |
| HIDDEN_06 | exile_permission_invalidates | cost state, knowledge | event log | cast, target player, choose object |
| HIDDEN_07 | reveal_audience | cost state, knowledge | reveal/look audience, event log | cast |
| HIDDEN_08 | look_audience | cost state, knowledge | reveal/look audience, event log | cast, target player |
| HIDDEN_09 | search_inspection | cost state, knowledge | library contents, event log | cast, target object |
| HIDDEN_10 | scry_knowledge | cost state, knowledge | library contents, event log | cast, target player, target objects, choose object |
| HIDDEN_11 | shuffle_invalidates_order | cost state, knowledge | library contents, event log | cast, target player |
| HIDDEN_12 | controlled_player_authority | cost state, knowledge | event log | cast, target player |
| HIDDEN_13 | pile_metadata | cost state, knowledge | library contents, event log | cast, target player, choose objects, pile |
| HIDDEN_14 | target_metadata | cost state | none | cast, face-down target |
| HIDDEN_15 | source_metadata | cost state | none | cast, mode, face-down target, yes/no |
| HIDDEN_16 | ability_metadata | cost state | none | cast, mode, face-down target, yes/no |
| HIDDEN_17 | copy_face_down | cost state | none | cast, yes/no, face-down choice |
| HIDDEN_18 | transcript_privacy | cost state, knowledge | replay/transcript, event log | cast, target player |
| HIDDEN_19 | no_omniscient_api | none | none | none |
| HIDDEN_HONEYCARD_SENTINEL | honey_sentinel | none | event log, replay/transcript | none |

## What would move Forge AF05

In dependency order, all outside this Lab workstream:

1. Provider construction: a face-down field with an explicit face-down type, an exact
   top-to-bottom library, knowledge state and mid-cast cost state in `ScenarioBootstrap`
   (a Forge bridge change, which needs its own authorized issue).
2. Provider observation: a principal-scoped event log, a reveal and look audience
   channel, library contents for an entitled principal, and a readback that proves the
   requested library and exile zones.
3. Lab execution: the shared mid-game selector surface on the Forge scenario lane
   (#459) for the scripted decision families.

No row needs only one of these steps:
- The pure projection rows (HIDDEN_01, 02 and 19) need steps 1 and 2. Step 2 is needed
  for the library and exile readback.
- HIDDEN_03 and 04 need the same, with knowledge state in step 1.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`
