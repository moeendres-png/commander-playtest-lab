# WS232 Process Isolation Plan

## Rule

One certified game = one fresh OS process = one fresh JVM. The bridge
enforces this mechanically: `XmageFullGameJsonlBridge.createFullGame`
refuses a second game in the same process (`full_game_process_already_used`).
Every WS232 run (record, replay, card/micro/smoke cell) opens its own
`_RawFullGameClient` (fresh `subprocess.Popen(java -jar ... full-game)`)
and closes it (clean `shutdown_engine`, 5s grace, then kill). No game state
can cross a process boundary: per-bridge `session`/`deckImporter` are
instance fields; only stateless static helpers exist; the single
`ThreadLocal` in `XmageFullGamePlayer` is per-player inside one game.

## Identity and seed discipline

- Explicit seed per game (`seed_required` at creation; `setRulesSeed` +
  `setRequireExplicitSeed(true)` before any Rules-random consumption).
- `starting_player_seat = seed % N`; deck handles distinct per seat;
  deck/pilot/seat coverage exactly 1..N (runner validates, engine revalidates).
- Rules RNG provenance per game: `rules_seed_binding` (`rules_random_calls`
  from `game.getRulesRandomCalls()`); pilot stochasticity derived separately
  (`sha256(scenario_seed:seat:offset:class)`), never fed back as Rules RNG.
- UUIDs are per-process (fresh identities per game by construction);
  artifacts persist seats (1..N), never UUIDs, hands, libraries, labels,
  prompts, or metadata contents.

## Grouping (dedup) rationale

One execution may certify multiple declared rows ONLY when it is the exact
same run and each row's criterion is independently evaluated against that
run's log:

- one symmetric Lions game at N certifies several MICRO cells at N (each
  mechanism independently observed in the public log);
- one symmetric card-X game at N certifies exactly one ACTUAL_CARD cell
  (X, N) — no cross-card credit;
- one record certifies RNG/tape cells at N; each independent replay is its
  own fresh process with its own verdict.

Failure attribution stays exact: every certified cell points at the exact
run record (run_id); a crashed/timed-out run certifies nothing (NOT_RUN or
UNKNOWN with cause, never PASS).

## Forbidden

- No shared JVM across certified cells. No in-process "reset" claims.
- No state injection, no outcome injection, no requested-option filtering.
- Timeout/crash != PASS.
