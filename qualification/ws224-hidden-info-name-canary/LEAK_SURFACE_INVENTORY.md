# WS224 LEAK_SURFACE_INVENTORY — pilot/replay/error string surfaces (pre-mutation, read-only analysis)

Source lock: `3cdade1dfb16c820465690680b0b0be8af7007ef` (WS218 terminal).
WS220 input: `F-HIDE-02` (UUID oracle is name-blind) + `BATCH2_NOTES.md` C2.
Read-only audit ref `1a6ffcdaa264bb64dbc32c9b32019092fc4a896b` consumed via
`git show` object identity only (no sibling-worktree access).

Boundary model (three tiers, per H-HIDE-01):

- TIER-PILOT: anything an outsider pilot principal can read (observations,
  legal actions, transcripts served to pilots, status/result payloads,
  submission error replies, pilot-facing replay verdicts). Canary names must
  NEVER appear here unless the Rules entitled the actor (grant window, own
  zones, public zones, chosen entitled options).
- TIER-PRIVILEGED: Lab-owned qualification evidence + engine-internal state
  (test-oracle reflection reads, sealed tapes/manifests, engine GameLog,
  JVM stderr). May carry private semantics where contractually necessary
  (decklists for reconstruction, hashes). Never served cross-principal
  during play. A privileged hit is NOT a pilot leak; over-sharing it would be.
- TIER-UNKNOWN: engine-internal GameLog/stderr history contents not proven
  either way from the Lab boundary. Stated honestly as UNKNOWN.

## S01 — Actor observation JSON (`pilot_state` / `actorView`)

- Producer: `XmageFullGameStateRedactor.actorView` (Java).
- Pilot-visible: YES (every pending decision carries `pilot_state`).
- Carries names: actor `hand` names, per-seat `battlefield`/`graveyard`/
  `command` names, `stack` names, `commander_status` names, window-only
  `granted_library` names. Opponent `hand`/`mana_pool` keys structurally
  absent; `library` order/identities absent; `exile` is count-only.
- Canary relevance: PRIMARY. Hidden-exclusive opponent hand/library names
  must be absent from the serialized view every frame, every actor.
- Adjudication: live per-frame hidden-exclusive scan (Java) + synthetic
  `canonical_actor_view` drop test (Python).

## S02 — Legal-action labels

- Producer: `XmageFullGamePlayer` option construction (`objectLabel`,
  ability text, mana text, seat names) via `DecisionController.option`
  (twin-stable `object_id` scrub only).
- Pilot-visible: YES (`legal_options[].label`, projected `actions[].metadata.label`,
  transcript `legal_option_labels` / `selected_option_labels`).
- Carries names: entitled option text (own casts, mana sources, seat names
  for starting-player choice, public targets). Engine alone selects the
  eligible set; adapter only projects.
- Canary relevance: PRIMARY. A hidden-exclusive name in any offered label
  for a non-entitled actor is a leak.
- Adjudication: live per-frame label scan (Java) + fingerprint join tests (Python).

## S03 — Legal-action metadata

- Producer: same as S02 (`objectMetadata`, `abilityMetadata`,
  `sourceMetadata`, pile `cards`, `context`, `source_object`,
  `choices_schema`, `cost`).
- Pilot-visible: YES (`legal_options[].metadata`, `actions[].metadata.xmage_option_metadata`,
  `actions[].metadata.source_object`, schemas, costs).
- Carries names: `name`/`card_name`/`source_name`/`choice`/`cards[].name`
  for entitled options; raw UUID fields (`option_id`, `object_id`,
  `source_object_id`, `ability_original_id`, `card_id`, defender/attacker/
  blocker/mode/player ids) travel here for entitled options only.
- Canary relevance: PRIMARY (WS220's exact gap: metadata could carry a name
  with no UUID, evading the UUID oracle).
- Adjudication: live per-frame metadata serialization scan (Java) +
  generic-fallback UUID-key exclusion test (Python `option_fingerprint`).

## S04 — Target/object projection

- Producer: `objectOptions` (label + metadata per eligible UUID),
  `allowed_target_ids` (UUID-only, target-like classes), `modes`.
- Pilot-visible: YES.
- Carries names: entitled target labels + `metadata.name`; ids are raw UUIDs
  for entitled targets.
