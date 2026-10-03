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
2. **Observation.** Each row needs a set of principal-facing channels
   (`required_principal_channels` in the matrix), built in three layers:
   - **Universal surface, on every row.** The shared mandatory verifier
     (`knowledge_projection.verify`) runs one forbidden-identity and sentinel scan for
     every HIDDEN row, whatever its obligation, and its `scan_coverage` check needs
     content on each of its channels. `VERIFIER_CHANNELS` maps every verifier channel
     to the Forge channel that carries it: prompt, context, option ids, labels and
     option, source, ability and pile metadata to `decision_frames`; state to
     `principal_scoped_state`; event to `event_log`; transcript (every document the
     principal receives) to `message_surface`; log to `transport_diagnostics`. So
     every row requires all five (`UNIVERSAL_PRINCIPAL_CHANNELS`).
   - **Obligation channels** (`OBSERVATION_REQUIREMENTS`), layered on top: reveal and
     look audience and projection, library contents, face-down redaction, and the
     replay or transcript export.
   - **Record channels:** a record that places a face-down object makes the shared scan
     forbid its identity to every non-entitled principal, so the row also requires
     `face_down_redaction`.

   Every required channel that is absent or unaudited is listed on the row; none is
   omitted. `test_no_row_omits_a_universal_principal_channel` fails if any row (fresh or
   in the committed matrix) lacks a universal channel, if a verifier channel has no
   mapping, or if the absent and unaudited lists drop a required channel.
   `test_a_re_omitted_universal_channel_is_caught` removes each universal channel in
   turn and shows the control catches it on all 20 rows. Against the earlier
   per-obligation table the control fails with 60 omitted (row, channel) pairs
   (`RED-universal-surface.*`; `GREEN-universal-surface.*` after the repair).

   Every channel is asserted against the pinned bridge source blobs, read with
   `git show <bridge_commit>:<path>`. Matching uses the code only: comments are
   stripped and whitespace is collapsed. `HiddenChannelDrift` is raised when:
   - a blob loses an asserted code fragment;
   - an absent token appears once the asserted fragments are removed;
   - the bootstrap reads a JSON field outside the closed set `BOOTSTRAP_FIELDS`;
   - the bridge dispatches a message type outside the closed set `MESSAGE_CASES`, or
     loses one.

   A channel has one of three statuses. **Supported** and **absent** are decided by the
   source. **Present but unaudited** marks a principal-facing channel that exists but
   whose obligation (a refusal probe, a leak or sentinel scan) is shown only by executing
   the row. The source assertion never stands in for that audit, and an unaudited
   channel alone is not a classification: such a row needs execution.

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
| library contents | absent | every library projects as `[]` with `library_size` only; no other `library*` zone key exists |
| event log | absent | `export_event_log` and `get_event_log` fail closed (`EVENT_LOG_UNSUPPORTED`; `event_log_supported = false`, its only occurrence) |
| reveal and look audience | absent | both `reveal` overrides only call `auditReveal`, whose whole body writes the bridge's internal audit (`session.audit("cards_revealed", ...)`); the controller has no other reveal path, and the state projection carries no revealed or looked-at key (`reveal_look_projection`) |
| replay or transcript | absent | `export_replay` is unsupported and `replay_supported = false` (its only occurrence). The bridge keeps an internal `SemanticReplay` and puts a `principal_observation_digest` in the state, but no replay or transcript is exported to a principal |
| face-down construction | absent | `ScenarioBootstrap` has no face-down field |
| library-order construction | absent | `ScenarioBootstrap` cannot place a library in a requested order |
| knowledge construction | absent | `ScenarioBootstrap` has no knowledge or permission field |
| cost-state construction | absent | `ScenarioBootstrap` has no mid-cast cost or payment field |
| message surface | present, unaudited | the whole request surface is 24 dispatched message types (`MESSAGE_CASES`); an unknown type is refused with `UNKNOWN_MESSAGE`, and the legacy `get_state` alias is the observer-scoped projection. Whether every message refuses an omniscient read, and what errors and diagnostics carry, needs the row's runtime refusal probes and channel scan |
| decision frames | present, unaudited | every key the projection writes into a frame summary, a legal action, its metadata and its object references is the closed set `DECISION_FRAME_KEYS` (48 keys; a new or lost key is drift). The sentinel obligation's facets map onto them (`DECISION_FRAME_FACETS`): prompt and context (`label`, `reason`, `kind`, `frame_kind`; Forge has no separate prompt or context field), option ids (`action_id`, `semantic_key`, `semantic_fingerprint`), labels, metadata, object references, and source (`source_object_id`, built from the source card name). Whether any of them carries a face-down or sentinel identity to a non-entitled principal needs the row's sentinel scan |
| transport diagnostics | present, unaudited | `BridgeMain`, the JSONL process the Lab launches, writes one response per line to stdout and nothing else; a malformed request echoes the parser's message and an internal failure returns a fixed text. Its own stderr diagnostics are the closed set `STDERR_PRINTS`, exception texts and stack traces included, and every engine `System.out` print is redirected to stderr. Engine prints are not bounded by bridge source, so whether stderr carries a hidden identity needs the row's channel scan. **The Lab cannot run that scan yet:** `bridge_launcher` pipes stderr but discards it on close and reads only a 2000-character tail when stdout closes mid-request, so `lab_capture.transport_diagnostics` is a Lab gap on every row, since the shared verifier scans the process log for every row (bound to the launcher source by `LAB_CAPTURE_ASSERTIONS`) |

