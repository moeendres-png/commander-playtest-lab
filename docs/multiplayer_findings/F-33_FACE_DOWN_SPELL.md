# F-33: a face-down spell on the stack is named only to its controller

- **Issue:** #369
- **Surface:** XMage full-game lane observation and option labels (`XmageFullGameStateRedactor` stack view, `XmageFullGamePlayer.objectLabel`).
- **Classification:** bridge defect (hidden-information leak). The rules engine is correct.
- **Pin:** `f79e4168` (unchanged).

## Rules predicate

- CR 708.4: a face-down spell has no characteristics that an opponent may see.
- CR 708.5: its controller may look at it.
- CR 723.4 extends that look to the controller of that player's turn.

## Evidence (4P, before the fix)

P1 casts Exalted Angel face down using morph. While the spell is on the stack:

- the priority decisions of P4, P3 and P2 contain "Exalted Angel", because the stack item used `StackObject.getName()`;
- P2's Counterspell target option is labelled "Exalted Angel", because `objectLabel` resolves the id through `game.getCard`.

Once the spell resolves, the face-down permanent has an empty engine name, so the battlefield does not leak.

## Fix

- **Stack view:** a face-down spell carries `face_down: true`. Its `name` is shown only to a principal entitled to its controller's private state (the controller itself, or per CR 723.4 the controller of that player's turn); for everyone else it is `null`. `publicView` nulls the name.
- **Option labels:** a face-down spell is labelled "Face-down spell" for any chooser but its controller.

## Test

`XmageMultiplayerFaceDownSpellTest` runs at 4P and 5P and checks that:

- every opponent is asked for priority while the spell is on the stack, and none of their decisions names the card;
- P1 is shown the name, and the public view is not;
- P2's Counterspell targets the spell by its "Face-down spell" option and counters it.

Results: 2/2 red before the fix, 2/2 green after. Full bridge suite: 694 run, 0 failures.

## Follow-up: the resolved face-down permanent

Once the morph resolves, its controller may still look at it (CR 708.5).

- **Bug:** `private_identity` came only from the registry used for restored face-down permanents. A controller who cast a morph in-game was never told which card it is.
- **Fix:** the identity now falls back to the engine's own card behind the permanent. It is shown to the controller, to the controller of that player's turn (CR 723.4), and to anyone the engine grants `LOOK_AT_FACE_DOWN`. A face-down token has no hidden card, so it shows nothing. `publicView` still strips `private_identity`.
- **Test:** `aFaceDownPermanentIsIdentifiedOnlyToItsController` (4P/5P) fails before the fix and passes after. It checks that P1 is shown "Exalted Angel" and that no other view, and not the public view, contains it.
