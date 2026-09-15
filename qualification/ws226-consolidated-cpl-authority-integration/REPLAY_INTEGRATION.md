# WS226 REPLAY_INTEGRATION — WS218 semantic replay survives

Preserved byte-exact from the WS223 base; no sibling modifies replay sources
(verified: WS221/WS222/WS224/WS225 deltas contain no `semantic_replay/` or
`ws218` paths except WS225's historical pointer).

- Sources: `src/commander_lab/semantic_replay/*` (10 files: tape, recorder,
  consumer, canonicalization, capability, divergence, fingerprint, source_lock,
  tape_helpers) + `RNG contract` + sealed source lock companions.
- Evidence: `qualification/ws218-semantic-replay-tape-v1/*` (contracts:
  EVENT_TAPE/RNG_TAPE/STATE_DIGEST/SEMANTIC_OPTION_IDENTITY/CHECKPOINT/
  CANONICALIZATION; POSITIVE_REPLAY 2–5P dual-replay; TAMPER_MATRIX 19 cases;
  HIDDEN_INFORMATION_REPLAY; WS220 R1–R12 impact; runs/REPLAY_2P–5P +
  tapes/ws218-tape-2p–5p; ws218_driver.py).
- Guards: `tests/unit/test_semantic_replay_tape.py` (unit + integration) +
  WS223 `CARDINALITY_4P_REPLAY_GATE.json` (replay-gated 4P smoke).
- Standing: AF09 PASS (tape lane 2P–5P; campaign-scale replay stays with G14
  NOT_APPLICABLE). WS218 AF09 replay remains PASS in WS226 recompute.

No replay semantic change; deterministic semantic replay still from recorded
seeds + authoritative Decision Options.
