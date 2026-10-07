# #572 starting-player authority: LOCAL_OBSERVED evidence

`LOCAL_OBSERVED` only. This is **not** PB-03 qualification credit; credit comes
from PB-03 on an exact head plus a sealed epoch. Nothing here selects a provider
or claims Architecture Freeze.

Source lock at capture: branch `opencode/oc572-starting-player-20261006`, head
`e94647c9fb6d76737cf5ec4724c46f366144d8e3` (tree
`ce44364f244e6e6dea6c0f2ede044b2bc0ae580b`), i.e. after the review repair
`8c572e79` (P2/P3 + R3-C1..C5) and the normal merge of `main` `84c17f9d` (the
separated Space Bunny rebind PR #576). Pinned XMage candidate:
`b479fe74fd1eaf899ff16c6a9203e74a91c0f339` (a built local artifact was
installed for this run; the engine reports its own commit at handshake).

This document supersedes the pre-P3-3 capture taken at `976429e3`
(sha256 `ac5c127fddc85c48e8e3eaef9d7fc9f083912eba05c3124fac81e088bed9b1aa`):
the P3-3 repair made the CR 103.2 prompt chooser/chosen identities a required
part of the confirmed channel, so that capture no longer exercises the current
credit rule. It remains historical provenance only.

Raw document (re-captured):
`LOCAL_OBSERVED_STARTING_PLAYER_EVIDENCE.json`
sha256 `6a29c3da15f79e882dcb5e423c2f18cc591d11445dc5464baa24c3898bda44d4`.
The reproducible capture harness is committed beside it:
`capture_starting_player_evidence.py` (records
`provider_prompt_answer_recorded` from the driver's terminal facts).

## Commands

```bash
PYTHONPATH=src python3 .claude/skills/lab-ops/scripts/real_rows.py build
PYTHONPATH=src python3 .claude/skills/lab-ops/scripts/real_rows.py cardinality xmage
PYTHONPATH=src python3 .claude/skills/lab-ops/scripts/real_rows.py pregame xmage
python3 docs/oc572_starting_player_20261006/capture_starting_player_evidence.py
```

## Fix-after: the record's own declaration reaches the engine

`PLAYER_COUNT_2P`, `3P`, `4P` and `5P` (each on its own keyed launch), real
pinned XMage: PASS.

- `declared_starting_seat = p1`,
  `starting_player_declaration.source = RECORD_TEMPORAL_STATE_PRE_FIRST_TURN_ACTIVE_PLAYER`
- `starting_player_provider_acknowledged_seat = 0` (the create request echo; a
  weak fact only)
- `starting_player_provider_confirmed_seat = p1` — the engine's own start_game
  readback, resolved through the engine's seat roster; this is the independent
  confirmation the channel rests on
- `provider_prompt_answer_recorded = true` — the bridge published the chooser
  and chosen identities of the CR 103.2 prompt it actually answered, and all
  three identities resolved to the declared seat (R3-C1/R3-C3); a first-player
  fallback in a pod of 3+ can no longer be mistaken for an answer
- `starting_player_channel = PROVIDER_ENGINE_CONFIRMED_STARTING_SEAT`
- construction proof `CONSTRUCTION_EQUAL`, with
  `temporal_state.active_player` and `temporal_state.priority_player` EQUAL
  (`requested=P1`, `observed=P1`) under that verified channel.

`PILOT_MULLIGAN` (keyed launch), real pinned XMage: PASS.

- same declaration source and channel, provider acknowledgement `0`, engine
  readback `p1`, `provider_prompt_answer_recorded = true`, `CONSTRUCTION_EQUAL`.

The JSON document carries all five runs with their engine-returned fields; the
`real_rows.py` console output independently printed PASS for the same rows.

## Fail-before / fail-closed controls

Same 2P record with the declaration removed (`temporal_state` moved to turn 1,
no active player): **UNKNOWN**, `FAIL_CLOSED_UNSATISFIED`, and the run never
creates a game. The engine would have refused it anyway; the driver states the
reason first:

```
DecisionUnsatisfied: the record declares no starting seat and the XMage create
channel requires an explicit starting_player_seat; the Lab never supplies a
p1/seat-0 default
```

The same refusal is coded at the provider boundary when a caller omits the
field (Java bridge tests):

```
missing_starting_player_seat: CREATE_COMMANDER_GAME requires an explicit
starting_player_seat; the bridge never defaults to seat 0
```

`WS05-CMD-START-2` on the current 1.0.21 record (NATIVE_STATE_LOAD, turn-1
precombat main, `required_events` names `starting_player:P1` but the record
declares no starting seat): **UNKNOWN** with the same missing-authority reason.
Before this change the generic lane answered the p1 default and the row's
construction proof could not establish equality anyway; now the row fails closed
for the authoritative reason. Closing it needs the already-adjudicated contract
1.0.22 natural-start erratum (#441 ruling 6007651998), not a Lab choice.

## What was not run here

- Forge real-engine rows: no local Forge checkout at the pinned bridge source
  `ee37e4a52d99401ba57fba7ca516ac01f1981161`; the Forge column is exercised by
  the PR's PB-03 run. `NOT_RUN` is not PASS.
- PB-03 / sealed epoch: produced by CI on the exact PR head.
- The unit-suite packaging smoke tests fail locally because the ambient
  environment carries `rich 13.9.4` while `requirements/lock.txt` pins 15.0.0;
  the identical failure set reproduces on `origin/main` in a clean detached
  worktree.
