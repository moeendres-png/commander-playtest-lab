# G1 R1 TurnBegan placement: impact adjudication (C5) and divergence record (C6)

- **Decision implemented:** Coordinator decision G1 on #561 (comment 6005365186), R1 approved with
  conditions C1-C6; R2 denied. The six combat-step rows are out of scope (separate ruling).
- **Bridge source (this revision):** `d9e356aa90da4c14dd6767a4ca11d38b9870a4ce` (tree `27bee40d`,
  forge#35) on `claude/forge-unified-successor-20260929`. forge#35 deletes only
  `.foundry/oc561-g1-r1-forge-20261006.yaml` (the engine fork's own OpenCode workstream state file)
  from the forge#33 merge `80336359cf468bec91f525199adb7d09fc726a69` (tree `e5731fea`), which had
  ported the G1 R1 placement from the superseded local Claude line (`510697fa` implementation and
  tests, `04892c87` WS216 test driver, `67da6f07` review follow-ups; tree `8973bc76`) onto the
  unified successor from `ee37e4a5` (forge#28). Over `ee37e4a5` the only changed paths are
  `forge-protocol2-bridge/`: 0 Rules-Core files and 0 card-data files; every bridge blob is
  byte-identical between `80336359` and `d9e356aa` (`StateProjection.java` blob `b3f801c3` at both).
  Exact-head CI on the new commit: Test build run `37620949527` (**success**, Java 17 and Java 21,
  push; completed 2026-10-07 12:54Z). The iOS compatibility gate does not trigger for a
  `.foundry`-only change. The superseded `80336359` exact-head runs (`37531998578`
  Java 17/21 success, `37531998583` iOS success) are provenance only and are never reused. **PB-03
  at the merged pin is PENDING**.
- **Rules-Core authority:** unchanged, `bb0a740d`.
- **Evidence class:** every C5 run below is LOCAL_OBSERVED and ran on the **superseded local Claude
  line** noted in each table row (before `ee37e4a5`; after `510697fa`/`04892c87`/`67da6f07`). Those
  runs are kept as provenance for the ported semantics and are **not credited to the merged pin**
  (`80336359`/`d9e356aa`). Credit requires exact-head CI (present on both merged pins, by run id)
  plus a sealed PB-03 epoch on the merged pin.
- **Not:** Production Provider selection, Architecture Freeze, a denominator change, a Rules-Core
  change, or a PASS promotion.

## What changed in the bridge

| Condition | Implementation at the merged bridge (forge#33 content, forge#35 head; `forge-protocol2-bridge`) |
|---|---|
| C1 fail closed | `BridgeSession.ScenarioTurnBeganSubscriber.onTurnBegan` is registered on the game event bus by `installScenarioBootstrap` (`game.subscribeToEvents(new ScenarioTurnBeganSubscriber())`) before the game thread starts; `handleScenarioTurnBegan` acts only on `GameEventTurnBegan` with `turnNumber()==1` for the intended game. Guava's EventBus (`Game.java:95`) swallows subscriber exceptions, so the handler catches every `Throwable` and records it with `recordScenarioBootstrapFailure`. A session-owned `scenarioBootstrapInvocations` latch records a second turn-1 run as an error; a failure recorded after the hook already completed fails a RUNNING session and aborts the parked frame. The retained `startGameHook` requires `requireScenarioBootstrapCompleted()` (no recorded failure and exactly one successful placement), turn one, and a complete placement list. |
| C2 no fabricated events/state | `ScenarioBootstrap.placeBattlefield` places permanents **untapped** at TurnBegan (the untap step runs after it). Counters are added once there with `addCounterInternal(..., fireEvents=false, ...)` and are never re-applied. Requested tapped state is applied silently with `Card.setTapped(true)` in the retained post-untap hook; `applyPostUntap` then applies requested hands, life and commander damage. `requireCompletePlacement` fails closed on a truncated placement list instead of skipping plan entries. |
| C3 no readiness laundering | `StateProjection.battlefieldDetails` projects `controlled_since_turn_began = !card.isFirstTurnControlled()` (raw summoning sickness, CR 302.6, never `hasSickness()`) for every battlefield entry, redacted ones included. The forge#33 bootstrap neither reads nor validates the requested field; `forge_scenario_lane.py` forwards it only for checkpoint verification and marks `MISMATCH` on a different, missing or non-boolean readback. A non-boolean request or a non-battlefield object is `UNSUPPORTED`. (On the superseded local Claude line the Java side additionally failed an impossible request closed; that verification is Lab-side in the merged port and is covered by `_READBACK_ASSERTIONS` plus the lane checkpoint tests.) |
| C5 hook frame | `PhaseHandler.setupFirstTurn` is unchanged: the hook still runs inside the `givePriorityToPlayer` frame (`PhaseHandler.java:1023-1026`). `_HOOK_ASSERTIONS` are re-derived for `installScenarioBootstrap` / `handleScenarioTurnBegan` / `requireScenarioBootstrapCompleted` / `applyPostUntap`; `_SCENARIO_HOOK_ASSERTIONS` bind the untapped TurnBegan placement, the complete-placement guard and the silent post-untap tap. `_READBACK_ASSERTIONS` assert the `StateProjection` projection fragment. A pre-G1 hook-placement bridge is drift (`test_capability_matrix_refuses_the_pre_g1_hook_placement`). Stale rationale updated: the combat-step dimension, `temporal_reachable`, the `ScenarioBootstrap` class documentation, the `_requested_battlefield` forwarding comment and the `_UNOBSERVABLE_RECORD_DIMENSIONS` text. |

Placement point (re-located on `ee37e4a5`; unchanged by the forge#33 port and by forge#35):
`PhaseHandler.advanceToNextPhase` fires `GameEventTurnBegan` at `:180`. The readiness loop at
`:183-187` clears sickness for the active player's permanents unless `isStartsGameInPlay()` on
turn 0. The placed permanents are not start-in-play objects, so the active seat's permanents are
controlled since the turn began. Every other seat's stay summoning sick (CR 302.6).

## C5: requalification of the 17 Forge PASS rows

**Provenance: every run in this section is LOCAL_OBSERVED on the superseded local Claude line**
(`ee37e4a5` before; `510697fa`/`04892c87`/`67da6f07` after), not on any merged pin
(`80336359`/`d9e356aa`). It is retained as the ported semantics' provenance and is not
requalification credit for the merged pin; see the repin sections below.

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
   - On the local after-runs the classification counts were CONTRACT 2, LAB 39, PROVIDER 17,
     SCENARIO_LANE_EXECUTABLE 12, pass 0. Regenerated on the merged forge#33 tree for the first repin
     they were CONTRACT 2, LAB 37, PROVIDER 19, SCENARIO_LANE_EXECUTABLE 12, pass 0; the delta came
     from main's `stack_state`/`action_cost_state` lane changes absorbed by the merge, not from this
     repin. In both the local and the merged matrices 17 rows simply lose the control-history entry
     from their `mechanisms` list; no `first_missing` changes, no row changes class, and no row gains
     credit. (Second-repin counts are in the forge#35 section below.)
6. **Bridge suite, `WS216SeparateProcessTest.testPipeAmount`.**
   - At `510697fa` it failed with "unexpected COMBAT_DECLARE_ATTACKERS for p1 while driving to
     PRIORITY". p1's placed Dire Wolves / Master of the Wild Hunt may now attack on turn 1, so the
     engine asks p1 for an attack declaration that it did not ask for before.
   - Adjudication: **intended engine-visible consequence of R1**. CR 302.6 / CR 508.1a: the active
     player controlled them continuously since the turn began.
   - Fix (test driver only, `04892c87`, narrowed in `67da6f07` after review P3-4): the pilot
     declines only an attack declaration on turn 1 for the starting seat p1 that is not the frame
     kind it drives to ("No attacks" by label, reachability only, no behavioural credit). Every other
     own-seat combat frame still raises the unexpected-frame AssertionError.
   - No production code changed for it.
   - No row in the 17 reaches p1's turn-1 declare-attackers step, so no requalified row shows this
     frame (identical frame sequences above).

7. **Review rerun at `67da6f07` with the P3-1 lane (`C5_DIFF_BEFORE_REVIEW_HEAD.txt`).**
   - The same producer and lifecycle runs were repeated at the review head with Lab `9585fda`
     (raw digests: scenario `e3c366cb…`, lifecycle `ca6f1131…`).
   - The 12 scenario PASS rows and the 5 lifecycle/pregame PASS rows are again unchanged in
     classification, checkpoint verdicts, frames, offered options and terminal facts.
   - The only further difference is on non-PASS rows (MICRO_LAYERS, MICRO_MODES): the checkpoint
     field's `observed` now lists every same-name detail (for example `[false, false]`) instead of
     the first one.
   - Adjudication: **intended (P3-1)**. The verdicts and the classifications are unchanged.

Not re-baselined silently: nothing was re-baselined. The historical epoch evidence stays bound to
`ee37e4a5`.

## First repin to forge#33 (historical, superseded by forge#35)

- **Pin:** the Lab's `config/rules_engines.json` bridge source moves from the local-only Claude line
  `67da6f07` (tree `8973bc76`) to the merged forge#33 commit
  `80336359cf468bec91f525199adb7d09fc726a69` (tree `e5731fea`, PR 33) on
  `claude/forge-unified-successor-20260929`. `ASSERTED_BRIDGE_COMMIT`, the AF05 matrix
  `bridge_commit`, `CURRENT_BRIDGE`/`_TREE` and `CANONICAL_FORGE_BRIDGE_COMMIT` move with it. The
  Rules-Core authority stays `bb0a740d`.
- **Exact-head CI (now present, by run id):** Test build `37531998578` (Java 17 and Java 21 jobs
  completed success) and iOS compatibility gate `37531998583` (success), both push runs on
  `80336359`. The lock records them; PB-03 on the merged pin stays PENDING.
- **The merged port differs from the local line.** The unified successor's port reworked the
  implementation: the latch, failure record and hook live on `BridgeSession`
  (`ScenarioTurnBeganSubscriber` / `handleScenarioTurnBegan` / `recordScenarioBootstrapFailure` /
  `requireScenarioBootstrapCompleted`), placement is `ScenarioBootstrap.placeBattlefield`, and the
  post-untap apply is `applyPostUntap` with `requireCompletePlacement`. The Java-side validation of a
  requested `controlled_since_turn_began` is not present; the readback projection
  (`StateProjection.battlefieldDetails`) is the same engine fact and the Lab checkpoint comparison is
  the whole check. The port keeps the PR #33 hardening: a late bootstrap error fails a RUNNING
  session and aborts the parked frame; the hook requires turn one and a complete placement list; the
  complete and incremental attack paths decline only the starter's turn-1 sick casts; a scenario
  phasing permanent phases out at the untap step (documented divergence).
- **Lab-side adaptations made for this repin:**
  - `forge_scenario_lane.py`: `_HOOK_ASSERTIONS` and `_SCENARIO_HOOK_ASSERTIONS` re-derived from the
    forge#33 blobs; the control-history readback moved out of the bootstrap field assertions into a
    new `_READBACK_ASSERTIONS` table asserted against `StateProjection.java`, whose blob digest is now
    part of `ForgeScenarioSource`; stale placement-timing comments updated.
  - `forge_hidden_information.py`: `ASSERTED_BRIDGE_COMMIT` moved to `80336359`; the closed
    `BOOTSTRAP_FIELDS` set loses `controlled_since_turn_began` because the merged bootstrap no longer
    reads it. Every other channel fragment matched unchanged; the census reruns at 20
    `PROVIDER_ADAPTER_GAP`, AF05 effect UNKNOWN, pass 0.
  - `FORGE_AF05_MATRIX.json` and `FORGE_RESIDUAL_MATRIX.json` regenerated with their scripts;
    manifests regenerated with `scripts/regenerate_hash_manifests.py`.
- **What this is not:** no historical receipt was relabelled, no row was promoted to PASS, and the C5
  data above was not re-run on the merged pin. Requalification of the 17 Forge PASS rows still
  requires PB-03 on `80336359` plus a sealed epoch.

## Second repin to forge#35 (this revision)

- **Why.** The H4F guard at `docker/forge/Dockerfile:48` admits only `forge-protocol2-bridge/` and
  `pom.xml` as drift from the Rules-Core pin, and forge#33's tree still carried the engine fork's own
  `.foundry/oc561-g1-r1-forge-20261006.yaml`, so the H4F build refused `80336359` with "unapproved
  Rules-Core drift outside the qualified H4F surface". forge#35 deletes only that file; the guard is
  not weakened. The successor branch head is `d9e356aa` (forge#35 merge, tree `27bee40d`, parents
  `80336359` and `c2546d26`).
- **Pin.** The Lab's `config/rules_engines.json` bridge source moves `80336359` -> `d9e356aa` (PR 35);
  `ASSERTED_BRIDGE_COMMIT`, the AF05 matrix `bridge_commit`, `CURRENT_BRIDGE`/`_TREE` and
  `CANONICAL_FORGE_BRIDGE_COMMIT` move with it. The Rules-Core authority stays `bb0a740d`, and every
  bridge blob is byte-identical to `80336359`, so the capability tables (readback + hook) re-derive
  unchanged against the new blobs.
- **Exact-head CI (by run id).** Test build run `37620949527` completed **success** for `d9e356aa`
  (`Test with Java 17` at 12:54:19Z and `Test with Java 21` at 12:53:43Z, push). The iOS
  compatibility gate cannot trigger for this commit (its path filter admits only `**/*.java`,
  `**/pom.xml`, `forge-gui-ios/**` and its own workflow file; forge#35 changes only
  `.foundry/oc561-g1-r1-forge-20261006.yaml`), so no iOS run exists or will exist and none is
  applicable to a state-file-only change. The `80336359` runs `37531998578`/`37531998583` are
  provenance for the superseded commit only and are never reused.
- **Review P3 (comment 6035940198) fixed on the Lab side.** `forge_scenario_lane.py` compared the
  `battlefield_details[].tapped` readback with `bool(item.get("tapped"))`, so an absent key became
  `False` and a default untapped request passed as EXACT against a detail that never stated it. The
  readback is now compared as the literal engine `True`/`False` (the same strict rule as
  `controlled_since_turn_began`): a missing or non-boolean key is a MISMATCH and can never credit.
  Two new red tests fail on the old code (`test_missing_tapped_readback_is_never_coerced_to_untapped`,
  `test_non_boolean_tapped_readback_is_never_coerced`).
- **Census and manifests.** `FORGE_AF05_MATRIX.json` and `FORGE_RESIDUAL_MATRIX.json` regenerated with
  their scripts against the new pin; manifests only with `scripts/regenerate_hash_manifests.py`. AF05
  at `d9e356aa`: 20 `PROVIDER_ADAPTER_GAP`, pass 0, effect UNKNOWN. Residual at this revision after the
  `origin/main` merge (#580-#588): CONTRACT 2, LAB 36, PROVIDER 19, SCENARIO_LANE_EXECUTABLE 13,
  pass 0; the delta vs the first repin is main's #585/#587 reclassification, not this repin.
- **Merge with `origin/main`.** Generated conflicts (`WS17_SHA256SUMS`,
  `FORGE_RESIDUAL_MATRIX.json`) were resolved by regeneration with their scripts, never by hand.
- **What this is not:** no historical receipt was relabelled, no row was promoted to PASS, and the C5
  data above was not re-run on the merged pin. Requalification of the 17 Forge PASS rows still
  requires PB-03 on `d9e356aa` plus a sealed epoch.

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
- **Phasing at the turn-1 untap step (recorded, review P3-2):**
  - CR 502.1 / CR 702.26: phasing happens at the start of the untap step. Since R1 places permanents
    at TurnBegan, before that step, a phasing permanent placed for the starting seat phases out on
    turn 1.
  - XMage's BEGIN_TURN placement behaves the same: phasing is the engine's own untap-step action on a
    permanent that exists then.
  - The phased-out permanent is absent from the battlefield readback (`getCardsIn` filters phased-out
    cards). A record that requests it on the battlefield at the checkpoint can only be a MISMATCH,
    never a PASS.
  - Control: `G1R1TurnBeganBootstrapTest.testPhasingPlacementPhasesOutAndIsAbsentFromReadback`
    (Breezekeeper phases out, Grizzly Bears is the present control).
  - None of the 17 PASS rows places a phasing permanent.
- **Event-less mid-turn change (recorded):**
  - The silent post-untap `setTapped(true)` fires no `GameEventCardTapped`. It is a state change with
    no event. It is accepted only within the XMage precedent's setup exception: setup is muted on the
    public tape.
  - Placing the permanent tapped before the untap step would fabricate an untap and its event, which
    is worse.
  - It is never used for anything but the requested initial tapped state.

## Red tests and mutation-kill evidence

Java (`G1R1TurnBeganBootstrapTest`, real engine, 6 tests; `MUTATION_JAVA.txt`). These mutation runs
were made on the superseded local Claude line; the merged port keeps the same controls under its own
test names (`testLateBootstrapErrorFailsRunningSessionClosed`,
`incrementalAttackFramesNeverAskSickTurnOneCast`, `phasedScenarioPermanentLeavesReadbackAtUntap`):

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
| J12 bridge enumerates sick attackers | **survived (equivalent)** on the complete-declaration path: the engine's own `validateAttackers` revalidation still excludes the turn-1 cast creature, so the offered options do not change. |
| J13 late bootstrap error does not fail the session | killed (`testLateBootstrapErrorFailsRunningSessionClosed`) |
| J14 abort turns FAILED into CLOSED | killed (same test) |
| J15 bridge enumerates sick attackers (incremental path) | killed (`testIncrementalAttackDeclarationOmitsTurnOneCastCreature`: "(1/6)"). On the incremental path (more than four candidates), the bridge enumeration is the only guard, and this control covers it (review P3-5). |

Python (`test_forge_scenario_lane.py`, `MUTATION_PYTHON.txt`): P1–P7 all killed. Review P3-1
added these mutants:

- P8, matching only the matched detail instead of the group multiset: killed by the MICRO_COSTS
  nine-Swamp test and the ambiguity test.
- P10, ambiguity reported as EXACT: killed.
- P11, `bool()` coercion of the request: killed by `test_control_history_request_is_never_coerced[1, "true"]`.
- P12, `bool()` coercion of the `tapped` readback (review P3 6035940198): killed by
  `test_missing_tapped_readback_is_never_coerced_to_untapped` and
  `test_non_boolean_tapped_readback_is_never_coerced`; both are red on the old code.
- P9, `in (True, False)` instead of `is`: survived as an equivalent mutant. The JSON-typed multiset
  comparison still separates `1` from `true`.

Earlier list: (checkpoint verdict
dropped, truthy readback accepted, dimension back to UNOBSERVABLE, request not forwarded, hook
assertion reverted, latch fragment dropped, non-battlefield request accepted).

## UNKNOWN / open

- Exact-head CI for the merged pin `d9e356aa`: **GREEN (PRESENT)** — Test build run `37620949527`
  completed success (`Test with Java 17` at 12:54:19Z and `Test with Java 21` at 12:53:43Z, push).
  The iOS compatibility gate cannot trigger for this commit (path filter: Java, pom,
  `forge-gui-ios/**`, its own workflow file; forge#35 changes only the fork's `.foundry` state
  file), so no iOS run exists or will exist and none is applicable. The superseded `80336359` runs
  (`37531998578` Java 17/21 success, `37531998583` iOS success) are provenance for that commit only
  and are never reused. The superseded local line `67da6f07` had **NOT_RUN** (never pushed); the
  374/0/0/0 local suite is provenance on that tree only and is not credited to the merged pin.
- PB-03 epoch at `d9e356aa`: **NOT_RUN**. Current Forge standing at the merged pin stays UNKNOWN
  until it exists; no historical PASS is promoted by this repin.
- C4(c), complete-declaration path: no bridge-level mutant kills it (J12 is equivalent). It is
  guarded by engine revalidation. The incremental path is covered (J15 killed).
- Review P3-1: same-name, same-controller battlefield objects are now matched as a multiset. EXACT
  requires every matching detail to agree; an ambiguous attribution is UNKNOWN (never credited).
  None of the 12 scenario PASS rows changes.
- Review P3 (6035940198): the `.tapped` readback is compared as the literal engine boolean; an
  absent or non-boolean key is a MISMATCH, so a missing readback can never be laundered into EXACT.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`
