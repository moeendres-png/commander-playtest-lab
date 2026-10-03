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
   (CR 800.4a). The elimination verifier reads the engine's verdict (P1 and P3 survive);
   the row binding `player_leaves:P2` then requires both the LOST event and the engine
   reporting P2 lost and left. The probe requires the same, plus an empty engine stack
   at the next decision and every survivor at its requested life.
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

## WS05-MP-ELIM-CONTROL-3: harness gap (not executed in this change)

**Record.** P1's turn 1, P1 holding priority. P2 is at 0 life, and P2 owns a Control
Magic attached to P1's Grizzly Bears, which P2 controls.

**What blocks it.** The harness cannot place an attachment or a control change
(MICRO_CONTROL and CARD_25 precedent), so both must be caused by a real Control Magic
cast. Control Magic is an Aura, cast only when its owner could cast a sorcery
(CR 303.1, 117.1a), and on P1's turn 1 P2 has had no turn of its own (seat order
P1 → P2 → P3). A first reading classified this as a fixture defect. That was wrong: the
fresh-context review showed a route that keeps the record as written. A declared flash
enabler for P2 (for example Leyline of Anticipation, a placed permanent like the
existing declared fuel and instruments) lets P2 cast Control Magic on P1's turn after
P1 passes priority (CR 702.8a). The spell resolves, and P1 again holds priority with an
empty stack, which is the record's checkpoint. P1 then eliminates P2.

**Classification:** `HARNESS_GAP`. The lane has no entry that causes a requested
permanent (with its attachment and control change) by its cast and then verifies the
resulting battlefield against the record. Such an entry is a generic extension of the
composed route here: the permanent is cast and resolved, its battlefield state is
verified, then the elimination runs. It is not a contract erratum. The row stays
**UNKNOWN** until that entry exists.

## Remaining blockers

| Row | Blocker |
|---|---|
| WS05-MP-ELIM-CONTROL-3 | Harness gap: no entry that causes a requested permanent by its cast (flash enabler route above) |
| WS05-MP-ELIM-TURN-3 | Candidate XMage engine defect; engine remediation is #507 (another owner) |
