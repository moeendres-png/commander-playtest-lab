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
| `RNG_RULES_TAPE` | every Rules-RNG operation is taped with the randomness it consumed (`before` < `after`) and its result digest; P1's own library shuffle is taped; a different seed in a third fresh process changes P1's result (live control); the RNG tape stays separate from the decision tape |

Two further properties are required of every row:

- the record's own scenario obligation is verified by the generic production
  executor (`midgame_rows.execute_row`);
- the clean-process twin is verified, with all adversarial controls detected.

## Scenario

All five rows share one scenario. P1 casts Burn Down the House and chooses the
Devil mode, and three Devil tokens enter. The start-of-game library shuffle
(CR 103.2) is the Rules RNG operation.

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
  records the engine's live `rules_random_calls`, which come from an
  orchestration-scoped `get_midgame_state` read. Every accepted state-changing
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

The engine reports each library shuffle it performs through a new orchestration
channel, `get_rules_rng_tape`. The channel carries digests only, never card
identities or native ids, and no principal receives it. For each shuffle it
reports:

- the seat;
- the `rules_random_calls` before and after the shuffle;
- a digest of the permutation the shuffle left the library in, relative to the
  deck's own first-seen order.

The same seed reproduces that digest in every process. A different seed changes
it; `XmageRulesRngResultTapeTest` pins this, and the live seed control rechecks it
for every `RNG_RULES_TAPE` run.

The same channel reports a **privileged state digest**: every player's zones in
seating order, the library order included, written as process-independent tokens:

- a requested object's semantic id;
- a deck card's first-seen position;
- otherwise the object's name.

The twin records this digest at every decision and at the terminal.

The record's native step `rules-shuffle` (`NATIVE_RULES_RNG_SHUFFLE_DECLARED_LIBRARY`)
names a shuffle after resolution, but nothing in the scenario causes one, and a
shuffle ordered by the harness would be state the Rules Core never caused. The
1.0.19 erratum therefore declares the step realized by the engine's own
start-of-game shuffle of P1's library (CR 103.2). That shuffle is the record's
`NATIVE_LIBRARY_SHUFFLE` channel and its required event
`rules_rng:library_shuffle:P1`. The erratum states the substitution explicitly
(`rules_rng_procedure`, `native_procedure_step_realized_by`). Its generator is
`generate_contract_1_0_19.py`.

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
- **A harness refusal is never a FAIL.** An ambiguous fingerprint or a missing
  observation stays unexecuted.

## Departures from the Phase 1 contract

- **Checkpoint digests.** The public and actor digests are the qualified WS218
  digests, which the Lab computes from the decider's `pilot_state`; a frame
  without one fails closed. The privileged digest is computed engine-side.
- **Checkpoint placement.** Checkpoints are taken at every decision and at the
  terminal. There is no separate initial or post-answer checkpoint: the next
  decision's checkpoint is the post-answer state.
- **Game id.** The game id is deliberately the same in both processes. Decision
  ids and native object ids differ.

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
