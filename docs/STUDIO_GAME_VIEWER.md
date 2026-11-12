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

## Simulation series: several games per engine process

A series (`python -m commander_lab.studio simulate`, `POST /api/simulations/batch`) plays its
games in chunks. One `play-batch` process plays a chunk in one bridge JVM, one game after the
other; `workers` chunks run at once. Options (CLI `--workers`, `--games-per-jvm`; the same
names in the API body):

| Option | Range | Default |
| --- | --- | --- |
| `workers` | 1 to 16 | `min(4, cpu count - 1)`, at least 1 |
| `games_per_jvm` | 1 to 24 | 6 |

A chunk is never larger than `games_per_jvm`; there are at least `workers` chunks (as far as
there are games), so a short series still uses every worker. The bridge starts with the fast
options of `fast_jvm_options` (`src/commander_lab/engine/rules/fast_jvm_options.py`, the helper
of `benchmark_xmage_full_games.py --fast`): serial GC, and the AppCDS archive `<jar>.jsa` only if
it exists next to the jar (the JVM ignores one that does not match the jar). Build it with
`scripts/build_xmage_cds_archive.py`. With `workers` above 1 each bridge JVM uses its own copy of
the card repository. A launcher that is not `java` runs as it is, one game per process.

Every game keeps its own log, seed, table row and status. A game that fails is a failed row: its
JVM is discarded, the rest of the chunk continues in a fresh one, and a neighbour whose JVM was
killed by the failure is played again alone (`run_batch`). Cancelling a series terminates the
running engine processes; games that never started have no row. A row appears when its chunk
has finished, so progress moves in steps of up to `games_per_jvm` games.

The series record (API `execution`, `<games>/<batch id>.series.json`, and the title of the
saved source) names the execution identity: `workers`, `games_per_jvm`, the chunks, the JVM
flags (heap, serial GC, AppCDS, batch size) and whether serial GC and AppCDS were used.

"Same game" means: for the same seed, deck and pod, the semantic transcript SHA-256
(`semantic_transcript_sha256`, the field `benchmark_xmage_full_games.py` records as
`semantic`, now also in the closing entry of every game log), the winner seats and the
decision count are equal to those of the game played alone, one game per JVM, default JVM
options. `scripts/check_studio_series_identity.py` checks it on the real engine (Chulane,
`precon` pod of `deckbau_eval.py`, seeds 1-6: alone versus a series with 2 workers, 3 games
per JVM, fast options) and exits non-zero on any difference. Result of the
run of 2026-11-12 (jar built from the pinned source, AppCDS archive present): 6 of 6 games
identical in hash, winners and decisions. Wall times of that run (a loaded machine, a
measurement only): 588 s alone against 314 s as a series. Unit tests
(`tests/unit/test_studio_series_fast.py`) check chunking, per-game logs, failure isolation,
cancellation and the option ranges with fake engines.

Evidence and qualification lanes are untouched and keep one game per JVM; the files that may
batch games are listed in `test_only_known_files_can_batch_games`. The single game started
with "Neue Partie" stays one game per JVM.

## Not in this step

Every seat is a pilot. A human seat needs the engine to wait for a person and is a later
step. Token images are not in the public card data the Studio imports; tokens show as text.
