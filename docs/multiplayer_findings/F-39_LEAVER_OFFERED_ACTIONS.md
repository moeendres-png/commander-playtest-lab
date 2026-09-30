# F-39: a player who leaves while holding priority is still offered actions

- **Issue:** #389 (first filed as F-37; renumbered because F-37 and F-38 were taken by parallel lanes the same day)
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

## Follow-up: a concession in the middle of a cast

The first fix left frames in the middle of a cast unchanged. The probe then showed that they failed the lane too:

- P2 concedes while its own Lightning Bolt's target or payment frame is open, then answers that frame (the WS213 contract).
- The engine refuses the rest of the cast of a player who left, and the cast never reaches the stack.
- The lane still failed: `XMAGE_ACTION_EXECUTION_FAILED: priority cast failed` for the target frame, `mana activation failed` for the payment frame.

**Fix:** in `XmageFullGamePlayer`, when a cast, activation or mana activation is refused and the player is no longer in the game, it unwinds like a cancelled payment (`leftMidAction()`) instead of failing the lane. Nothing is chosen for the player, and no option is added.

**Regression:** `aCastInProgressUnwindsWhenItsCasterLeaves` (4P/5P × target/payment) is 4/4 red before the fix and 4/4 green after. Its assertions:

- P2 is never asked again;
- the stack ends empty;
- P3 stays at 40.
