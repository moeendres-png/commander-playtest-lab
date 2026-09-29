# F-34: a departed turn controller keeps deciding for the controlled player

- **Issue:** #377
- **Surface:** XMage full-game lane, turn control (CR 723) combined with leaving the game (CR 800.4a).
- **Classification:** engine defect plus bridge defect.
- **Pin:** `f79e4168` (unchanged). The engine fix is a donor for the repin lane.

## Rules predicate

CR 800.4a: when a player leaves the game, effects that give that player control of another player end. The controlled player then makes its own decisions for the rest of its turn.

## Evidence (4P/5P, before the fix)

P1 activates Mindslaver ("You control target player during that player's next turn") targeting P4. During P4's turn, P1 concedes while it is making P4's priority decision (`acting_for_seat=3`).

| Build | `P4.turnControlledBy` after the concession | Pending and later frames go to |
|---|---|---|
| pin | P1 (departed) | P1 |
| donor engine fix | P4 | P1 (pending frame not re-addressed) |

## Root cause

- **Engine:** `GameImpl.leave` calls `player.resetOtherTurnsControlled()`, which clears only the leaver's own controlled-players set. The controlled player's `turnControlledBy` still names the departed player.
- **Bridge:**
  - The frame pending at the concession keeps the addressee chosen when it was requested.
  - `decidingPlayer` routed to any controller the engine named, even one that had left.

## Fix

**Engine (donor only)**
- **Where:** mage branch `claude/f34-turn-control-leave-20260929`, commit `2786665809`, based on the pin.
- **Change:** before resetting the leaver's set, `GameImpl.leave` returns each player whose turn the leaver controlled to itself.
- **Status:** handed to the repin lane (#360). The Lab pin is not changed.

**Bridge**
- `XmageFullGameDecisionController.followTurnControl`, called by `submitConcede` after the native concession, re-evaluates the pending frame against the engine's current turn-control state.
  - If the engine gave the turn back, the same engine-generated decision is re-addressed to the new decider under a new decision id. Options, bounds and prompt are unchanged, and the labels were already the controlled player's.
  - The re-addressed frame is recorded as a new `decision_requested`.
- `decidingPlayer` fails closed with `TURN_CONTROLLER_LEFT` when the engine names a controller that has left the game. The bridge never decides the 800.4a outcome itself.

## Tests

`XmageMultiplayerControllerLeavesTest` (4P/5P) branches on the engine's own control state:

- **Engine still names P1 (pin):** no frame is published and the lane fails closed with `TURN_CONTROLLER_LEFT`.
- **Engine returned control (donor engine):** no later frame of P4's turn is addressed to P1 or carries `acting_for_seat`, and P4 answers its own turn.

Results:

| Build | Before the fix | After the fix |
|---|---|---|
| pin | 2/2 red (the departed P1 is asked) | 2/2 green (fails closed) |
| donor engine | 2/2 red | 2/2 green (re-addressed to P4) |

## Known limit

On the pin, a concession by a turn controller during the controlled turn ends the lane fail-closed. The game continues correctly only after the repin carries the engine fix.
