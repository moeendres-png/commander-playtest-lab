# WS224 surface scans — verdicts with provenance

## OBSERVATION_SCAN — PASS

- Java live (S01): `pilot_state` serialization scanned every frame for hidden
  UUIDs AND hidden-exclusive names: 2P 60/60, 3P 60/60, 4P 60/60, 5P 60/60
  frames clean. Structural negatives (opponent `hand`/`mana_pool` absence)
  re-asserted per frame.
- Fresh-JVM boundary: 24/24 decisions clean over the production JSONL lane
  (all 4 actor seats observed).
- Python synthetic: `canonical_actor_view` + all digests clean for
  `WS224_CANARY_*` sentinels at 2P–5P, including adversarial smuggled-opponent-hand
  input (dropped downstream); actor-public names preserved (no global scrub).

## LEGAL_ACTION_SCAN — PASS

- Java live (S02/S03/S04): pending-decision serialization (`legal_options`
  labels + metadata + context + source_object) and `legalActionsPayload`
  actions serialization scanned every frame, 240/240 clean. Target/object
  projection covered (options are the projection).
- Python synthetic: `option_fingerprint` generic fallback excludes UUID-like
  keys; occurrence-join semantics unchanged (existing unit tests green).

## TRANSCRIPT_SCAN — PASS

- Java live (S05/S06/S12): each transcript event scanned AT BIRTH against its
  own actor's canary set — current request event pre-submit, accepted/failure
  completions post-submit (with actor-seat binding check). 240 frames clean.
  First naive cumulative-history scan failed as predicted by the boundary
  model (other actors' entitled history), was adjudicated as privileged-history
  conflation, and replaced by the at-birth rule — which then passed 4/4.
- Python synthetic: `semantic_transcript` clean for public-only transcripts;
  planted-sentinel detector proven non-blind.
- Historical `native_transcript`s: see HISTORICAL_ARTIFACT_SCAN (read-only,
  advisory disposition; entitlement discharged by the live at-birth proof).

## ERROR_DIAGNOSTIC_SCAN — PASS

- Java live (S10/S11): per-count attacker probes — wrong actor, stale
  decision, ghost option (ILLEGAL_ACTION), ghost UUID target — all REJECTED
  without advancing, messages free of the full hidden-name set (16/16 probes).
- Fresh-JVM boundary: wrong/stale/ghost probes rejected with
  `external_pilot_decision_rejected` envelopes, no hidden-name echo, no advance.
- Python synthetic: all 18 `DivergenceClass` templates + policy/conformance
  structural messages scanned for sentinel surfaces — clean. `ILLEGAL_ACTION`
  echoes only attacker-supplied ids, never the allowed set (no oracle).

## GRANT_WINDOW_SCAN — PASS-BOUNDED

- 264 live frames (240 Java + 24 boundary): zero non-empty `granted_library`
  outside `choose_object` library decisions. No live window arose under neutral
  play (same bound as WS213/WS215: exclusion logic present, window-live path
  not exercised live). Window-live digest rule (sorted names, never raw order)
  covered synthetically. Honest bound stated; not upgraded.

## REPLAY_TAPE_SCAN — PASS

- Fresh WS224 4P tape (35 steps, recorded at this HEAD): steps carry digests +
  entitled chosen labels only; structural scan asserts no `hand`/`mana_pool`/
  `granted_library` arrays, no raw UUIDs in steps.
- Sealed WS218 2P–5P tapes rescanned structurally (same assertions) — clean.
- Manifest decklists classified EXPECTED_PRIVILEGED (reconstruction
  necessity, never pilot-served mid-game). Tape contract UNCHANGED.

## REPLAY_ERROR_SCAN — PASS

- Fresh tamper (actor-principal swap) on the WS224 4P tape fails closed with
  `ACTOR_MISMATCH`; diagnostic carries seats/revisions only — no deck names.
- All 18 divergence templates + consumer detail sites audited: details
  interpolate seats/revisions/counts/digests/outcome numbers only. The single
  engine-text-bearing diagnostic (`EARLY_TERMINATION` with `failure` JSON)
  was clean in all live runs (no engine failures observed).
- Pilot-facing verdict shape is pass/steps/seat-outcomes only (asserted live).
