# Phase 7 Closeout — P2 Process-Isolation Audit (audit-first, no edit)

Verdict: **ALREADY_IMPLEMENTED_VERIFIED** — no code change (no second batch
runner, no new machinery).

## Requirement → current-bytes evidence

- One isolated engine process/JVM per game: Python `full_game.py` runner
  spawns one bridge subprocess per run (`close()` dispositions:
  graceful/unacked/forced-kill/already-exited); Java side isolates per
  `Game` instance + session thread.
- No cross-game Rules-state leakage: `restoredStateIsDeterministicAcrossRuns`
  (two sequential games, identical constructed digests) + 10-game terminal
  batch lineage (PR #240) + `test_variant_hash_cross_process` green.
- Deterministic run identity: `run_key` sha256 (`FullGameBatchRecord` pattern
  `^[0-9a-f]{64}$`); resume/skip semantics preserve it.
- Clean child shutdown: `tests/unit/test_full_game_shutdown.py` green (17/17
  with variant-hash + protocol contract in the same run just executed).
- Crash/timeout classification: `FullGameFailureClass`
  (configuration/protocol/conformance/engine); bridge timeouts →
  `FullGameProtocolError` with stderr tail; batch loop continues past
  failures (one failed game cannot corrupt others — structured per-case
  records).
- Artifact isolation: per-batch output directory, per-`run_key` record files.
- Reproducible seed binding: `rules_seed_binding` in every session payload
  (explicit seed, match flags, call counts).
- Secret/private-state-safe diagnostics: error paths carry typed codes +
  engine UUIDs (never card names/hand contents); pilot views stay
  principal-scoped (Phase 1 honeycard + Phase 3 hidden suites green).

## Rerun (current bytes)

`test_full_game_shutdown.py` + `test_variant_hash_cross_process.py` +
`test_phase85_protocol.py`: 17/17 green. No gap found; nothing implemented.