- Canary relevance: PRIMARY. Non-entitled hidden names must never be offered
  as targets/choices.
- Adjudication: live scan (Java); occurrence-join ambiguity tests (Python).

## S05 — `decision_requested` transcript event

- Producer: `DecisionController.recordDecisionRequested` (class, actor_seat,
  prompt, public/private refs (hashes), `legal_option_types/labels`).
- Pilot-visible: YES (served in `resultPayload.transcript`; sealed in
  historical `primary.json` `native_transcript`; canonicalized to
  `transcript_canonical.txt`).
- Carries names: prompt text + full offered label list (entitled).
- Canary relevance: PRIMARY. Same rule as S02 over the archived form.
- Adjudication: live transcript slice scan (Java) + historical read-only scan.

## S06 — `decision_accepted` transcript event

- Producer: `recordDecisionAccepted` (class, actor_seat, prompt, selected
  types/labels, numeric).
- Pilot-visible: YES (same distribution as S05).
- Carries names: CHOSEN option labels only (actor-entitled by construction:
  chosen among offered).
- Canary relevance: SECONDARY (chosen == entitled), still scanned to prove no
  unchosen hidden names are recorded.
- Adjudication: live scan (Java) + `semantic_transcript` redaction test (Python).

## S07 — Pilot-state / policy input (`PilotStateView`)

- Producer: `ExternalPilotDecisionPolicy._pilot_state` (Python).
- Pilot-visible: YES (in-process pilot input; principal-scoped by contract).
- Carries names: actor `hand_names`, actor `battlefield_names`, actor
  commander names. Opponents contribute counts/threat only
  (`PilotOpponentView`: player_id, life, threat, board_power, graveyard/
  hand sizes) — NO opponent names by construction.
- Canary relevance: PRIMARY (policy must never receive hidden names).
- Adjudication: synthetic sentinel test (Python) asserting opponent hidden
  names absent from `hand_names`/`battlefield_names`/opponent views while
  actor names remain (no global scrub).

## S08 — Public-state payload

- Producer: `public_state_reference` / `private_actor_state_reference`
  (`"actor-view:" + stateHash`), `public_state_digest`.
- Pilot-visible: YES, but carries HASHES only, never names.
- Adjudication: by construction + hash-shape assertion (no names possible).

## S09 — Status/result payloads

- Producer: `XmageFullGameSession.statusPayload` / `resultPayload`
  (game ids, seats, seed, terminal flags, thread name, decision counts,
  `engine_error_diagnostics`, `failure{type,message}`, seat-mapped
  `outcomes{seat,player_id,life,won,lost,left,can_concede}`,
  `rules_seed_binding`, `turn_number`, transcript, evidence flags).
- Pilot-visible: YES (every Lab-boundary reply).
- Carries names: NONE except via embedded decision/transcript/diagnostics
  (covered S01/S05/S06/S10). Outcomes carry no card names. `player_id`s are
  principal UUIDs (identity, not card data; digests map them to seats).
- Canary relevance: SECONDARY (container). Scanned as serialized whole in
  live tests to catch compositional leaks.
- Adjudication: live whole-payload scan (Java) + fresh-JVM boundary scan (driver).

## S10 — Errors (submission / protocol / engine)

- Producers: `DecisionController.submit` (STALE/actor/membership/numeric),
  `ActionProjection.toDecisionResponse` (actor/type/bounds/membership),
  `JsonlBridge` error envelopes (`code`+`message`, no state),
  Python `FullGameProtocolError`/`FullGameConformanceError` (structural text),
  engine `XMAGE_FULL_GAME_FAILED` (`exception class + safeMessage`),
  `TableEvent.ERROR` diagnostics (`exceptionClass: message [event=...]`).
- Pilot-visible: YES (submission replies; status `failure`; result `failure`).
- Name-echo analysis (code-derived, proven by negative tests):
  - STALE/actor/bounds/type errors echo decision/actor/type strings only.
  - `ILLEGAL_ACTION` echoes the ATTACKER-SUPPLIED `optionId` verbatim. An
    attacker probing with a guessed NAME gets their own guess echoed, not
    hidden data. Errors NEVER list the allowed set, so no oracle.
  - `JsonlBridge` errors carry no decision content.
  - Python policy/conformance errors interpolate seats/counts/versions only.
  - Engine `safeMessage` / table-event diagnostics are the ONE surface that
    could in principle carry engine-composed card text; sampled stderr shows
    log4j warnings only, and live probes assert no hidden names in observed
    `failure`/`engine_error_diagnostics`.
