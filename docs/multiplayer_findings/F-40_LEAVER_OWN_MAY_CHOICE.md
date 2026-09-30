# F-40: a player who concedes during its own "may" choice still decides

- **Issue:** #403
- **Surface:** XMage full-game lane. A concession (WS213) while the conceder's own non-priority choice is pending (CR 800.4a).
- **Classification:** bridge defect, whose stale answer the engine then counts.
- **Pin:** `9375f35a` (repin v2), with the F-39 native concede follow-up.

## Rules predicate

CR 800.4a: a player who left the game makes no choices.

With Tempt with Discovery ("Each opponent may search … For each opponent who does, search your library …"), P1 searches once for itself and once for each **remaining** opponent who accepts.

## Evidence (4P/5P, before the fix)

P1 casts Tempt with Discovery. The first opponent asked concedes while its `choose_use` frame ("may search") is open.

- The frame stays addressed to the departed player, whose `isInGame()` is `false`.
- Answering "Yes" is accepted. P1 then searches once more than the rule allows: 3 extra searches at 4P instead of 2.

## Root cause

F-39's follow-up retires the conceder's stale frame through XMage's native `signalPlayerConcede(true)`. `GameImpl.setConcedingPlayer` sends that signal only to the **priority player** (or the player controlling it), because XMage stops only that dialog.

A conceder whose own choice is pending during another player's spell is not the priority player. Its stale frame was never retired, and the engine counted its answer.

## Fix

After the native concession, `XmageFullGameSession.submitConcede` calls `XmageFullGameDecisionController.cancelPendingForDepartedPlayer`.

- It retires a pending frame whose own player is no longer in the game, for the observed classes whose callbacks unwind natively: `target`, `mana_payment` and `choose_use`.
- The retirement is recorded as `engine_decision_cancelled` with reason `player_left_game`.
- A retired `choose_use` returns `false`, which is what XMage's own player returns once it cannot respond. No pilot response is accepted, and nothing is chosen on the player's behalf beyond that native no-response.
- Priority keeps its F-39 path.
- Other classes are unchanged until they are observed and qualified. This is the same rule the F-39 follow-up states.

## Tests

`XmageMultiplayerLeaverMayChoiceTest` (4P/5P) asserts that:

- no frame is exposed to the departed player after it leaves;
- every remaining opponent is asked once;
- P1 searches exactly once per remaining opponent who accepted;
- the retirement is recorded.

It is 2/2 red before the fix ("no choose_use frame is exposed to P4/P5 after it left") and 2/2 green after.

The other leave suites stay green:

- `XmageMultiplayerLeaverStackTest`
- `XmageMultiplayerLeftPlayerDecisionTest`
- `XmageFullGameConcedeActionTest`
- `XmageMultiplayerControllerLeavesTest`