The four construction channels share one closed set: the bootstrap reads exactly these
JSON fields:
`attached_to`, `battlefield`, `card`, `commander_damage_taken`,
`continuous_effects_present`, `controller`, `counters`, `decision_script`, `hands`,
`id`, `life`, `owner`, `players`, `stack`, `tapped`.

## Per-row matrix

All 20 rows request a face-down permanent and an exact library order, which the
bootstrap cannot construct. Every row's readback also cannot prove the requested library
and exile zones.

Every row carries the universal surface the shared verifier scans, plus face-down
redaction (each record places a face-down object). On every row that means:
- **required:** principal-scoped state, decision frames, event log, message surface,
  transport diagnostics, face-down redaction;
- **absent:** event log;
- **present but unaudited:** decision frames, message surface, transport diagnostics;
- **Lab gap:** stderr capture (`lab_capture.transport_diagnostics`).

The table names what each row needs beyond that.

| Row | Obligation | Other construction gaps | Absent principal channels | Other Lab execution gaps |
|---|---|---|---|---|
| HIDDEN_01 | opponent_hand | none | event log | none |
| HIDDEN_02 | opponent_library | none | event log | none |
| HIDDEN_03 | public_exile | knowledge | event log | none |
| HIDDEN_04 | face_down_controller | knowledge | event log | none |
| HIDDEN_05 | exile_permission_persists | cost state, knowledge | event log | cast, target player, choose object, target object |
| HIDDEN_06 | exile_permission_invalidates | cost state, knowledge | event log | cast, target player, choose object |
| HIDDEN_07 | reveal_audience | cost state, knowledge | event log, reveal/look audience, reveal/look projection | cast |
| HIDDEN_08 | look_audience | cost state, knowledge | event log, reveal/look audience, reveal/look projection | cast, target player |
| HIDDEN_09 | search_inspection | cost state, knowledge | event log, library contents | cast, target object |
| HIDDEN_10 | scry_knowledge | cost state, knowledge | event log, library contents | cast, target player, target objects, choose object |
| HIDDEN_11 | shuffle_invalidates_order | cost state, knowledge | event log, library contents | cast, target player |
| HIDDEN_12 | controlled_player_authority | cost state, knowledge | event log | cast, target player |
| HIDDEN_13 | pile_metadata | cost state, knowledge | event log, library contents | cast, target player, choose objects, pile |
| HIDDEN_14 | target_metadata | cost state | event log | cast, face-down target |
| HIDDEN_15 | source_metadata | cost state | event log | cast, mode, face-down target, yes/no |
| HIDDEN_16 | ability_metadata | cost state | event log | cast, mode, face-down target, yes/no |
| HIDDEN_17 | copy_face_down | cost state | event log | cast, yes/no, face-down choice |
| HIDDEN_18 | transcript_privacy | cost state, knowledge | event log, replay/transcript | cast, target player |
| HIDDEN_19 | no_omniscient_api | none | event log | none |
| HIDDEN_HONEYCARD_SENTINEL | honey_sentinel | none | event log, replay/transcript | none |

## What would move Forge AF05

In dependency order, all outside this Lab workstream:

1. Provider construction: a face-down field with an explicit face-down type, an exact
   top-to-bottom library, knowledge state and mid-cast cost state in `ScenarioBootstrap`
   (a Forge bridge change, which needs its own authorized issue).
2. Provider observation: a principal-scoped event log, a reveal and look audience
   channel, library contents for an entitled principal, and a readback that proves the
   requested library and exile zones.
3. Runtime audit: once a row can be constructed, its refusal probes and its leak and
   sentinel scan over the message surface, the decision frames and the transport
   diagnostics. Every row needs this, because the shared verifier scans that whole
   surface on every row. The Lab must first retain the bridge's stderr.
4. Lab execution: the shared mid-game selector surface on the Forge scenario lane
   (#459) for the scripted decision families.

No row needs only one of these steps:
- The pure projection rows (HIDDEN_01, 02 and 19) need steps 1, 2 and 3. Step 2 is
  needed for the event log and for the library and exile readback.
- HIDDEN_03 and 04 need the same, with knowledge state in step 1.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`