- Canary relevance: PRIMARY (attacker-inducible path).
- Adjudication: live wrong/stale/unknown/illegal probes per count (Java) +
  synthetic error-message scan over all `ReplayDivergence` classes (Python).

## S11 — Rejection diagnostics (historical `negative_controls`)

- Shape: `wrong_actor: REJECTED:...`, `unknown_action: REJECTED:...`,
  `unadvanced: true`. No names by construction.
- Adjudication: live probes re-prove per count; historical values scanned
  read-only for name matches (none expected).

## S12 — Audit/transcript artifacts

- `transcript_canonical.txt` (UUID-scrubbed stable rows), `summary.json`,
  `transcript` arrays in result payloads, WS215 run transcripts.
- Pilot-visible: canonical rows are shared evidence; MUST carry no private
  state by construction (UUID-scrubbed, `pilot_state` dropped).
- Adjudication: live transcript scan (Java) + canonical-row scan (Python/driver).

## S13 — Semantic Replay tape

- Producer: `recorder.record_tape` (fresh JVM, production lane + policy).
- Tiers:
  - PRIVILEGED by design: `game_manifest.decks[].{commander_names,mainboard}`
    (full decklists for reconstruction), `commander_identities`.
  - Pilot-facing semantic content: `initial_checkpoint` digests,
    per-step `{principal_observation_digest, legal_set_digest,
    selected_fingerprints, selected_labels (CHOSEN entitled only),
    numeric value+bounds, rng/turn coordinates, event/post digests}`,
    `terminal_checkpoint` seat-mapped five-field outcomes + digests.
  - NEVER in tape: raw UUIDs, hand/mana/granted arrays, wall-clock, request ids.
- Canary relevance: PRIMARY for pilot-facing fields; manifest decklists are
  EXPECTED_PRIVILEGED (reconstruction necessity, never served to pilots
  mid-game), explicitly NOT classified as leaks.
- Adjudication: tape-structure scan + selected-label entitlement argument +
  digest recomputation (driver); consumer verdict shape test (Python).

## S14 — Semantic Replay tamper/divergence diagnostics

- Producer: `consumer.replay_tape` raising `ReplayDivergence(class, detail)`;
  19 tamper cases sealed in WS218.
- Pilot-facing: YES (pass/steps/seat-outcomes only on success; class/seat/
  revision/calls strings on failure).
- Carries names: NONE by construction (details interpolate seats, revisions,
  counts, digests — verified by scan over all 19 diagnostics).
- Adjudication: rescan all 19 tamper diagnostics for card-name content (driver).

## S15 — Grant/look/search entitlement windows

- Mechanism: `ZONE_FULL_LOOK[game][viewer] -> {owners}`,
  `beginZoneFullLook` before library-zone `request`, `endZoneFullLook` in
  `finally`; `grantedLibraryView` returns owner library cards ONLY inside
  the window, else empty; `lookOwnerFor` keys on first library-zone card.
- Rule: a name visible inside the live entitled window to the entitled viewer
  is NOT a leak; the same name outside the window (or to a non-viewer) IS.
- Adjudication: live window-boundedness assertions (Java: grants only inside
  `choose_object` library frames; empty elsewhere) + windowed digest test
  (Python: granted names digested sorted, never ordered raw).

## S16 — Engine-internal logs

- `GameLog`/history (in-memory engine), JVM stderr/stdout, `XmageAuditEventLog`,
  doctor/probe outputs, cache keys (public-only per H-HIDE-01), structural-lane
  `ReplayDebugger` / `ScenarioFixture.known_library_tops` / `structural hand_names`
  (UNSCOPED by F-HIDE-03 — explicitly NOT pilot surfaces; assurance stays
  XMage-lane-scoped).
- Status: engine-internal GameLog/stderr HISTORY remains UNKNOWN from the Lab
  boundary (sampled fresh stderr carries log4j warnings only; no Lab-boundary
  evidence of a pilot path). Stated honestly; NOT upgraded to PASS. No Forge
  redactor exists (F-HIDE-03; out of scope).
