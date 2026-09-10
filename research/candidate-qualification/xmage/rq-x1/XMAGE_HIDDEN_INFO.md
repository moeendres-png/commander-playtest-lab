# RQ-X1 — Hidden Information (CODE_DERIVED, key cites DIRECTLY_VERIFIED)

Pin: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`. All paths relative to
`/tmp/rq-xmage-src`. Verdict scale: STRUCTURAL | PROJECTION |
SERIALIZATION | SERVER_REDACTED | UI_ONLY | ADAPTER_REDACTED | UNKNOWN.

SHORT ANSWER: hidden-info protection is SERVER_REDACTED per-viewer projection
(one `GameView` per recipient, built from a `game.copy()`), NOT structural
(the engine `Game`/`Player.choose*` methods receive the FULL game object) and
NOT proven safe: UUIDs and set/card numbers of hidden cards travel on the
wire, logs are single-broadcast strings gated only at construction, and no
adversarial no-leakage suite exists. Server-side ⇒ safe must NOT be assumed.

## 1. Data flow (concrete call chains, CODE_DERIVED)

Periodic update:
`GameImpl.fireUpdatePlayersEvent` (`Mage/src/main/java/mage/game/GameImpl.java:3258-3266`)
→ `TableEvent(UPDATE)` → `GameController.updateGame` (`Mage.Server/.../game/GameController.java:821-829`)
loops sessions AND watchers → each `getGameView()` does `game.copy()` then
`new GameView(copy.getState(), copy, playerId, watcherUserId)` with
permission filtering (`GameSessionPlayer.java:199-230` DIRECTLY_VERIFIED
pattern; `GameSessionWatcher.java:102-110` watcher variant) → per-user
`fireCallback` (`User.java:259-262`, `Session.java:431-475`) →
`ClientCallback(GAME_UPDATE, gameId, GameView→GZIP)` (`Mage.Common/.../callback/ClientCallback.java:34-42,70-84`;
`CompressUtil.java:28-33`) → JBoss Remoting bisocket Java serialization.
Compression/serialization is transport only — redaction happens BEFORE it, in
view constructors.

Decision request: `HumanPlayer.chooseTarget` → `PlayerQueryEventSource.target`
→ `GameController.target:864-877` (builds `new CardsView(game, cards,
playerId, true)` — searcher-only candidate set) → `GameSessionPlayer.target`
(`GAME_TARGET(GameClientMessage(view,…))`) to the chooser only; other players
get "Waiting for X" (`GameController:910-943`).

Private vs public log: `game.informPlayer(p,msg)` (`GameImpl:3952-3957`) →
`PERSONAL_MESSAGE` → one user (`GameController:228-230,947-948`); vs
`game.informPlayers` (`:3223-3231`) → `INFO` →
`ChatSession.broadcast` (same `ChatMessage` object to ALL users,
`ChatSession.java:139-200`) — NO per-recipient log filtering.

## 2. View/projection inventory (`Mage.Common/src/main/java/mage/view/`)

| Class | Projection role |
|---|---|
| `GameView` | per-viewer root: `myHand` (own only), `opponentHands` (empty unless controlling turn), `watchedHands` (permission only), stack, exiles, revealed (public), lookedAt (viewer-only), companion, combat, players, `canPlayObjects` |
| `PlayerView` | library/hand as COUNTS only (`PlayerView.java:71-72`, DIRECTLY_VERIFIED pattern); graveyard full (public); exile owner-filtered; sideboard withheld from opponent humans (`:94-99`); battlefield partitioned; `topCard` only if revealed (`:107-109`) |
| `CardView extends SimpleCardView` | full projection; face-down branch redacts name/rules/types/costs, generic back image (`CardView.java:302-386,1032-1120`; `fillEmpty…` is the redaction primitive) |
| `PermanentView extends CardView` | adds board state; `original` (pre-transform card) non-null ONLY for controller or after game end (`PermanentView.java:43-71`) |
| `CardsView` (map key = real card UUID) | per-card `canShowAsControlled` gate (`CardsView.java:54-64`; `CardUtil.java:2553-2555`: controller-or-owner == viewer) |
| `SimpleCardView/SimpleCardsView` | minimal: `id:UUID + expansionSetCode + cardNumber` — used for opponent/watched hands, LookedAt, decks |
| `ExileView` / `RevealedView` / `LookedAtView` | per-card gate / full-public / viewer-only-minimal respectively |
| `StackAbilityView` | rewrites face-down source display (`:56-70`); skips face-down related objects (`:99-101`) |
| `CombatGroupView` | passes `null` viewer (uncontrolled) but face-down redaction still applies via `isFaceDown` |
| `GameEndView` | intentional full reveal (`hasEnded()` lifts all gates) |
| `GameClientMessage` / `AbilityPickerView` / `DeckView` / `DraftView` | per-recipient decision envelopes (UUID sets/maps) |

## 3. Per-category verdicts

| Category | Verdict | Justification |
|---|---|---|
| Opponent hands | SERVER_REDACTED | `myHand` filled only for `player.getId().equals(createdForPlayerId)` (`GameView.java:80-83` pattern; `myHand` field DIRECTLY_VERIFIED at `GameView.java:46,83,252`); counts only in `PlayerView:72`; `opponentHands` cleared unless controlling turn (`GameSessionPlayer:232-244`); `watchedHands` only with `hasUserPermissionToSeeHand` (`GameSessionWatcher:112-119`) |
| Library order/content | SERVER_REDACTED | only `library.size()` int on wire; order lives in server `Library Deque<UUID>` (`Library.java:19,144-168`); full library `CardsView` only in per-searcher dialog |
| Look-at permissions | SERVER_REDACTED | `state.lookedAt` keyed by viewer (`GameState:71,144,213,549-571`); `GameView` ships only `getLookedAt(myPlayerId)`; cleared next update (`GameImpl:3258-3266`) |
| Reveals | PROJECTION (intentionally public) | global `state.revealed`; full `CardView`s to all + log broadcast (`PlayerImpl:1968-1994`) |
| Searches | SERVER_REDACTED | log is only "searches library" (`PlayerImpl:2969-2971`); candidate set per-searcher (`TargetCardInLibrary:58-114`) |
| Face-down battlefield (morph/disguise/manifest/cloak) | SERVER_REDACTED | state `faceDown` bool (`CardState:19,53-57`); server object mutated to nameless 2/2 (`BecomesFaceDownCreatureEffect:194-367`); views redact + null `original` for opponents; TYPE booleans (`morphed/disguised/…`) DO go to all — type leaks, identity does not |
| Foretell | SERVER_REDACTED | exiled `withName=false` (`ForetellAbility:155`); controller re-access via `LOOK_AT_FACE_DOWN` as-though (`:240-277`); back image on wire |
| Hidden exile (generic) | SERVER_REDACTED | same `ExileView/CardView` gate; log "a face down card" when `withName=false` (`PlayerImpl:5411-5424`); CR 708.9 forced reveal on battlefield/stack→exile (`PlayerImpl:5122-5130`) |
| Graveyard / stack / command / top-card | PROJECTION (correctly public) | full to all (face-down gated); `topCard` only if `isTopCardRevealed` |
| Secret choices (ask/target/mode/amount dialogs) | SERVER_REDACTED | per-recipient query events; never fanned out; chosen modal mode becomes public on stack only post-choice (correct) |
| Game logs / events | SERVER_REDACTED **at construction only; single broadcast** | identical `ChatMessage` to all (`ChatSession.broadcast`); protection is `hideCard`/`withName` gates (`PlayerI
...[truncated 3010 chars]