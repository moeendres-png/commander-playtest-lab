# WS215 HIDDEN_INFO_CARDINALITY — PASS (N principals)

WS213 hidden-info PASS impact-adjudicated against N principals and
re-proven per count (fresh JVMs, production sessions):

- Structural (every frame, every count): only the actor entry carries
  `hand`/`mana_pool`; every other entry carries counts plus public zones
  (battlefield, graveyard, command, stack, commander_status); 0
  violations across all runs (matrix 24 + observations + supplemental).
- Oracle (test-only peeking, never pilot input): native opponent
  hand/library card UUIDs scanned against the serialized actor view —
  **9985 frames checked, 0 violations** across 25 qualification runs
  (2P/3P/4P/5P × neutral/develop/mulligan/commander/terminal paths).
  5 oracle *errors* occurred, all confined to one superseded pre-fix
  debug run (reflection defect, fixed; that run is not evidence).
  Grant-scoped `granted_library` identities excluded only inside the
  live entitlement window (no window arose; exclusion logic present).
- 5P cross-principal: P1 vs P2/P3/P4/P5 scoping checked independently
  every frame the actor rotates (all five seats act in every 5P run);
  opponent hand identities absent for every pair; library
  identities/order absent for every pair.
- Public zones remain public (battlefield/graveyard/command/stack
  present for all seats); option metadata carries no other principal's
  private identities (oracle covers labels/metadata/source/state);
  transcripts/canonicals carry no private state (UUID-scrubbed stable
  rows by construction).
- 4P WS213 hidden evidence (8709 rows/0 violations) retained as
  provenance; WS215 re-proves the property under the generalized
  contract rather than inheriting it.

Machine companion: `HIDDEN_INFO_CARDINALITY.json`.
