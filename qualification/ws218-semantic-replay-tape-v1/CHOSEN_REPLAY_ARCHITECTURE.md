# WS218 DESIGN_OPTIONS + CHOSEN_REPLAY_ARCHITECTURE

## Options considered

### A. Python-side tape over the production JSONL lane (CHOSEN)
- Recorder/consumer wrap `_RawFullGameClient` + production
  `ExternalPilotDecisionPolicy` (recorder only). No Java changes, no new
  bridge capability, no state injection, no legality reconstruction.
- Fingerprints/fdigests computed from authoritative frames already offered
  by the Core; UUIDs mapped via live seat/observation joins.
- RNG attribution via live `rules_seed_binding.rules_random_calls`
  coordinates (before/after per step) + state transition; per-op native
  kind tap unavailable without an engine change, so the contract records
  the calls-coordinate model explicitly rather than inventing kinds.
- Concessions as `lifecycle_concede` steps via native
  `get_concede_offer`/`submit_concede` for the exact principal.
- Pros: smallest mutation surface; provider-neutral frame (class string,
  principal seat, revision, fingerprints, numeric bounds); preserves all
  WS215 proofs; fail-closed ambiguity; atomic writes; fresh JVM per
  record/replay. Cons: requires bounded+concede terminals for cheap
  qualification (natural 100-life FFA terminals are far); per-op RNG kinds
  remain coordinates, not native labels (documented, verified by
  call-equality + state-equality).
- Rules-correctness: maximal — Core regenerates everything; Python only
  compares and resubmits CURRENT native ids.

### B. Java-side replay identities + per-decision RNG/state digests in the bridge
- Add `replay_fingerprint`, `rules_random_calls`, state hash to every
  `pendingDecision`; Python compares opaque strings.
- Rejected: larger engine mutation for no semantic gain (Python already
  sees the same authoritative fields); rebuild/requalify burden; risks a
  second identity authority drifting from the Core; still needs Python
  seat-mapping for hidden scoping. Reserved as a future optimization only
  if profiling proves the Python join is a bottleneck (it is not; replay
  needs correctness, not throughput).

### C. Snapshot restore / state-write fast-forward
- Restore zones/life/counters/ledger/stack or inject winner to skip to
  mid-game or terminal.
- REJECTED: forbidden without a separately-authorized native snapshot/
  restore API (not in WS218); violates the checkpoint-as-evidence rule.

### D. Same-seed twin as replay
- Rejected: WS213/WS215 prove twins are determinism evidence, not a replay
  contract (no legal-set compare, no choice resolution, no lock, no
  divergence taxonomy). Kept only as a determinism control.

### E. Forge integration in WS218
- Rejected: out of scope. The frame is kept engine-neutral (string
  classes, seat principals, fingerprint multisets, numeric bounds,
  calls-coordinates) so the WS217 families (`TARGET_SELECTION`,
  `DIVIDED_ALLOCATION`, `NUMBER_CHOICE`, opaque targets, Core-validates)
  can be bound later without weakening XMage correctness.

## Chosen architecture (A)

- Contract versions: tape `semantic-replay-tape/1.0.0`, canonical
  `semantic-canonical-1.0.0`, option identity
  `semantic-option-identity-1.0.0`, state digest
  `semantic-state-digest-1.0.0`.
- Modules: `semantic_replay/canonicalization.py`, `fingerprint.py`,
  `tape.py`, `tape_helpers.py`, `divergence.py`, `source_lock.py`,
  `recorder.py`, `consumer.py`, `capability.py`.
- Recorder: fresh JVM, exact manifest, seed bound pre-start, initial
  checkpoint verify, per-step pilot decision + fingerprint/record + native
  submit + RNG/event/post verify, bounded prefix + native concessions to a
  complete terminal, atomic sealed write, incomplete marker otherwise.
- Consumer: parse/validate, lock verify refuse-before-execution, fresh JVM,
  exact-manifest construction, seed bind, initial verify, per-step
  actor/class/revision/observation/legal-set verify, exactly-one native
  resolution, CURRENT-id submit, RNG/event/post verify, terminal verify;
  0/>1 matches fail; no fuzzy/skip/injection.
- Capability: tape-lane flag false until positives (2P-5P) + tamper matrix
  + hidden/process evidence qualify it; bridge `replay_supported` stays
  false; exporter/twin insufficient.

Machine companion: `CHOSEN_REPLAY_ARCHITECTURE.json`.
