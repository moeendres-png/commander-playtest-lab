# WS224 PROCESS_ISOLATION

At least one representative canary run uses the normal fresh-JVM / production
JSONL boundary (not only in-memory unit serialization) — exceeded:

- BOUNDARY: fresh JVM (`_RawFullGameClient` Popen `... full-game`), 4P Lions,
  seed 424242: 24/24 per-decision hidden-exclusive scans clean across all 4
  actor seats + 3 attacker probes + stderr-tail scan. Evidence:
  `runs/BOUNDARY_4P.json` (22.5s / 5.6s runs observed).
- REPLAY: fresh 35-step 4P tape recorded at this HEAD (`runs/ws224-tape-4p.json`,
  5.8s) + fresh-process replay PASS (5.7s) + fresh-process tamper replay
  failing closed with `ACTOR_MISMATCH`. Evidence: `runs/REPLAY_4P.json`.
- In-JVM matrices (same-JVM sessions, production lane classes): 240 frames
  across 2P–5P. Existing process-isolation proofs (one-game-per-process
  refusal, atomic writes) retained from WS218 without rerun (no bridge change).

No shared mutable engine state across record/replay/boundary. No raw push used.
