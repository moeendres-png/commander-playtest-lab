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

## Playing seat 1 yourself (human seat)

"Neue Partie" with "Sitz 1 selbst spielen" starts a game in which the page answers for seat 1
(`studio/play.py`, `POST /api/play/{id}/decision`). XMage still decides every rule: the page shows
only the options the engine offers to that seat and sends back one of them. The AI plays the other
seats. Owner decisions for this mode (2026-11-17, binding):

- **No time limit.** Owner-Entscheid 2026-11-17: im PLAY wartet ein Mensch unbegrenzt; kein Zeitlimit
  beendet die Partie. The page offers no limit to choose. Every start path with a human seat hands
  the bridge the explicit value `decision_timeout_seconds = 0` (unlimited), so the bridge default of
  120 s never applies; the Studio refuses another value for a human seat (HTTP 422). The bridge
  property itself is unchanged. If the bridge nevertheless reports a terminal error
  (`DECISION_TIMEOUT`, engine failure, closed or exited bridge), the loop does not wait on: the game
  ends as failed and the page shows the message.
- **Hands are revealed after the game.** Owner-Entscheid 2026-11-17: nach Spielende werden die Hände
  aufgedeckt. While a game runs, the hands of the AI seats are not delivered: `GET /api/play/{id}` and
  `GET /api/games/{id}` serve the frames without them, and a pick of an AI seat out of a hidden zone loses
  its card names (the engine names the zone of each option: hand or library, such as a tutor or a London
  mulligan bottom; a zone it does not name counts as hidden; picks from the battlefield, graveyard,
  exiled and stack stay visible). The log file in the data folder keeps the full
  frames, because the reveal needs them; it is a local file and is never served while the game runs.
  Once the game has its closing entry, both routes serve the full frames and the page marks the hand
  as "nach Spielende aufgedeckt". Replay then shows what each seat held; a page that watched the game end reloads the frames once
  to receive them.
- **Fast-forward ("Vorspulen bis zu meiner nächsten Entscheidung").** Owner-Entscheid 2026-11-17:
  Vorspulen darf ausschließlich die Pass-Option der Engine auf Prioritätsabfragen senden; sonst nie
  eine Mensch-Entscheidung automatisch beantworten. This is the one narrow exception to the rule
  against silent skips (`AGENTS.md` §2), and the Owner switches it on knowingly. While it is on, the
  page answers a priority question of the human with the pass option the engine offered, the same
  option the opt-in auto-pass sends, and nothing else (`static/vorspulen.js`). It stops, switches
  itself off and shows "Vorspulen beendet: <Grund>" when your turn begins, at every decision that is
  not a priority question (mulligan, attack, block, target, mode, X, mana, trigger order, multiple
  choice, yes/no), when the engine offers no pass option, when the active player is unknown and, with
  "auch bei Gegner-Zaubern anhalten" (default on), when an object that is not yours is on the stack.
  A rejected answer ends it too. While it is on the AI delay of the session is 0 (the existing
  `POST /api/play/{id}/speed`) and the page polls every 150 ms; the slider value comes back when it
  ends. Limit: no bridge change, so it cannot play faster than the engine and the pilots compute, and
  each pass is one request. The old auto-pass checkbox is unchanged and stays opt-in.
- **Save and resume** is not built (Owner: only if it makes sense). A game lives in the memory of the
  Studio process; closing the Studio ends it.

Keyboard: Space toggles the replay only when no button, link or field has the focus; arrows step
through the replay. The decision panel is announced to screen readers when a new decision arrives,
its option groups are labelled groups, and a poll that keeps failing shows a banner "Verbindung zum
Studio unterbrochen" instead of retrying silently.

## Simulation series: several games per engine process

A series (`python -m commander_lab.studio simulate`, `POST /api/simulations/batch`) plays its
games in chunks. One `play-batch` process plays a chunk in one bridge JVM, one game after the
other; `workers` chunks run at once. Options (CLI `--workers`, `--games-per-jvm`; the same
names in the API body):

| Option | Range | Default |
| --- | --- | --- |
| `workers` | 1 to 16 | `min(4, cpu count - 1)`, at least 1 |
| `games_per_jvm` | 1 to 24 | 16 |

The default of 16 (6 before #1587) rests on the Owner-PC throughput measurement of #1588 (WSL2,
`SIMULATED_RESULT`; `docs/analysis-reports/owner_pc_throughput_1588_20261120.md`): +10.5 % to
+13.6 % games per hour against 8 games per JVM, peak memory per JVM unchanged, identical seeds.
Native Windows is `UNKNOWN`. 24 stays selectable but is not the default; the Studio budget stays
at most 56 games per JVM (Owner decision E9).

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

Token images are not in the public card data the Studio imports; tokens show as text. (An
earlier sentence here called the human seat a later step; it exists, see "Playing seat 1
yourself (human seat)" above.)

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

Games are counted per stratum: the deck state (`deck_hash` of the seat, #1657) and the table
size (the number of seats in the log header, #1683). Each stratum is its own table with its own
n/N (`stands`); a log whose header names no deck state or no complete seat list stands apart as
"Stand unbekannt" or "Tischgröße unbekannt" (`unknown_strata`), never added to a known stratum
and never treated as equal to another unknown one. Several deck states are combined only
stratified (Mantel-Haenszel, `strata` = number of strata) and only at one table size: strata of
2, 3 and 4 seats are never combined, because their base win rates differ (1/2, 1/3, 1/4).
When the known strata span several table sizes, the top level carries no card rows
(`NOT_POOLED`), and `cohorts` holds one table per table size (#1694). Within its own table, the
deck states of that table size are combined stratified by the same rules: never across a change
of engine, bridge jar, pilot, decision policy or pod set, and only above `min_exposed`. A single
stratum of another table size therefore no longer takes the stratified view away from the
others. The page shows one section per table size, and every stratum appears once in it with its
own n/N and provenance. `compare_logs` (paired comparison over a logs folder) refuses pairs of
two table sizes in one answer unless `--allow-mixed` is given.

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
