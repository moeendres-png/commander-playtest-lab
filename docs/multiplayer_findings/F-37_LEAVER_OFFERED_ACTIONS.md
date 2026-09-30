# F-37: a player who leaves while holding priority is still offered actions

- **Issue:** #389
- **Surface:** XMage full-game lane, concession (WS213) combined with a pending priority frame (CR 800.4a).
- **Classification:** bridge defect. The rules engine is correct.
- **Related:** F-35, same family (offered options that abort the game) with a different cause; F-34, same re-issue step.
- **Pin:** `f79e4168` (unchanged).

## Rules predicate

CR 800.4a: when a player leaves the game, all objects that player owns leave the game, and its spells and abilities on the stack cease to exist. A player who has left takes no actions.

## Evidence (4P/5P, before the fix)

On P1's turn, P2 casts Lightning Bolt at P3 and keeps priority with a second Bolt castable. P2 then concedes (`submitConcede`).

- **Engine:** correct. P2 has left, the Bolt is gone from the stack, and P3 stays at 40.
- **Bridge:**
  - P2's unanswered priority frame still offers "Lightning Bolt — Cast Lightning Bolt".
  - Picking it fails the lane: `XmageFullGamePlayer.priority` casts, the engine refuses a player who has left, and the result is `XMAGE_ACTION_EXECUTION_FAILED: priority cast failed`.

## Root cause

WS213 keeps a concession from wedging the engine: the conceder answers its own pending frame. That frame was built before the concession, so it kept every action that was legal then.

XMage itself stops the conceder's open dialog when the priority player concedes (`GameImpl.setConcedingPlayer` calls `signalPlayerConcede(true)`), and the Lab does not implement that signal.

## Fix

After the native concession, `XmageFullGameDecisionController.followTurnControl` (the F-34 step) re-issues a pending priority frame whose own principal has left:

- it keeps only the `pass_priority` option;
- its context carries `actor_left_game: true`;
- it gets a new decision id and is recorded as a new `decision_requested`.

Options are only removed, never added. The pilot still answers the frame, so nothing is decided for it and the WS213 contract is unchanged. Frames of other decision classes are left as they were (see the known limit below).

## Tests

`XmageMultiplayerLeaverStackTest` (4P/5P) asserts:

- P2's Bolt ceased to exist;
- the frame offers only pass;
- P2 is never asked again;
- P3 took no damage.

It is 2/2 red before the fix, because "Cast Lightning Bolt" is still offered, and 2/2 green after. `XmageMultiplayerControllerLeavesTest` and `XmageFullGameConcedeActionTest` stay green.

## Known limit

A concession in the middle of a cast (a pending target or payment frame of the conceder) keeps its options. That surface is WS213's; native XMage aborts every open dialog there.
