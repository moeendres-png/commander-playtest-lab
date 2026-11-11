# Commander Studio: watching a simulated game

The Studio page `partie.html` ("Partien") shows a game that the rules engine played. XMage
is the only rules authority: it decides every rule and every legal option. The Lab's pilots
choose on every seat. The Studio writes down what happened and shows it; it never works out a
rule and never feeds anything back into the engine.

## What is recorded

`studio/games.py` writes one game log per game into `games/` of the Studio data folder
(outside the repository): a header (seed, engine pin, pilots, seats), one entry per decision
the engine asked for, and a closing entry with the result. An entry holds the board as the
engine published it to the deciding seat (life, counts, battlefield, graveyard, command zone,
stack, that seat's hand) and the option the pilot chose. Face-down cards are never named.

A game log is a `SIMULATED_RESULT`: one seed, one set of pilots. It says what happened in this
game, not how strong a deck is.

## Playing a game

    python -m commander_lab.studio play --deck OWN.json --deck A.json --deck B.json --deck C.json --seed 7

Two to six decks in seat order, as deck snapshots. The page's "Neue Partie" does the same for
a saved deck revision and preconstructed decks from `data/decks/precons/`; the game runs in
its own process and the page follows the growing log.

The engine start command comes from `COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD`, as for every
full game of the Lab. Without it the Studio uses `engine/xmage-engine-bridge.jar` in the Studio
data folder when Java (17 or newer) is installed. That file is the packaged engine bridge
built from the pinned XMage source.

A deck with a card the pilots' public card catalog (`data/cards/pilot_card_knowledge.json`)
does not know is refused before the game starts; the page names the cards. Extend the catalog
with `scripts/build_pilot_card_knowledge.py --names-file`.

## The page

Table with every seat (card images from the local image cache, tapped cards turned), the
stack, the hand of the deciding seat, and a chronological list of actions with life changes.
Playback has start, step, next turn, a speed setting and a position slider; passing and mana
payment can be skipped. A running game is followed live.

## Not in this step

Every seat is a pilot. A human seat needs the engine to wait for a person and is a later
step. Token images are not in the public card data the Studio imports; tokens show as text.
