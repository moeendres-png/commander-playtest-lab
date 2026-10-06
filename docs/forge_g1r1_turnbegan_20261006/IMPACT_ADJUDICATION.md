# G1 R1 TurnBegan placement: impact adjudication (C5) and divergence record (C6)

- **Decision implemented:** Coordinator decision G1 on #561 (comment 6005365186), R1 approved with
  conditions C1-C6; R2 denied. The six combat-step rows are out of scope (separate ruling).
- **Bridge source:** `ee37e4a52d99401ba57fba7ca516ac01f1981161` (tree `b26c5936`) ->
  `04892c8749b6684246c81edf58b248f54a7869e1` (tree `9946e894`). Two local commits on `ee37e4a5`:
  `510697fa` (implementation and tests) and `04892c87` (WS216 test driver). `bb0a740d..04892c87`
  touches only `forge-protocol2-bridge/`. **The Forge commits are not pushed**; the successor lock
  (`qualification/forge-bridge-g1r1-turnbegan-20261006/`) holds Test build and iOS as PENDING.
- **Rules-Core authority:** unchanged, `bb0a740d`.
- **Evidence class of every run below:** LOCAL_OBSERVED. It is not credit. Credit requires the pushed
  head, exact-head CI and a sealed PB-03 epoch.
- **Not:** Production Provider selection, Architecture Freeze, a denominator change, a Rules-Core
  change, or a PASS promotion.

## What changed in the bridge

| Condition | Implementation (`forge-protocol2-bridge`) |
|---|---|
| C1 fail closed | `ScenarioBootstrap.TurnBeganPlacement` is registered on the game event bus (`Game.subscribeToEvents`) before the game thread starts. It acts only on `GameEventTurnBegan` with `turnNumber()==1`. Guava's EventBus (`Game.java:95`) swallows subscriber exceptions, so the subscriber catches every `Throwable` and records it with `BridgeSession.recordBootstrapError`. A one-shot latch counts turn-1 runs: a second run is recorded as an error and places nothing. The retained `startGameHook` (`completeInRetainedHook`) throws unless there is no error, exactly one run, a completed placement and turn 1. |
| C2 no fabricated events/state | Permanents are placed **untapped** at TurnBegan. Counters are added once there with `addCounterInternal(..., fireEvents=false, ...)` and are never re-applied. Requested tapped state is applied silently with `setTapped(true)` (`Card.java:4644`) in the retained hook, after the untap step (`completeAfterUntap`). |
| C3 no readiness laundering | Battlefield entries accept a boolean `controlled_since_turn_began`. It is never set. After the untap step it is compared with `!card.isFirstTurnControlled()` (`Card.java:3668`), never `hasSickness()`. A mismatch (an impossible request) throws, so the session fails closed. `battlefield_details` gains the same engine fact as a public readback. Lab: `forge_scenario_lane.py` checkpoint-verifies the field (`MISMATCH` on a different, missing or non-boolean readback). A non-boolean request or a non-battlefield object is `UNSUPPORTED`. |
| C5 hook frame | `PhaseHandler.setupFirstTurn` is unchanged: the hook still runs inside the `givePriorityToPlayer` frame (`PhaseHandler.java:1023-1026`). `_HOOK_ASSERTIONS` were re-derived for `TurnBeganPlacement` / `completeInRetainedHook` / `recordBootstrapError`. New `_SCENARIO_HOOK_ASSERTIONS` bind the latch, the error capture, the exactly-once assertion and the counters/tapped split. A pre-G1 hook-placement bridge is drift (`test_capability_matrix_refuses_the_pre_g1_hook_placement`). Stale rationale updated: the combat-step dimension (lane.py:887 on this head; was :820-835), `temporal_reachable` (:1281; was :1210-1215) and the `ScenarioBootstrap` class documentation (was :22-26). |

Placement point (re-located on `ee37e4a5`): `PhaseHandler.advanceToNextPhase` fires
`GameEventTurnBegan` at `:180`. The readiness loop at `:183-187` clears sickness for the active player's
permanents unless `isStartsGameInPlay()` on turn 0. The placed permanents are not start-in-play
objects, so the active seat's permanents are controlled since the turn began. Every other seat's stay
summoning sick (CR 302.6).

## C5: requalification of the 17 Forge PASS rows

Epoch `ab357d1772c3-8698ff38979c` has 17 Forge PASS rows:

- 12 rows on the Forge ScenarioBootstrap lane:
  - WS05-MP-ELIM-OWNED-3, WS05-MP-ELIM-PRIO-3, WS05-MP-ELIM-5;
  - WS05-CMD-ZONE-GY/EXILE/HAND-YES/NO;
  - WS05-CMD-DMG-SPLIT, WS05-CMD-PARTNER-DMG, WS05-CMD-PARTNER-ZONE.
