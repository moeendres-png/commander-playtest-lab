# F-31: a library-zone choice shows only the cards the engine put in front of the chooser

- **Issue:** #364
- **Surface:** XMage full-game lane observation. The grant is opened in `XmageFullGamePlayer.chooseTargetInternal` and projected by `XmageFullGameStateRedactor.grantedLibraryView`.
- **Classification:** bridge defect (hidden information). The rules engine is correct.
- **Pin:** `f79e4168` (unchanged).

## Rules predicate

Each principal sees only the library cards the effect shows it:

| Effect | Chooser | Sees |
|---|---|---|
| Fact or Fiction | the separating opponent | only the five revealed cards |
| Impulse (or another top-N look) | the looking player | only those N cards |
| A search | the searching player | the searched library |

No principal learns any other library card or the library order.

## Evidence (4P, before the fix)

- **Fact or Fiction:** P1 casts it, and P3 separates. At P3's `choose_object` decision (5 options), P3's `granted_library` for P1 held all **91** cards of P1's library, in library order. The grant was 0 before and after the decision, so the window itself closed correctly.
- **Impulse:** P1 was likewise granted its whole library instead of the top four.

## Root cause

The WS92-D2 look window opened `beginZoneFullLook(viewer, owner)` for any choice over library-zone cards. `grantedLibraryView` then projected `owner.getLibrary()` in full, ignoring the card set the engine handed to the decision.

## Fix

- **Recording:** the grant records the engine-selected card set of the decision (`restrictedCards`).
- **Projection:** `granted_library` shows only those cards, in library order.
- **Fail closed:** a grant without a recorded set shows nothing.
- **Search:** unchanged, because the engine passes the searched library as the set.

The card set is stored per game and per owner. It is independent of *who* holds the grant, which #351 widens to the controller of a controlled turn.

## Tests

`XmageMultiplayerLibraryGrantTest` runs at 4P and 5P and checks:

- **Fact or Fiction:** only P3 is granted, exactly the five revealed cards.
- **Impulse:** only P1 is granted, at most the top four.
- **In both:** every granted card is one the engine put in front of the chooser, and nothing is granted outside the decision.

Results:

- Before the fix: 4/4 red.
- After the fix: 4/4 green.
- `Ws92D1D2D3ProjectionTest` now passes the looked-at set explicitly and stays green.
