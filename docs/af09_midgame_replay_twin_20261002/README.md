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
| `REPLAY_STATE_HASHES` | public and actor-observation digests are recorded at every decision, and the processes' native object ids are disjoint |
| `RNG_RULES_TAPE` | Rules RNG coordinates (`before`/`after` `rules_random_calls`) are recorded per answer, P1's start-of-game library shuffle is on the tape, and the RNG tape is kept apart from the decision tape |

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

## PB-03 integration

- **Runner.** After the PB-03 ledger, `MIDGAME_REPLAY_TWIN_EXECUTIONS.json` is
  written. Every verified row whose engine-reported build is the candidate commit
  persists a runner-bound positive receipt
  (`receipts/positive/af09-midgame-replay-twin-<row>.json`). A verified row whose
  build is any other commit earns nothing. The runner's own row stays UNKNOWN and
  names this route.
- **Assembler.** A row is credited only through its receipt, with execution mode
  `AF09_MIDGAME_CLEAN_PROCESS_REPLAY_TWIN`. The twin document reaches the AF09 gate
  only when it is bound to all of the following:
  - the fresh XMage column;
  - its engine commit;
  - the assembling runner.
- **Gate.** The AF09 verdict follows `EXPORT_REFUSAL_ADJUDICATION.md`. The
  single-process export refusal stays recorded but no longer blocks a proven twin.

## Local results

The rows were run on the merged AF07 head with pinned XMage `37e4df6c`: **5/5
verified twins**, all adversarial controls detected. The authoritative result is
the exact-head PB-03 run.

## Out of scope

- **Forge.** The replay/RNG rows stay UNKNOWN on Forge. They need the Forge
  scenario lane's decision execution (#459 surface), which does not exist yet.
- **No Rules decisions in the harness.** The twin computes no legality, never
  mutates engine state outside the two recorded request kinds, and decides no
  Rules question.
