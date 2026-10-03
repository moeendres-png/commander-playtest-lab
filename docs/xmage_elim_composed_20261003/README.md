# #508 XMage composed causal elimination routes

Workstream `XMAGE-ELIM-COMPOSED-ROUTES-20261003` (issue #508, parent #255). It continues
the two #456 rows whose blocker was a Lab harness gap: "the causal routes are not
composed". XMage candidate `37e4df6c` and successor contract 1.0.20 are unchanged.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

## WS05-MP-ELIM-STACK-3: executed through a composed route

**Record.** P1's turn 1, P1 holding priority. P2 is at 0 life, and P2's own Lightning
Bolt targeting P1 is on the stack. Obligation: P2 leaves the game (CR 800.4), and the
P2-owned spell on the stack leaves the game and does not resolve (CR 800.4a).

**Why it needs composition.** No priority point shows a player at 0 life before
state-based actions (CR 704.3). The existing causal-elimination entry therefore
substitutes the victim's life openly and causes the loss with real damage. The stack
must exist while that loss happens, and the existing causal-stack entry builds stacks
only in games without elimination instruments.

**Composed entry: `causal_stack_elimination` (engine bridge).**
- It reuses both preparations unchanged:
  - the elimination's open life substitution and declared instruments, from
    `planCausalElimination`, split into `eliminationRecord`;
  - the stack's frame sources in hand and declared fuel, from `prepareCausalStack`.
- Both existing verifiers serve the composed game. Nothing is placed on the stack, and
  no life total or lost/left flag is set.

**Route** (production probe and the PB-03 midgame producer):
1. **Arrival.** The engine is driven to the checkpoint, and construction equivalence is
   verified.
2. **Stack.** P2 casts its Bolt at P1 on the engine's own frames, paid with the declared
   Mountain. The stack verifier must report `causal_match`: `obj:leave-bolt`, controlled
   by P2, targeting P1.
3. **Elimination.** P1 casts the 14 declared Bolts at P2 on the engine's frames. The
   engine deals the damage and applies the loss (CR 704.5a), then the cleanup
   (CR 800.4a). The elimination verifier must report P2 lost and left, with P1 and P3
   surviving.
4. **Obligation.** XMage removes a leaving player's stack objects without an event
   (`GameImpl.leave`: `getStack().removeIf(object -> object.isControlledBy(playerId))`).
   The evidence is therefore the engine's own stack:
   - frames now carry the stack size from the frame's `pilot_state`;
   - `stack_empty_after` holds when the first priority frame after P2's LOST event shows
     an empty stack;
   - the Bolt never reaches the graveyard and never deals damage;
   - P1 stays at 40.

**Generic fix found on the way.** `eliminate_causally` picked instruments by substring
("bolt", "mountain") over every placed object, so in a composed game the victim's own
Bolt and fuel Mountain counted as instruments. It now reads the plan's declared
instruments, bound by the engine's native ids (`elimination_instrument_ids`).

**Local result** (pinned XMage `37e4df6c`):
- **Probe:** `CAUSAL_ROUTE_REACHABLE`. The stack verifier reported a match; P2 ended at
  life −2, lost and left; the survivors are P1 and P3; P1 is at 40.
- **PB-03 producer:** verified, with all four terminal facts true.

Local evidence is not credit. Credit comes only from the same-epoch PB-03 run on the
pushed head.

## WS05-MP-ELIM-CONTROL-3: blocked by a temporal impossibility in the record

**Record.** P1's turn 1, P1 holding priority. P2 is at 0 life, and P2 owns a Control
Magic attached to P1's Grizzly Bears, which P2 controls.

**Why it cannot be executed as written:**
- The harness cannot place an attachment or a control change (MICRO_CONTROL and CARD_25
  precedent), so both must be caused by a real Control Magic cast.
- Control Magic is an Aura without flash, cast at sorcery speed (CR 307.1) and only by
  its owner P2 on P2's own turn.
- The turn order is seat order (P1 → P2 → P3; F-41), so P2's first turn is turn 2. On P1's
  turn 1, no P2 turn has happened, so no causal history can reach the requested state.

**Classification:** `FIXTURE_DEFECT`. A versioned contract erratum would have to move the
checkpoint to a turn after P2's first turn, for example P1's turn 4: P2 casts Control
Magic on its turn 2, and P1 eliminates P2 on turn 4. That changes the record's
temporal state, and passing through whole turns needs combat declarations no record
field determines. The successor contract is outside this workstream's ownership, and the
erratum needs Coordinator adjudication under #255. The row stays **UNKNOWN**.

## Remaining blockers

| Row | Blocker |
|---|---|
| WS05-MP-ELIM-CONTROL-3 | Fixture temporal impossibility (above); a contract erratum needs Coordinator adjudication |
| WS05-MP-ELIM-TURN-3 | Candidate XMage engine defect; engine remediation is #507 (another owner) |
