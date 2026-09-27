# RNG + Replay Comparison — XMage vs Forge (FINAL-PROVIDER-CDQ-20260927)

## Rules ownership

Rules randomness originates in the Rules Core with explicit seed authority on
both candidates. The harness may control a supported seed/tape interface but
never chooses Rules outcomes manually. No equal-RNG faking, no manual outcome
injection, no harness-as-Rules-engine.

## XMage evidence (reconciled authority `59332671…`)

- Same-seed public semantic replay qualified: 4P seeded run, 4476 decisions,
  semantic match true (engine-local object identifiers excluded by design).
- Per-count replay MATCH in sealed 2/3/4/5P lanes (Isamaru+Plains scope).
- L7 9/9: public/principal views non-oracle; public/private hash separation;
  transcripts omit private actor-state references.
- Rules-seed binding surface (`XmageFullGameRulesSeedBindingTest.java`) +
  replay tape unit suites (supporting only).
- Fixture level (Gate B): RNG_RULES_TAPE, REPLAY_DECISION_TAPE,
  REPLAY_EVENT_TAPE, REPLAY_CLEAN_PROCESS, REPLAY_STATE_HASHES all stay
  UNKNOWN — no N-scoped replay-match rerun exists for those fixtures' exact
  tape/operation scope.
- Readiness: `rules_rng` SUPPORTING; `semantic_replay` TECHNICALLY_CONFORMANT.

## Forge evidence (ingested WSR20, tip `18bba95a…`, re-executed 31/31 in Gate D)

- `RNG_REPLAY_RESULTS.json`: RNG_RULES_TAPE DIRECT (Core-owned MyRandom
  binding, explicit seeds, seed twins 424242/777); REPLAY_DECISION_TAPE,
  REPLAY_EVENT_TAPE, REPLAY_CLEAN_PROCESS (fresh-JVM + fresh-process 2–6P),
  REPLAY_STATE_HASHES all DIRECT; MICRO_RULES_RANDOMNESS TC (channel + hook
  proven; predetermined-HEADS scenario residual named).
- Suites: WS227SemanticReplayTest (9), WS227SeparateProcessTest (fresh JVM),
  WsR15DeterminismTwinTest, WsR16SixPlayer twins, WS233 cardinality/process
  replay + fresh-process, WS202 seed twins, R20 flip-call framing.
- Tamper negatives fail closed (WRONG_ACTOR / STALE_REVISION /
  CHOSEN_OPTION_MISSING / RNG_DRIFT / STATE_DRIFT / EVENT_DRIFT, no mutation).
- Readiness: Forge `rules_rng` TECHNICALLY_CONFORMANT, `semantic_replay` DIRECT.

## Per-fixture record (common set)

For RNG_RULES_TAPE: seed/tape identity, engine binding, random operation,
decision interaction, terminal consequence — XMage UNKNOWN (fixture level),
Forge UNKNOWN (packet absent).

For REPLAY_* fixtures: same decisions + same Rules RNG + same semantic
events + same terminal semantic state required where applicable; engine-local
object identifiers need not match. Forge holds fixture-corresponding DIRECTs;
XMage holds generic same-seed replay (fixture-level UNKNOWN) → those rows are
NON_COMPARABLE (evidence asymmetry). Seed comparability per row is recorded
in `COMMON_FIXTURE_NORMALIZATION.json` (packet `seed_comparable` slots:
Forge seed twins 424242/777; XMage Rules-seed binding + same-seed replay).

## Replay vs construction

Construction/import artifacts alone are not replay evidence (AGENTS.md §5).
Only the qualified same-seed public semantic replay runs above count, and
only at their proven scope — they are not transferred to fixture obligations.
