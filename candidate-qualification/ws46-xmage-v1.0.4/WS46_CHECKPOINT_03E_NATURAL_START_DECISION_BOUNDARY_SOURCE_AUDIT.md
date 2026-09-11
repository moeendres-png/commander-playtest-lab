# WS46 CHECKPOINT 03E — NATURAL-START DECISION-BOUNDARY SOURCE AUDIT

## Source Lock

- Commander Lab examined head: `842431d0af4290d86257ea7de5d8010050e49058`
- Commander Lab examined tree: `d65631c38b7357a9ab3d0ef5831ec77f5e6dd849`
- WS44 freeze commit: `12940248497a8795991cbbd2eedef72945528cfe`
- WS44 namespace tree: `6579e119605b90248426a3121a47c487b2bb13cd`
- WS44 v1.0.4 materialization blob: `4e3344bac577aca677260a837dd78e2c096f72f1`
- WS44 materialization SHA-256: `9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35`
- XMage commit: `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
- XMage tree: `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`

## Fresh Run State at Checkpoint

Exact Construction-v2 run: `34218604151`

Exact job: `102036168036` (`full107-construction`)

At checkpoint time the job was still `in_progress` in step 15, `Execute fresh v1.0.4 full107 native construction probe`.

Fresh exact-head steps already completed PASS in that job:

- source locks;
- independent v1.0.4 denominator reconstruction;
- qualification overlays;
- exact XMage build;
- qualification bridge build;
- runtime classpath materialization.

No Construction-107 runtime PASS is granted by this checkpoint.

## New Source Finding

The seven immutable `NATURAL_GAME_START` records are not blocked from native execution by XMage bootstrap. `XmageWs26QualificationSession` does all of the following for that entry mode:

1. sets normal-game options (`testMode=false`, `skipInitShuffling=false`);
2. starts real XMage execution with `game.start(startingPlayerId)`;
3. waits in `start()` on `controller.awaitPendingOrTerminal(...)`;
4. checkpoints `game_started_or_first_decision` before any external `submit` call is made;
5. exposes live provider state through `replayRecorder.currentState()` in `qualificationStatePayload()`.

Therefore a request-independent native state exists at the first externally visible player-decision boundary without executing a discretionary player choice.

## Proven Legacy Evidence Gap

`candidate-qualification/ws42-xmage-v1.0.3/apply_ws42_native_readback_overlay.py` intentionally grants `semantic_state` construction readback only for `NATIVE_STATE_LOAD` and labels every other entry mode:

`NATURAL_START_REQUIRES_EXECUTOR_BOUNDARY`

The WS42 capture then requires the snapshot boundary:

`AFTER_NATIVE_SETUP_VALIDATION_BEFORE_PRIORITY_RESUME`

and requires `semantic_state` inside the readback object.

Consequently the WS42 readback contract cannot prove any WS46 Natural-Start record even though the underlying current XMage session already reaches a real first-decision boundary. This is a qualification-evidence plumbing gap, not yet evidence of a Rules-Core failure.

## Required Remediation Boundary

Any WS46 Natural-Start remediation must remain qualification-only and must:

- preserve the existing `NATIVE_STATE_LOAD` snapshot semantics unchanged;
- capture only live `replayRecorder.currentState()` after `start()` has reached the first pending external decision and before any `submit` call;
- explicitly prove a pending external decision exists (not merely a timer expiry or fabricated state);
- emit a distinct Natural-Start snapshot-boundary identifier;
- keep `request_object_copied_as_proof=false`;
- not consume `successor_requested_state` or the declared requested digest as observed evidence;
- preserve Rules RNG tape and seed-binding evidence;
- fail closed on terminal engine failure or absence of the required decision boundary;
- grant no construction credit until independent v1.0.4 normalization validates observed native state against the immutable contract.

## Gate Status

- Reconciliation: PASS
- Exact XMage build/source lock: PASS on the exact examined head run through build/classpath steps
- Full107 construction: `UNKNOWN / IN_PROGRESS`
- Independent normalized construction gate: NOT CLOSED
- Historical v1.0.3 runtime credit imported: `0`
- AF04/05/06/08/09: NOT GRANTED by this checkpoint
- AF07: NOT GRANTED
- Architecture Freeze: NOT GRANTED

## Exact Next Action

Read the terminal result/artifact of run `34218604151`. If it confirms the source-proven Natural-Start readback failure, implement the minimal WS46-only first-decision-boundary readback described above, persist the exact failure evidence, and execute a fresh exact-head Construction-v2 run. If a different earlier runtime blocker appears, remediate that blocker first.