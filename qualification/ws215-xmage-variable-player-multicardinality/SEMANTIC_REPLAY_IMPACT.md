# WS215 SEMANTIC_REPLAY_IMPACT — PARTIAL (unchanged, cardinality-noted)

WS213 `SEMANTIC_REPLAY_STATUS = PARTIAL` impact-adjudicated against the
cardinality change; WS215 implements no Replay v1:

- Present (unchanged, now per-count): explicit orchestration seed bound
  to the native per-game Rules RNG with `rulesSeedExplicit` +
  `requireExplicitSeed` proof per run; `getRulesRandomCalls` accounting;
  native decision transcript (offsets, classes, seats, prompts, option
  types/labels, selections, numerics) attributing every discretionary
  input — for N = 2..5. Same-seed twins match per count per mode
  (determinism), but twins are NOT equated with semantic replay.
- Still absent (unchanged): checkpoint schema (seed + calls + turn/phase
  + decision offset + state digest), state restore path (would be
  zone/life/ledger injection, forbidden without its own authority),
  shipped replay consumer with semantic comparison, replay validation
  gate, `bit_exact_replay_validated` (false everywhere, honest).
- Cardinality note: a future replay contract must cover variable N
  (seat maps, N-principal observations); nothing in WS215 precludes it,
  nothing in WS215 completes it.
- Injection ban preserved: no checkpoints-as-state-writes anywhere.

A dedicated replay successor remains expected. `FULL107 = NOT_RUN`
(burden unchanged: full behavior matrix gated on qualified setups +
credited pilots, after variable-player session + replay contract).

`GLOBAL_BEHAVIOR_CREDIT_CHANGE (WS215) = 0` — systemic conformance only;
no cardinality test converted to behavior credit.

Machine companion: `SEMANTIC_REPLAY_IMPACT.json`.
