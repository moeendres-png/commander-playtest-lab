# AF09 Phase 2: clean-process replay twins of the replay/RNG rows (2026-10-02)

Workstream: `AF09-CLEAN-PROCESS-REPLAY-TWINS-20261001` (#454, PR #461, parent #255).
`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

Phase 1 (`docs/af09_replay_twins_20261001/`) qualified the twin contract on full
games. Phase 2 applies the same contract to the five replay/RNG rows of the
107-row provider denominator, on the production midgame lane, inside the PB-03
current-boundary chain.

## The rows

| Row | Its own property, read off the twin's tapes |
|---|---|
| `REPLAY_CLEAN_PROCESS` | the replay process consumed only the record's external input stream and finished without failing closed |
| `REPLAY_DECISION_TAPE` | every taped answer carries semantic selection fingerprints, and the mode choice is taped |
| `REPLAY_EVENT_TAPE` | the canonical event tape records the three Devil tokens and holds no native id |
| `REPLAY_STATE_HASHES` | public, actor and privileged digests are recorded at every decision and at the terminal, and the processes' native object ids are disjoint |
| `RNG_RULES_TAPE` | every Rules-RNG operation is taped with the randomness it consumed (`before` < `after`) and its result digest, and the taped operations account for every Rules random call; P1's own library shuffle is taped; in a third fresh process a different seed changes P1's result **and the game state** (live control). **Not creditable from this scenario**: see below |

Two further properties are required of every row:

- the record's own scenario obligation is verified by the generic production
  executor (`midgame_rows.execute_row`);
- the clean-process twin is verified, with all adversarial controls detected.

## Scenario

All five rows share one scenario. P1 casts Burn Down the House and chooses the
Devil mode, and three Devil tokens enter. The record's required RNG event
`rules_rng:library_shuffle:P1` is the engine's start-of-game shuffle of P1's
library (CR 103.2).

Successor contract **1.0.19** adds the SLOT-04 lossless library errata these rows
need. The records named seven of P1's library cards without declaring a complete
library, so SLOT-04 L7 refused them on every candidate. The errata declare:

- complete checkpoint hands;
- P1's complete library: the seven named cards on top, then 91 template
  Mountains.

The obligation digest is unchanged.

## Record and replay

`src/commander_lab/qualification/current_boundary/midgame_replay_twin.py`:

- **Record, process A.** The row's decision script runs on the generic executor.
  The taping client records each distinct engine decision once. With it, it
  records the engine's Rules-RNG coordinate, results and privileged state digest
  from the orchestration channel described below. Every accepted state-changing
  request becomes the external input stream: decision answers and arrival
  completions. Each answer is identified by its WS218 fingerprint plus the
  record semantic ids of the objects it names. Without that occurrence identity,
  five identical Mountains would collide.
- **Replay, process B, a fresh JVM.** The same record and seed are constructed
  again, and the input stream is re-issued from the tape alone. Each recorded
  fingerprint must match exactly one offered option. Zero matches or several fail
  closed (`CHOSEN_OPTION_AMBIGUOUS`); the replay never takes a first match. A
  diverging frame is never answered.
- **Comparison.** `replay_twins.compare_twin_runs` compares the two runs, and the
  mandatory adversarial controls run against them. Process-local identifiers (the
  game id, decision ids and native object ids) are recorded and never compared.

## The Rules RNG and its results

The engine reports each library shuffle it performs through an orchestration
channel, `get_rules_rng_tape`. For each shuffle it reports:

- the seat;
- the `rules_random_calls` before and after the shuffle;
- a digest of the permutation the shuffle applied, relative to the library's
  order immediately before it.

That permutation depends only on the Rules RNG and the library size. The same
seed reproduces it in every process, and a different seed changes it.
`XmageRulesRngResultTapeTest` pins both, and the live seed control rechecks them.

**The channel is not an observation.** The bridge refuses it on every launch that
does not carry an orchestration key (`COMMANDER_LAB_ORCHESTRATION_KEY`), and its
capabilities declare `orchestration_channel_enabled`. A launch cannot inherit the
key: both canonical spawn paths, `bridge_launcher.launch` and
`MidgameLaneClient`, strip it from the parent environment before applying the
launch's own overrides, and only the replay twin's launch sets one. A malformed
key disables the channel; it never crashes a game.

AF05's omniscience probes include the message. They require the refusal reason
`ORCHESTRATION_CHANNEL_NOT_ENABLED`; a refusal because the engine was busy counts
as a leak. Each twin generates one random key and
gives it to its own record, replay and control processes only. Every digest is an
HMAC under that key, so nobody without the key can read a hidden order out of a
digest or test a guess against it. The engine reports `engine_state` and answers with digests only while it is
parked on a decision, or after a clean game over (no failure, no engine error).
It rechecks that state after computing the digest. A running or failed engine
yields no digest.

The same channel reports a **privileged state digest**: every player's zones in
seating order, including library order, damage, counters, tapped, face-down and
phasing state and attachments, plus the command zone, the stack and the turn
position. Each object is written as its requested semantic id, otherwise its true
name. Two cards of the same name that the record does not name are the same state:
the restoration's game-load seam fills a requested template run with any of them.
(The first live run showed it: deck-position tokens made two otherwise identical
processes differ at the checkpoint seam.) The twin records this digest at every
decision and at the terminal.

### Why `RNG_RULES_TAPE` stays UNKNOWN

The record's native step `rules-shuffle` (`NATIVE_RULES_RNG_SHUFFLE_DECLARED_LIBRARY`)
names a shuffle of the declared library after the cast resolves. Nothing in the
scenario causes one, and a shuffle ordered by the harness would be state the Rules
Core never caused, so **the step is not executed**. The 1.0.19 erratum says so
(`rules_rng_procedure`, `native_procedure_step_not_executed`). Its generator is
`generate_contract_1_0_19.py`.

The shuffle the scenario does contain is the start-of-game shuffle. It reorders
identical scaffolding cards, which the checkpoint's complete library then
replaces, so its result has no Rules consequence.

The live seed control measures this. A third fresh process replays the record's
own taped inputs under seed + 1. The different seed counts as having a Rules
consequence only if one of these happens:
- the engine offers a different frame for those inputs;
- the replay reaches a different end state (privileged digest).

A difference the restoration erases changes neither, while any Rules-caused
shuffle in the obligation would show. Here the result changes but the game does
not (`rng_result_has_state_consequence` is false). The result is taped, replayed
and compared, but it is no Rules RNG evidence. `RNG_RULES_TAPE` therefore stays
UNKNOWN with that exact blocker.

A scenario in which a Rules-caused shuffle of distinguishable cards occurs is an
obligation-adjacent erratum and needs Coordinator adjudication (#255). Until then,
AF09 XMage cannot reach PASS: the midgame twin reaches the gate only when all five
rows verified.

## Independence and failure classification

- **Each terminal is its process's own:** its observation digest and its privileged
  state digest. The record's evaluated terminal facts stay in its execution
  document and are never part of the compared terminal.
- **A demonstrated replay violation is a FAIL.** The engine either offered a
  different frame for the same inputs, or a semantic tape compared unequal. Both
  conditions must hold:
  - the record's obligation was verified;
  - every identity and precondition check passed: build, source, fixture, seed
    acknowledgement, and distinct observed processes.

  The finding is bound to the commit and the runner. The assembler records it as
  a FAIL row, the same way AF05 records a demonstrated leak.
  A frame divergence at the very first input counts too: only the record's own
  sections must be complete.
- **A harness refusal is never a FAIL.** None of these stays anything but
  unexecuted:
  - an ambiguous fingerprint or a missing observation;
  - a replay stopped by an engine failure or a timeout (the engine reports no clean
    game over);
  - a run whose identity or precondition checks failed.

## Departures from the Phase 1 contract

- **Checkpoint digests.** The public and actor digests are the qualified WS218
  digests, which the Lab computes from the decider's `pilot_state`; a frame
  without one fails closed. The privileged digest is computed engine-side.
- **Checkpoint placement.** Checkpoints are taken at every decision and at the
  terminal. There is no separate initial or post-answer checkpoint: the next
  decision's checkpoint is the post-answer state.
- **Game id.** The game id is deliberately the same in both processes. Decision
  ids and native object ids differ.
- **Taped operations.** Only library shuffles are taped as RNG operations. A run
  in which any other Rules random call happened (a coin flip, a random discard)
  fails `rng_operations_account_for_all_calls` and stays UNKNOWN.

## PB-03 integration

- **Runner.** After the PB-03 ledger, `MIDGAME_REPLAY_TWIN_EXECUTIONS.json` is
  written. Every verified row whose engine-reported build is the candidate commit
  persists a runner-bound positive receipt
  (`receipts/positive/af09-midgame-replay-twin-<row>.json`). A verified row whose
  build is any other commit earns nothing. Every earlier replay-twin receipt is
  removed before a run. The runner's own row stays UNKNOWN and names this route.
- **Assembler.** A row is credited only through its receipt, with execution mode
  `AF09_MIDGAME_CLEAN_PROCESS_REPLAY_TWIN`. The receipt's digest must be the one
  this epoch's document recorded for that row, and that document must declare all
  five rows. A demonstrated violation is recorded as a FAIL row. The twin document
  reaches the AF09 gate only when all of the following hold:
  - it is bound to the fresh XMage column, its engine commit and the assembling
    runner;
  - all five rows verified;
  - the twin is one of those rows' own twins.
- **Gate.** The AF09 verdict follows `EXPORT_REFUSAL_ADJUDICATION.md`. The
  single-process export refusal stays recorded but no longer blocks a proven twin.

## Local results

The rows were run on the merged AF07 head with pinned XMage `37e4df6c`. The local
run is diagnostic and persists no evidence; the authoritative result is the
exact-head PB-03 run and its packet.

## Out of scope

- **Forge.** The replay/RNG rows stay UNKNOWN on Forge. They need the Forge
  scenario lane's decision execution (#459 surface), which does not exist yet.
- **No Rules decisions in the harness.** The twin computes no legality, never
  mutates engine state outside the two recorded request kinds, and decides no
  Rules question.