- 5 rows that never use the bootstrap: PLAYER_COUNT_2P–5P and PILOT_MULLIGAN.

Method:

- **Scenario lane:** the epoch's own producer, `forge_scenario_lane.execute_and_persist` (20 selected
  rows, fresh process per row, seed 424242, max_steps 400), runs at each pin. "Before" is
  `ee37e4a5` with Lab `580d815`. "After" is `04892c87` with Lab `f0b2f43` plus the repin; an earlier
  after-run at `510697fa` gives the same result. Before was run twice to measure the noise floor.
- **Lifecycle and pregame rows:** `full107.run_cardinality` / `scripted_pregame_row` (the
  `real_rows.py cardinality|pregame forge` shape), keyed and unkeyed, before and after.
- **Comparison:** `C5_DIFF_BEFORE_AFTER.txt` and `C5_DIFF_NOISE_FLOOR.txt` are the normalised per-row
  diffs. Volatile request/game/option ids, timestamps and identity blocks are masked. Offered options
  are compared as multisets. Each row line reports the frame sequence (kind, actor, option count) and
  the new readback field.

Raw documents stay in session scratch, with these sha256 digests:

| Document | sha256 |
|---|---|
| before | `93f9eeae…` |
| before2 | `202c3ede…` |
| after@510697fa | `0c7824fd…` |
| after@04892c87 | `a0c7f71f…` |
| lifecycle before | `93a33c42…` |
| lifecycle after@04892c87 | `2dc14277…` |

### Results

| Rows | Before | After | Frames (kind, actor, count) | Offered options (multiset) | Terminal facts / obligation |
|---|---|---|---|---|---|
| 12 scenario PASS rows | EXECUTED_OBLIGATION_OBSERVED; checkpoint EXACT (9) / ALLOWED_VARIANCE (3) | identical | identical sequence in all 12 | identical | identical (semantic events, obligation facts, checkpoint verdicts) |
| PLAYER_COUNT_2P–5P (keyed) | PASS | PASS | n/a | n/a | identical except masked game ids |
| PILOT_MULLIGAN (keyed) | PASS | PASS | n/a | n/a | identical |
| Unkeyed variants, WS05-CMD-MULL-2/4 (non-PASS controls) | UNKNOWN | UNKNOWN | n/a | n/a | identical |
| 8 non-PASS scenario rows in the same producer | unchanged classification | unchanged | identical | identical | identical |

### Every difference, adjudicated

1. **New readback field `battlefield_details[].controlled_since_turn_began`.** It appears in every
   executed scenario row's readback and causal-route snapshots.
   - Adjudication: **intended, additive (C3)**.
   - The values follow CR 302.6 in every row: `true` for the starting seat p1's placed permanents,
     `false` for every other seat's (for example WS05-CMD-ZONE-GY-YES: 8 true / 25 false across
     snapshots).
   - The field is not part of `StateHash` and is not in the orchestration `constructedState` key set,
     so frame hashes and digests are unaffected.
   - It names no card, so the AF05 channel table needs no change beyond the bootstrap field.
2. **Order of offered options inside some frames.** Examples: `Plains [activate_ability]` and
   `Swords to Plowshares [cast_spell]`, and `Mountain [play_land]` and the commander cast.
   - Adjudication: **noise, not a G1 R1 effect**.
   - The same permutations occur between the two identical `ee37e4a5` runs (raw diff); compared as
     multisets, the noise-floor diff has 0 differing leaves.
   - The options a pilot is offered are identical.
3. **Lab classification text and dimensions on non-PASS rows.** Affected: MICRO_COSTS,
   MICRO_REPLACEMENT, WS05-MP-COMBAT-4 and WS05-MP-BLOCK-4.
   - The `semantic_objects.controlled_since_turn_began` UNOBSERVABLE finding is gone (C3), and the
     combat-step detail no longer cites summoning sickness.
   - Adjudication: **intended (C3, C5 rationale update)**.
   - Each of these rows remains UNSUPPORTED_DIMENSION through other dimensions:
     - MICRO_COSTS: `temporal_state.active_player`, `action_cost_state` and decision execution.
     - The combat rows: `combat_state` and `temporal_state.combat_step`.
   - No row changes class, and no PASS is gained.
4. **`neutral_initial_state.battlefield[].controlled_since_turn_began` now forwarded.** This applies
   to MICRO_COSTS, MICRO_REPLACEMENT and WS05-MP-COMBAT-4.
   - Adjudication: **intended (C3)**.
   - These rows are statically UNSUPPORTED and were not executed, so the bridge never verified these
     requests in this run.
   - None of the 12 PASS rows requests a control history.
5. **Residual census (`FORGE_RESIDUAL_MATRIX.json`).** The `controlled_since_turn_began` mechanism
   disappears from the rows that requested it.
   - Adjudication: **intended**.
   - The classification counts are unchanged in kind: CONTRACT 2, LAB 39, PROVIDER 17,
     SCENARIO_LANE_EXECUTABLE 12, pass 0.
