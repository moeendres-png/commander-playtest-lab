# WS218 TAPE_SCHEMA — `semantic-replay-tape/1.0.0`

Strict (`extra=forbid`) pydantic schema in
`src/commander_lab/semantic_replay/tape.py`. Top-level: `schema_version`,
`tape_id` (SHA-256 over canonical manifest + initial + steps),
`source_lock`, `game_manifest` (format `commander-ffa`, N=2..5, seats,
decks, commanders, life, starting/mulligan contracts, seed, pilot
derivation, isolation), `rng_contract` (root seed + explicit/require +
calls-coordinate model), `initial_checkpoint`, ordered `steps`
(dense 1..N; decision revisions strictly increasing for decision steps),
`terminal_checkpoint` (terminal true, turn, calls, seat-mapped outcomes,
digests), `seal` (canonicalization/identity/state versions + schema +
terminal digest).

Steps: `sequence`, `step_kind` (`decision`|`lifecycle_concede`),
`decision_class`, `actor_principal` 1..N, `decision_revision`
(authoritative offset), observation/legal digests + legal size, selected
fingerprints + redacted labels, numeric value+bounds where authorized,
RNG calls before/after, event offsets + digest, post digest. Numeric
coherence validated (bounds together; choice within bounds). No
timestamps, no wall-clock, no raw UUIDs, no state-write fields, no outcome
injection fields exist in the schema.

Machine companion: `TAPE_SCHEMA.json`.
