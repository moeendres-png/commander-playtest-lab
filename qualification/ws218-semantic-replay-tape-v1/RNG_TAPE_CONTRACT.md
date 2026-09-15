# WS218 RNG_TAPE_CONTRACT

Rules RNG is engine-owned. Tape records `root_rules_seed`,
`rules_seed_explicit=true`, `require_explicit_seed=true` (attribution
model `calls-coordinate-plus-state-transition`), plus per-step
`rng_calls_before/after` observed from live `rules_seed_binding`
(`game.getRulesRandomCalls()` at status time). The pinned engine exposes
no stable per-operation kind tap without an engine change, so per-op
kinds are NOT invented; attribution is calls coordinates plus the
state/event transition they produced. The fresh engine regenerates every
result; recorded results are never injected. Calls mismatch →
`RULES_RNG_CALL_DRIFT`; seed/contract mismatch → `RULES_RNG_RESULT_DRIFT`.
`RandomUtil` is never authoritative (no import in the tape package; bridge
retired it as Rules authority in WS213). Positives show post-start
consumption (2P 196→784, 3P 294→1176, 4P 392→1568, 5P 490→1960).

Machine companion: `RNG_TAPE_CONTRACT.json`.
