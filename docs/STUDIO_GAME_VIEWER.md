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
a saved deck revision and preconstructed or verified opponent decks from `data/decks/precons/`,
`data/decks/opponents/kaervek/current/deck.json` and `data/opponents/hosts_of_mordor_precon.json`
(including one-click buttons for the `precon`, `mixed` and `optimized` evaluation pods); the
game runs in its own process and the page follows the growing log.

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

## Card outcomes from simulated games

`python -m commander_lab.studio card-outcomes --deck-id ID [--games-dir DIR] [--min-exposed N]
[--out FILE.json]` and `GET /api/outcomes?deck_id=ID&min_exposed=N` read the recorded game logs
and, for each card of a deck, compare the win rate of that seat in games where the card was in
its **first dealt hand** with games where it was not. Estimand: win rate with the card in the
first dealt hand minus without; simulated games, these pilots, this pod set. The result is a
`SIMULATED_RESULT`, never a tier.

Why the first dealt hand: the shuffle decides it, so inside every game it is a randomised
exposure. "The card was cast" is not: the pilot casts what it can afford and what the game
allows, so cast-versus-not-cast is confounded by how the game went. Cards seen by the end of
the seat's third own turn are listed as a secondary count only, because effect draws and
mulligan bottoms depend on play (not randomised). Commanders start in the command zone and are
excluded; several copies in a hand count the game once. A seat's first dealt hand is the first
`mulligan` frame with cards, so a later mulligan does not replace it. Unfinished or failed
games are skipped, never counted as losses. A game with several winners gives each 1/k of a
win, a game without a winner gives nobody anything; both are counted as draws.

The table gives Wilson 95 % intervals for both win rates and a Newcombe hybrid-score 95 %
interval for the difference in percentage points. A card with fewer than `min_exposed` games
(default 100) in either group is `INSUFFICIENT_SAMPLE`: its numbers are shown but flagged and it
gets no rank. Ranking uses the lower bound of the difference interval, so a card with few games
cannot outrank a well-measured one on a lucky point estimate. Mixed engine commits or pilot
versions are refused unless `--allow-mixed` is given, and then reported as warnings.

What it does not say: how strong the pilots are or how a human would play the card (the pilot
decides how the card is used); anything outside the pods that were simulated (the opponents
are part of the experiment); a deck-building verdict for cards whose value comes late (a
finisher or an answer is rarely decisive in the opening hand, and a land-heavy hand is good or
bad for reasons that are not the single card). Treat it as one measurement next to the others.

Sample size: a card is in the first 7 of 99 cards of the library in about 7 % of games
(7/99 = 7.1 %). The interval half-width for a win rate is about `1.96 * sqrt(p(1-p)/n)`; at a
25 % win rate and +-5 pp that is n = 1.96^2 * 0.25 * 0.75 / 0.05^2 = about 290 exposed games,
i.e. 290 / 0.071 = about 4,100 games of that deck. +-3 pp needs about 800 exposed games, about
11,300 games. The difference interval is a little wider than this because the "without" group
adds its own noise. Each game seats four decks, so these are games in which the deck sat at
the table. With fewer games the table says so in its warnings.

### How to read the numbers (limits)

- **Intent to treat.** The measure is the effect of the card being in the *first dealt seven*.
  The "without" group includes games in which the card was drawn later, and a hand kept after a
  mulligan differs from the first seven, so the effect of owning the card in play is diluted
  towards zero.
- **Independence.** Games that share a seed or a pod are treated as independent. They are not
  fully independent, so the intervals are somewhat too narrow.
- **Duplicates and seats.** Logs sharing a `game_id` are the same game: it is counted once (the
  first file by name) and `duplicate_logs_ignored` reports the rest. When a deck sits at more
  than one seat of a game, only its lowest seat counts for that game; `multi_seat_games`
  reports how often.
- **Many comparisons.** With N cards compared at 95 %, about 0.05 * N will look different from 0
  by chance (`comparisons`, `expected_chance_findings`). Treat the ends of the list as
  hypotheses to re-test with new games, not as verdicts.
- **Cache.** Each finished packed log is read once; the extracted exposure is kept next to the
  logs in `games/.outcomes-cache/<log name>.json`, keyed by the log's size, modification time
  and a format version. A changed or damaged entry is rebuilt, and logs still being written are
  never cached. Deleting the folder is safe: the next request rebuilds it from the logs.
