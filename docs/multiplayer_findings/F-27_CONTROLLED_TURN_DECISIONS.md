# F-27: decisions during a controlled turn go to the controller

- **Issue:** #348
- **Surface:** XMage full-game lane decision routing (`XmageFullGameDecisionController`) and observation (`XmageFullGameStateRedactor`).
- **Classification:** bridge defect. The rules engine is correct.
- **Pin:** `f79e4168` (unchanged).

## Rules predicate

CR 722 (Controlling Another Player): while a player controls another player's turn, the controller makes every choice and decision for the controlled player, and sees everything that player can see. Mindslaver's reminder text says the same.

## Evidence (before the fix)

At 4P and 5P, P1 activates Mindslaver targeting PN, the next player in turn order. During PN's turn:

- the engine reports `getTurnControlledBy() == P1`;
- the lane still asked PN's own principal for PN's priority, mana payment, targets and cleanup discard;
- P1 was never asked and never shown PN's hand.

## Root cause

- The decision controller always used the engine player whose callback fired as the deciding principal.
- The redactor projected a hand only to its owner.

## Fix

**Routing.** When the engine records that another player controls this player's turn (`Player.getTurnControlledBy`):

- the decision goes to the controller's principal;
- the request carries `acting_for_seat`;
- a missing controller fails closed.

**Observation.** The controller's pilot state shows the controlled player's hand, mana pool and land plays. Looks made by the controlled player during the turn are also shown to the controller (F-26 log).

Other players still decide their own decisions during the controlled turn, for example when they get priority.

## Tests

`XmageMultiplayerTurnControlTest` runs at 4P and 5P and checks that:

- PN is never asked during its controlled turn;
- every decision made for PN goes to P1, with `acting_for_seat` set to PN's seat;
- P1 sees PN's Lightning Bolt;
- P1 makes PN bolt itself, so PN loses 3 life;
- the next turn is decided by its own player again.

Result: 2/2 red before the fix, 2/2 green after.
