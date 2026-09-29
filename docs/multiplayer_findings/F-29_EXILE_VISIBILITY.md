# F-29: exiled cards are shown to exactly the principals entitled to them

- **Issue:** #366
- **Surface:** XMage full-game lane observation (`XmageFullGameStateRedactor.actorView` / `publicView`).
- **Classification:** bridge defect (missing public and entitled information). The rules engine is correct.
- **Pin:** `f79e4168` (unchanged).

## Rules predicate

- **Face-up exile:** exile is a public zone, so a face-up exiled card can be seen by every player (CR 406.3). Examples: Swords to Plowshares, impulse draw, suspend.
- **Face-down exile:** a face-down exiled card can be seen only by players an effect allows to look at it (CR 406.3). Example: Gonti, Lord of Luxury, "you may look at that card for as long as it remains exiled". For Gonti that is Gonti's controller, not the card's owner.

## Evidence (before the fix)

The redactor projected only `exile_count` for each player, never an exiled identity. The comment said identities were absent "until XMage marks them publicly known", but face-up exile *is* publicly known.

As a result, no principal learned what Swords to Plowshares exiled. A Gonti controller was never shown the card it may look at and cast.

## Fix

Each player entry carries an `exile` array alongside the existing `exile_count`:

| Exiled card | Who is shown it | In `publicView` |
|---|---|---|
| Face up | every principal | yes |
| Face down | only a viewer for whom the engine reports a `LOOK_AT_FACE_DOWN` as-though effect | stripped |

- The face-down check uses `ContinuousEffects.asThough(cardId, LOOK_AT_FACE_DOWN, …, viewerId)`, the same predicate `PlayerImpl.lookAtFaceDownCard` uses. Face-down entries are marked `face_down: true`.
- There is no card-name logic. The engine alone decides who may look.

## Tests

`XmageMultiplayerExileVisibilityTest` runs at 4P and 5P:

- **Swords to Plowshares on P3's Grizzly Bears:** every principal and the public view are shown the Bears in P3's exile. A control checks that nothing is shown before the spell.
- **Gonti, Lord of Luxury targeting P3:** only P1 is shown the face-down card. P3 (its owner), the other players and the public view see only the count, which is 1.