6. **Bridge suite, `WS216SeparateProcessTest.testPipeAmount`.**
   - At `510697fa` it failed with "unexpected COMBAT_DECLARE_ATTACKERS for p1 while driving to
     PRIORITY". p1's placed Dire Wolves / Master of the Wild Hunt may now attack on turn 1, so the
     engine asks p1 for an attack declaration that it did not ask for before.
   - Adjudication: **intended engine-visible consequence of R1**. CR 302.6 / CR 508.1a: the active
     player controlled them continuously since the turn began.
   - Fix (test driver only, `04892c87`): the pilot explicitly declines a combat declaration that is
     not the frame kind it drives to ("No attacks"/"No blocks" by label, reachability only, no
     behavioural credit).
   - No production code changed for it.
   - No row in the 17 reaches p1's turn-1 declare-attackers step, so no requalified row shows this
     frame (identical frame sequences above).

Not re-baselined silently: nothing was re-baselined. The historical epoch evidence stays bound to
`ee37e4a5`.

## C6: authority and divergence record

- **Authority:** CR 302.6 (control continuously since the most recent turn began), CR 508.1a (attacker
  eligibility), and CR 103.6a (the earliest point a permanent may be on the battlefield, after
  mulligans). It is applied as in the XMage BEGIN_TURN precedent
  (`docs/af07_final_closure_20261002/PLACEMENT_POINT_ADJUDICATION.md`, Option 2), which also verifies
  `controlled_since_turn_began` and never sets it.
  - Rules-text receipt status is unchanged from that record: CODE_DERIVED plus rule-number citation,
    official-text receipt PENDING_EXTERNAL_FETCH.
- **Divergence from Forge-native behaviour (recorded, accepted by G1):**
  - Forge's own start-in-play path keeps such permanents summoning sick on turn 1:
    `Player.initVariantsZones` sets `setSickness(true)` / `setStartsGameInPlay(true)` (`:2923-2924`),
    and the readiness loop's `getTurn() > 0 || !isStartsGameInPlay()` guard (`PhaseHandler.java:184`)
    keeps them sick.
  - The bootstrap deliberately does not mark its placements `startsGameInPlay`, so the active seat's
    placements become ready under CR 302.6.
  - This is recorded in the `ScenarioBootstrap` class documentation.
- **Event-less mid-turn change (recorded):**
  - The silent post-untap `setTapped(true)` fires no `GameEventCardTapped`. It is a state change with
    no event. It is accepted only within the XMage precedent's setup exception: setup is muted on the
    public tape.
  - Placing the permanent tapped before the untap step would fabricate an untap and its event, which
    is worse.
  - It is never used for anything but the requested initial tapped state.

## Red tests and mutation-kill evidence

Java (`G1R1TurnBeganBootstrapTest`, real engine, 6 tests; `MUTATION_JAVA.txt`):

| Mutant | Result |
|---|---|
| J1 subscriber swallows the exception | killed (exception and latch tests) |
| J2 hook assertion dropped | killed |
| J3 latch check dropped | killed (second run placed, no error) |
| J4 hook `runs != 1` weakened to `> 1` | killed (zero-run case) |
| J5 tapped applied at TurnBegan | killed (a tap/untap event fired) |
| J6 counters re-applied in the hook | killed (4 counters instead of 2) |
| J7 verification uses `hasSickness()` | killed (hasty Raging Goblin) |
| J8 projection uses `hasSickness()` | killed |
| J9 impossible request not failed | killed (both C3 reds) |
| J10 readiness laundered | killed |
| J10b laundered with verification off | killed by the C4(a) readback |
| J11 placement back in the hook | killed |
| J11b old placement point with verification off | killed, including C4(b) |
| J12 bridge enumerates sick attackers | **survived (equivalent)**: the engine's own `validateAttackers` revalidation still excludes the turn-1 cast creature, so the offered options do not change. C4(c) holds through engine authority, not through the bridge enumeration. |

Python (`test_forge_scenario_lane.py`, `MUTATION_PYTHON.txt`): P1–P7 all killed (checkpoint verdict
dropped, truthy readback accepted, dimension back to UNOBSERVABLE, request not forwarded, hook
assertion reverted, latch fragment dropped, non-battlefield request accepted).

## UNKNOWN / open

- Exact-head CI for `04892c87`: **NOT_RUN** (not pushed). The lock test is intentionally red until it
  exists.
- PB-03 epoch at the new pin: **NOT_RUN**. Current Forge standing at `04892c87` stays UNKNOWN until it
  exists.
- C4(c) has no bridge-level mutant that kills it (J12 is equivalent). It is an engine-behaviour
  control.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`
