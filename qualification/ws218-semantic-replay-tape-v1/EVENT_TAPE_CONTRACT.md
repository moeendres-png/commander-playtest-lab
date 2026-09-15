# WS218 EVENT_TAPE_CONTRACT

Events are decision-offset ranges plus canonical digests, not raw
GameEvent equality (the bridge audit log is lifecycle-only by design).
Per step: `event_offset_before` (authoritative revision),
`event_offset_after`, `event_digest` over sequence/class/actor/selected
prints/numeric/calls before-after/turn before-after/observation/post
(`tape_helpers.event_digest_for_step`). Debug/log strings excluded;
material zone/state/decision transitions bound via observation + post
digests. Consumer recomputes the digest from recorded coordinates and
fails `EVENT_DIGEST_MISMATCH` on divergence. `TAMPER_EVENT` proves it.

Machine companion: `EVENT_TAPE_CONTRACT.json`.
