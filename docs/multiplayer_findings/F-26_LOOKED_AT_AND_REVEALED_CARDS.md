# F-26: looked-at and revealed cards never reach the pilot

- **Issue:** #347
- **Surface:** XMage full-game lane observation (`XmageFullGamePlayer`, `XmageFullGameStateRedactor`).
- **Classification:** bridge defect. The rules engine is correct.
- **Pin:** `f79e4168` (unchanged).

## Rules predicate

- **Look:** a player told to look at cards sees them and nobody else does. Example: Peek, "Look at target player's hand. Draw a card."
- **Reveal:** a revealed card is shown to all players (CR 701.16a). Example: Duress, "Target opponent reveals their hand…".

The pilot state must carry each look to the looking principal only, and each reveal to every principal.

## Evidence (4P, before the fix)

P1 casts Peek on P3, who holds Craw Wurm. At P1's next decision:

- the pilot state has no looked-at or revealed field;
- "Craw Wurm" appears nowhere in P1's payload;
- the engine's `GameState.getLookedAt(P1)` is already empty.

## Root cause

XMage stores looks and reveals in `GameState.lookedAt` and `revealed`, but only until the next client update:

- `GameImpl.fireUpdatePlayersEvent()` and the priority prompt call `clearLookedAt()` and `clearRevealed()`;
- XMage's own client receives the cards through the table UPDATE event;
- the Lab redactor never read these fields.

So every `Player.lookAtCards` / `revealCards` effect was invisible to the external pilot.

## Fix

**Capture.** `XmageFullGamePlayer` overrides XMage's terminal methods:

- `lookAtCards(String, Card, Game)`
- `lookAtCards(Ability, String, Cards, Game)`
- `revealCards(Ability, String, Cards, Game, boolean)`

Each override calls super first, then records the engine's own call into a per-game log in the redactor. It records the card names, the owner seats, the engine window title and the turn. Simulation games are skipped.

**Projection.**

| Field | Shown to | In `publicView` |
|---|---|---|
| `looked_at` | the looking principal only | removed |
| `revealed` | every principal | kept |

Object ids are not projected, and there are no card-name special cases.

## Tests

`XmageMultiplayerLookAndRevealTest` covers Peek and Duress at 4P and 5P. It also includes a control that nothing is shown before the spell is cast.

- Before the fix: 4/4 red.
- After the fix: 4/4 green.

## Known limit

The log is not rolled back by an engine undo. Looks and reveals happen during resolution, where the lane does not undo.

## Follow-up: standing reveals (Telepathy)

A continuous "play with hands revealed" effect refreshes its reveal every time effects apply. XMage calls `revealCards(..., postToLog = false)` for that, which uses `Revealed.update` rather than `Revealed.add`.

- **Bug:** the first version appended every refresh. With Telepathy at 4P, `revealed` grew by about three entries per priority pass (9 → 48 after 12 passes), without bound over a game.
- **Fix:** the log mirrors XMage's split.
  - A logged reveal appends a new entry.
  - An unlogged one replaces the earlier entry with the same revealer and title.
- **Result:** each opponent's hand is one current entry.
- **Regression:** `XmageMultiplayerLookAndRevealTest.aStandingRevealStaysOneCurrentEntryPerPlayer` (4P/5P) fails 2/2 before the fix and passes 2/2 after.

**Harness note:** native state restoration cannot start a board that already has Telepathy on the battlefield. The continuous effect calls `hasPlayerInRange` before the game starts. The test therefore casts it.
