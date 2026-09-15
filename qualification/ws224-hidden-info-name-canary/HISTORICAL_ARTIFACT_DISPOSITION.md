# WS224 HISTORICAL_ARTIFACT_DISPOSITION — quarantine/advisory, no rewrites

Scan: `runs/HISTORICAL_ARTIFACT_SCAN.json` (66 committed `primary.json` +
4 sealed WS218 tapes, read-only; `rewrites = 0`).

## Classifications

- `NO_PRIVATE_NAME_MATCH`: 0 files (every historical transcript carries at
  least some card-shaped offered labels — expected: engines offer real cards).
- `EXPECTED_PRIVILEGED_ARTIFACT`: 4 (WS218 tapes: manifest decklists are
  reconstruction-privileged by design; steps carry digests + entitled chosen
  labels only).
- `POTENTIAL_LEAK_ARTIFACT`: 66 (all historical `primary.json`). The offered
  labels are overwhelmingly actor-own shapes (land/mana plays, own casts,
  mulligan/priority/seat/combat rows; avg ~10 cardish labels/file, max 19)
  but a static read cannot recompute per-event entitlement, so they stay
  advisory — NOT confirmed leaks.
- `CONFIRMED_PILOT_VISIBLE_LEAK`: 0. Zero `hidden_info_violations` in every
  file that carries the UUID-oracle counters.
- `UNKNOWN`: engine-internal GameLog/stderr history (unchanged from WS220).

## Disposition (advisory, history preserved)

1. Historical `native_transcript` / `decision_stream` artifacts are
   ACTOR-MIXED PRIVILEGED evidence: safe for Lab qualification review; MUST
   NOT be served as cross-principal pilot observations (e.g. do not train or
   prompt a seat-N pilot on seat-M's offered labels without per-event actor
   scoping).
2. The entitlement question these files cannot answer statically is discharged
   for the current lane by WS224 live proof: every offered set is
   engine-selected for its actor (240 in-JVM frames + 24 fresh-JVM boundary
   frames, UUID + name dimensions, all ordered pairs at 2P–5P).
3. No file is rewritten, redacted, or deleted. Future lanes that change the
   redactor/projection must rerun the WS224 oracles rather than inherit this
   disposition.
