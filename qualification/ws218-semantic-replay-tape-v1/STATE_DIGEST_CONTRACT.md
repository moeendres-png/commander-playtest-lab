# WS218 STATE_DIGEST_CONTRACT — `semantic-state-digest-1.0.0`

Three distinct digests (never one omniscient hash):
1. `internal_checkpoint_digest` (authoritative evidence): canonical actor
   view + legal fingerprints + seed + calls + turn + offset.
2. `public_state_digest`: turn/phase/step, seats, life/poison/counts,
   battlefield (sorted public permanents), graveyard order (names),
   command (names), stack order (names), commander damage/tax rows. No
   hand, mana, or granted library.
3. `principal_observation_digest`: full canonical actor view with UUIDs
   mapped to seat/occurrence keys; opponent hands/mana structurally absent
   (counts only); granted_library as sorted names window-only.

Canonical view maps `game_id→game`, player UUIDs→`seat:N`, objects→zone/
occurrence projections; battlefield sorted by semantic content; hand names
sorted; stack/graveyard order preserved. Tape artifacts contain zero raw
UUIDs and no hand/mana/granted arrays (verified by scan). Pilot-facing
surfaces return hashes/verdicts only. Unit tests pin cross-process
stability under UUID remapping and public/private separation.

Machine companion: `STATE_DIGEST_CONTRACT.json`.
