# Commander Studio: deck builder (BUILD)

Scope: `docs/OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md`. The deck builder is a
local web application in `src/commander_lab/studio/`. It works on the Owner's collection and
currently on one commander (Chulane, `docs/OWNER_DECK_FOCUS_CURRENT.md`).

## Data

Everything lives in one SQLite store in the Studio data folder
(`COMMANDER_LAB_STUDIO_DATA`, or `studio/` below `COMMANDER_LAB_OWNER_DATA`). The store refuses
a location inside this repository. Card images are cached next to it in `images/`.

| Command (`python -m commander_lab.studio ...`) | Reads | Data class |
|---|---|---|
| `import-inventory FILE.xlsx` | card identities and inventory of the collection | original |
| `import-scryfall PATH [--disambiguation FILE.csv]` | public card data (single `.jsonl`/`.jsonl.gz` or folder of split parts); links the collection | original (public) |
| `import-corpus-register FILE.csv` | source decks | normalized |
| `import-corpus-cards FILE.csv [FILE.csv ...] [--allow-deck-move]` | the cards of the source decks, one or several part files in one transaction (see below) | normalized |
| `import-hub FOLDER` | 2026-11-10 objective hub (`01_DECK_CATALOG_994_SOURCES.csv`, `02_CARD_DICTIONARY_*.csv`, `03_MAINBOARD_99_COMPACT_*.jsonl`, `06_OTHER_BOARDS_NEUTRAL_*.csv`) | normalized |
| `import-cohort FILE.csv --name NAME` | a named group of source decks | normalized |
| `import-marks FILE` | import user-provided card markings (favorite, excluded, notes) from CSV or JSON | original (user markings) |
| `import-edhrec FILE.csv` | EDHREC rows with numerator, denominator, page | original |
| `import-edhrec-manifest PATH [--raw-folder FOLDER]` | immutable 20 HTTP200 EDHREC public captures with full request/response SHA-256 provenance into `source_capture_event` and `observation` (never backfilling historical timestamps) | original (public capture) |
| `import-edhrec-cardrecs FILE.csv` | normalized EDHREC recommendations across cohorts (`cardrecs_alle.csv`) | normalized |
| `import-edhrec-delta PATH` | EDHREC delta JSONL files (`10_EDHREC_STATISTICS_DELTA_*.jsonl`, preserving `NULL` per-card denominators and separate `synergy_pct`) | normalized |
| `import-selection FILE.json --deck-id ID --name NAME --commander NAME` | a saved selection as first deck revision (marking `reserve` entries in `card_mark`) | original |
| `import-lab-deck FILE.json [--deck-id ID] [--name NAME] [--branch BRANCH]` | an on-disk Lab deck snapshot (`DECKBAU_INTERFACE.md`) as a revision | original |
| `import-simulation PATH [--engine-pin PIN] [--pilot-policy POLICY]` | `deckbau_eval.py` JSON simulation reports into `simulation_run` / `simulation_card` | simulated result |
| `fetch-roles --identity WUG --out FILE.json [--replace-scope]` | public role tags (Scryfall tagger) for a color identity, written as a full snapshot of that identity and imported; the query names only the colors | original (public, community labels) |
| `import-roles FILE.json [--replace-scope]` | a role file (format below) as claims | original, normalized or derived, by the file's origin |
| `import-rulings FILE.jsonl [FILE.jsonl ...]` | official card rulings (Scryfall rulings bulk, one ruling per line: `oracle_id`, `source`, `published_at`, `comment`) into `card_ruling`; the rulings of each file replace the ones stored from a file of the same name, and a ruling stays as long as one imported file still lists it (per-file provenance in `card_ruling_source`); a card that is not in the table has no ruling published, an empty table means never imported | normalized (public) |
| `check-role-labels FILE` | compares the role query slugs with a list of official tagger labels (JSON list or one label per line) and names every slug that is not a label | none (report) |
| `fetch-images --commander NAME` | card images of the legal pool into the local cache | public images |
| `data-report` | counts-only report: what the store has, lacks and does not know (collection coverage, public card data age, roles per origin, corpus, observations with unknown times and small denominators, marks, simulation runs) plus hashes of the role tables | none (report) |
| `import-owner-marks FILE.json` | the Owner's own favorites, exclusions and notes (format below) merged into `card_mark`; the report holds counts only | the Owner's own marks, never a rating |

### Role files and the lossless role import (schema 5)

`import-roles` never reads a file as "everything" unless the file says so. A role file
(`studio-roles-2`) carries `role_origin` (`SCRYFALL_TAGGER_ORIGINAL`, `CROSSWALK_NORMALIZED`
with `crosswalk_version`, or `ORACLE_TEXT_REVIEW`), `fetched_at`, `scope` and `roles`
(role name to oracle ids; the role names are those of `roles.ROLES`). Tagger and crosswalk
files also carry `tags` (role to original tag); a review of the Oracle text carries none.

| `scope.mode` | `scope.completeness` | Effect |
|---|---|---|
| `FULL_SNAPSHOT` | `COMPLETE_FOR_SCOPE` | replaces the earlier claims of the same origin, the same `scope.key` (for the tagger: the color identity) and the roles the file lists, and nothing else; if that removes claims, the run stops unless `--replace-scope` is given |
| `PARTIAL_INCREMENTAL` | `PARTIAL` | only adds |

A file without `schema` and scope is refused, except the file older `fetch-roles` runs wrote
(it names its color identity and a tag for every role; it is read as a full snapshot of that
identity). Refused as well: unknown role names, anything that is not an oracle id (blanks, card
ids), an oracle id twice in one role, a missing snapshot time or original tag, and a scope whose
mode contradicts its completeness.

What is stored: every statement is one row of `card_role_claim` (oracle id, role, origin, scope
key, source, original tag, mapping rule). A review of the Oracle text and a tagger label for the
same card and role are two claims; neither overwrites the other. `card_role` (what the builder
reads) is rebuilt from the claims, one row per card and role, pointing at the claim of the
strongest origin (tagger, crosswalk, Oracle text, legacy); `corpus_deck_role` (roles per source
deck) is rebuilt from `card_role` once. All of it happens in one transaction: a file that fails
any check, or an error in the middle, changes nothing, not even the source register. Importing
the same file twice leaves the store as it was.

Migration: schema 4 to 5 only adds the table `card_role_claim`; opening a store upgrades it. The
first role import after that keeps every `card_role` row that has no claim as a claim with origin
`LEGACY_UNSPECIFIED` (nothing is known about it beyond that it was there). A tagger snapshot
later replaces such a row when it lists the same card and role; legacy rows it does not list stay
and are counted in the report. Rollback: copy `studio.sqlite3` before the first import with this
version; an older program version ignores the new table but would not keep it in step.

The tagger bulk (`oracle_tags`) lists canonical labels. `board-wipe` and `graveyard-hate`, the
query slugs of `board_wipe` and `graveyard_hate`, are search aliases of `sweeper` and
`hate-graveyard` (`roles.SEARCH_ALIASES`; the search finds the same number of cards). A reader of
the bulk has to map them explicitly; `check-role-labels` shows where that is needed.

### Corpus card parts (schema 6)

A large corpus comes in several part files. Each file replaces the rows of the decks it holds and
nothing else, so repeating a file is harmless; `corpus_deck_part` remembers which file name holds
which deck. A deck must live in exactly one part, so the import refuses, before it writes
anything, (a) a deck that is listed in two of the files given together, and (b) a deck that an
earlier import took from a part with another file name (a deck split over two files, or a part
renamed: its rows would be replaced by the shorter list). `--allow-deck-move` says that the move
is intended. Several files given together are written in one transaction: a bad row in one of
them imports none. Decks imported by an older program version have no recorded part and are
accepted. `data-report` shows decks without card rows, without a recorded part, and decks whose
mainboard does not add up to 99 cards.

### Owner marks (favorite, excluded, note)

Marks are a filter, a star and an availability condition for the Owner's own use. They are
**never** a strength signal: no evidence figure, rating or tier reads them
(`evidence.TIER_POLICY["never_inputs"]`, pinned by `test_marks_never_change_the_evidence`).
`import-owner-marks` merges: a key a file does not mention stays as it is, a card that cannot be
resolved (by `card_id`, then by name) is counted and skipped, a bad value refuses the whole file
before anything is written, and a second identical import changes nothing. It reads
`{"format": "studio-marks-1", "marks": [{"card_id": "...", "card_name": "...",
"favorite": true, "excluded": false, "note": "..."}]}` and the export of the old HTML studio
(`state.fav` and `state.notes`; `wish`, `variants` and `tierOverride` are counted as ignored, a
tier override is deliberately not imported). A marks file is private data and does not go into
the repository.

### Evidence per card (R3 of #1185)

`evidence.pool_evidence(store, commander_names, view=...)` and `evidence.card_evidence` give,
per card, five layers side by side: `fact` (facts, rule-based mechanical features with the rule
and its version, roles with their origin), `observed_deck` (source decks per cohort as
count of denominator, EDHREC rows with numerator, denominator and snapshot time, or unknown),
`observed_game` (real game events from the Playgroup card atlas once it is imported, #1192), `combo_verified` and
`simulated_result`. Inclusion, lift and synergy are separate metrics and are never merged into
one field. A missing source is `NOT_COLLECTED`, zero hits in a known corpus is
`ABSENT_IN_KNOWN_CORPUS` (a missing observation, not weakness), and every card is `UNRATED`
until a model with outcome evidence exists (`TIER_POLICY`). The `commander` view binds
everything to the named commander; the `global` view has no colour filter and keeps only what
does not depend on a commander. Real game events come from the Playgroup card atlas
(`observed_game`, counted across all commanders, so both views show them): an observed
correlation with its sample size, never a causal card strength and never a tier.

`evidence.role_alternatives` lists free pool cards that share at least one role with a card: a
comparison of function. The order is descriptive (more shared roles, smaller mana value
difference, name) and `improvement_claimed` is always false, because no outcome evidence exists.

The page `tierliste.html` (link "Tierliste" in the header) shows this: views Chulane, Global and
current deck revision; every card "Unbewertet"; columns for mechanics, roles with origin, source
decks as count of denominator, EDHREC inclusion, real games and simulation; an evidence drawer per
card with all rows and the function alternatives; and a research list of what is missing per
card. Sorting by a frequency is offered as a reading aid and labelled as such. Marks are used
only as filters and as a star. API: `GET /api/evidence`, `GET /api/cards/{id}/evidence`,
`POST /api/cards/{id}/alternatives`.

`import-marks` (older command) replaces all three mark fields of every listed card;
`import-owner-marks` only changes the fields a file states. Prefer the latter for partial files.

### Deck universe and "Verbreitung (gezählt)"

The tier list page has a **Universum** selector in its header. A universe is a saved profile
that selects source decks by platform, cohort (for example `bracket:3`), deck date and a
minimum main-deck size. Pick a saved profile, or open "Universum anlegen" in the panel below
the header, fill the fields and save (`PUT /api/universe/profiles/{name}`; unknown keys and bad
dates are rejected). The page remembers the last choice in the browser only. Without a profile
the column shows "kein Universum gewählt".

For every card the column **Verbreitung (gezählt)** shows a level (S to D, or U) and
`hits/denominator`: the number of distinct decks of the chosen universe that contain the
card, over the number of decks in the universe. The panel shows the denominator with its
split by platform and by bracket, and a short snapshot id of the exact decks counted. The
card drawer repeats the numbers, the cut parameters, every spelling found, and loads
"Zusammen gespielt mit" (co-occurrence) on demand.

- It is a count of how often a card is played. It says nothing about how strong a card is.
  The "Unbewertet" tier cell and the evidence policy are unchanged, and the level is not an
  input to them.
- The level is computed from the share with the owner-set cuts (`tiers.py`); U means too few
  decks in the universe or an unknown denominator. A card whose name occurs in no universe
  deck is "unbekannt" (U, `NAME_NOT_FOUND_IN_UNIVERSE`), never a zero and never a low level,
  because absence cannot be told from a name mismatch.
- Names are matched case-insensitively against the oracle name, the engine name and the
  front face. If several spellings occur, the largest count is shown and all are listed;
  they are never added.
- Favourites, excludes and notes only filter the list. They change no count and no level.
- Platforms and brackets are always shown as separate breakdowns; cohorts are not merged
  silently.

Routes: `GET /api/universe/profiles`, `PUT /api/universe/profiles/{name}`,
`GET /api/universe/profiles/{name}/summary`, `GET /api/universe/spread?profile=NAME`,
`GET /api/universe/options?commander=NAME` (the commander is required, 422 without; at most
two names for a partner pair; the counts and offered values are those of that commander's
decks only),
`GET /api/cards/{card_id}/universe?profile=NAME`,
`GET /api/cards/{card_id}/cooccurrence?profile=NAME&limit=25`.

### Strength index ("Stärke-Index", schema 11)

A configurable estimate of card strength per commander, built from usage signals. It is
`DERIVED_DESCRIPTIVE`. It is not a measured win rate and not a statement about outcomes; the
outcome-based evidence field stays `UNRATED`, and the counted "Verbreitung" column is unchanged.

Import (all files optional, split parts `<name>_1.csv`, `_2.csv` are read in number order;
price columns are never read):

```
python -m commander_lab.studio import-signals FOLDER [--commander NAME]
```

The command reports rows read, written, replaced (existing rows of the same commander and
signal that were swapped for the new ones) and, for a file without a valid row, kept (the
existing rows that stayed) per file,
the commander names it imported and the names it did not recognise; when nothing was
replaced the status is `NOTHING_REPLACED`. Signals are stored in
`card_signal(commander_name, signal, card_name, value, numerator, denominator, source_id)`:
`edhrec_commander_inclusion|synergy` and `edhrec_bracket_inclusion:<core|upgraded|optimized|cedh>`
per commander of the files, `edhrec_global_inclusion` and `spellbook_variants` commander
independent (commander name empty), and
`tournament_lists` (lists of the commander that contain the card over all its lists, main and
commander section only) under `--commander` (default: the standard commander). Tournament
files are any `topdeck_*_decks.csv` (split parts `_1`, `_2` allowed); the commander of a
file is taken from its commander section and matched case-insensitively against the commander
names of the store, so a file of another commander is never stored under the wrong name. The commander
file's lift column and the spellbook file's partner count are not stored: no strength
component reads them, and the values remain in the source files (the lift also in the
observation pipeline). Stores imported earlier keep the rows of the two signals they
already hold until `card_signal` is rebuilt; nothing reads them. A value the
source does not publish is NULL (unknown), never 0; a card a source does not list has no row;
rows of a source fetch that was not `AVAILABLE` are not stored. The tournament player column
is never stored. Re-importing replaces the rows of the signals it writes.

Formula, per commander (`strength.py`, pure):

1. Share signals (inclusion, bracket inclusion, deck lists, tournament lists, global) use the
   share measure from the settings: the lower bound of the 95 % Wilson interval of
   numerator/denominator (recommended) or the raw share. Caveat: at one fixed denominator
   the Wilson bound is monotone in the numerator, so it keeps the raw order; it does not
   protect against small samples by itself, and `wilson_lower(0, n)` is exactly 0.0. The
   protection is the **minimum denominator per signal**: a share whose denominator is below
   the minimum is not ranked (component status `BELOW_MIN_DENOMINATOR`, a missing
   observation). Synergy and combo counts are used as published.
2. Each value becomes a percentile rank (0..1). The comparison group is the whole legal pool
   (recommended) or the card's type group or mana-value band; a group of fewer than 5 cards
   falls back to the whole pool and the card says so. Ties share the mean rank. The
   commander card and the basic lands are not ranked by default (tier `N`, "nicht
   bewertet"); the setting can include them. Cards the universe requires (card filter,
   `must_contain`) are filter cards: status `FILTER_CARD`, not ranked, labelled
   "Filterkarte".
3. Index = weighted mean of the present percentiles x 100 (one decimal); a missing component
   is left out and the weights are renormalised. `coverage` = weight of present components /
   weight of all components with a weight above 0.
4. Tier `U` ("zu wenig Daten") when coverage is below `min_coverage` or fewer than
   `min_components` weighted components are present; otherwise S/A/B/C/D by the index cuts
   (default 90/75/55/35, editable). A card absent from a source is a missing observation: it
   lowers the coverage, never the percentile. The setting "missing value" decides per share
   signal what a card without a value does: `skip` (recommended, the component is left out)
   or `lowest` (counts as the lowest percentile, 0; an explicit choice, never the default). With
   `min_coverage` 0 a card with a single weak signal can outrank a card listed by a source at
   1 of 755 decks, which is why the recommendation is 0.4.
5. A deck universe that is a subset (card filter) says so wherever its denominator is shown:
   "Teilmenge: nur Decks mit ..." with the number of excluded decks. The universe's
   `min_universe` is honoured by the strength view (below it: `UNIVERSE_TOO_SMALL`).

Counts are per commander: the universe of a strength request is resolved for the exact set
of the bound commanders (a partner pair matches only its own decks, as `builder.bound_to`
does), and a saved profile whose universe was deleted falls back to "no universe" with a
visible notice instead of failing the request; a profile list entry with an invalid stored
spec is marked invalid and does not break the list. Card names are matched deterministically
(oracle name, then engine name, then front face); a name claimed by two cards is reported in
`ambiguous_names`.

Settings (every label on the page carries its recommendation in parentheses; the
recommended values live in one place, `StrengthSettings` defaults in `strength.py`, and are
served by `GET /api/strength/presets` as `recommended`; the button "Empfohlene Werte" applies
them, an empty weight field means the recommended value and shows it): a weight per component (commander inclusion 3, bracket inclusion 2, deck-list
universe 2, synergy 1, tournament lists 1, global inclusion 1, combos 1, simulation 0), the
bracket (`core`, `upgraded`, `optimized`, `cedh`, `none`), the universe profile (the page uses
the Universum selector), the comparison group (`rank_group`: `pool`), the share measure
(`share_measure`: `wilson`), the minimum denominators (`min_denominators`: EDHREC 30,
tournament 5; the deck-universe minimum is the universe's own `min_universe`), the missing
value per share signal (`skip`), commander and basics (`rank_commander_and_basics`: off),
`min_coverage` (0.4), `min_components` (2) and the editable cuts (`tier_cuts` 90/75/55/35).
The page also filters by tier (S/A/B/C/D/U) and sorts by the percentile of any single
component. Presets:
Ausgewogen, Commander-nah, Turniernah. Owner settings are saved by name. Simulation results
do not count in the tier list and are for now neither collected nor processed for it (Owner
decision B11, 2026-11-12): the `simulation` weight stays as an option, is 0 in the defaults
and in every preset, and the component is `NOT_COLLECTED`. The page's layer count ("Schichten",
sort key and coverage list) does not count the simulation layer either.

The Owner's marks (favorite, excluded, note) never enter the index (Owner decision B4;
pinned by a test). On the page the settings panel "Stärke-Index" holds preset, bracket, one
input per weight, the minimum coverage and a named save; the choice is remembered in the
browser. The new column sorts by index with tier U last; the card drawer lists every
component with value, numerator/denominator, Wilson bound, percentile, weight and status.

Routes: `POST /api/strength` (body `commander` plus at most one of `preset`, `profile`,
`settings`; needs the `X-Studio` header like every non-GET route, 422 without commander),
`GET /api/strength/presets`, `GET /api/strength/profiles`,
`GET|PUT|DELETE /api/strength/profiles/{name}`.

The page names two different things and never mixes them: "Stärke-Index (Schätzung aus
Nutzungsdaten)" (this index) and "Ergebnis aus Partien (noch nicht bewertet)" (the outcome
evidence, `UNRATED`).

### Counting rules behind the shown numbers (follow-up to #1275)

- Cohorts of one family (the text before the first `:`, e.g. `bracket:3` and `bracket:4`) are
  alternatives (OR); cohorts of different families narrow each other (AND). A universe without a
  deck is an explicit state: `empty: true` with `empty_reason` (`NO_SOURCE_DECKS_FOR_COMMANDER`
  or `FILTERS_EXCLUDE_ALL_DECKS`) in the summary, the spread and the co-occurrence, and the
  cards' reason is `UNIVERSE_EMPTY`.
- One list of counted sections everywhere (`store.COUNTED_SECTIONS`: main, mainboard,
  commander, companion): sideboard, maybeboard and cuts count in no figure (universe spread,
  builder frequencies, role counts). Card-level counts, co-occurrence and lift use one
  primitive (`universe.deck_sets`): every spelling of a card is merged into the card, for the
  partner of a pair exactly as for the card itself.
- The builder pool says whether a card's source-deck count is unknown: `decks_known` is false
  when no deck of the commander names the card under any spelling (`decks` is then empty); the
  evidence items carry the same flag. Unknown is never shown as 0.
- Coverage of the strength index is the weight of the present components over the weight of
  the components that have usable data for this commander (a source never imported, or a signal
  wholly below its minimum denominator, counts against no card; a filter card leaves the
  deck-universe component out of its denominator). The minimum number of signals never exceeds
  what that data allows. The reason of a card is `NO_POSITIVE_WEIGHT`,
  `NO_SOURCE_FOR_COMMANDER`, `TOO_LITTLE_DATA` or `ENOUGH_DATA`; the tier follows the unrounded
  index. Other commanders known to the store are not ranked (like the chosen commander and
  basic lands, tier `N`) unless "rank_commander_and_basics" is on.
- The tier list's evidence reads the commander's EDHREC inclusion from `card_signal` when the
  older table has no value (the same entry the builder shows); spread levels carry a German
  `level_name` next to the stable level key.
- Derived figures are computed once per store state: `cache.py` keeps the resolved universe,
  the per-card spread and the builder counts keyed by the store file's change counter, so any
  committed write recomputes them. `GET /api/marks` reads the marks without building the pool.

### Data report

`data-report` prints JSON with numbers only: every figure is a count with its denominator, a
missing value is counted as unknown (never as zero), and no card name, deck address or note text
is included, so the output can go into an issue or a shared document. `roles.fingerprint` holds
hashes of `card_role_claim` (in total and per origin and scope), `card_role` and
`corpus_deck_role`: run the report before and after an import. An import limited to one scope
must leave the hash of every other scope unchanged, and an identical second import must leave
all hashes unchanged. The universe section reports each profile per bound commander (never mixed across
commanders), and the `commanders` section gives, per commander, the pool size, the number
of collection cards excluded for unknown legality, and the signal layer (rows per signal and
the coverage over the pool); commander names appear there, collection card names never do.
The report states what
it cannot measure (`not_measured_here`: pilot knowledge and engine card support for the
collection, collection changes since the last export). The plan for closing the gaps is #1182.

### Captured public EDHREC snapshots (schema 7)

`import-edhrec-manifest` imports immutable 20 HTTP200 public EDHREC captures with full
request/response SHA-256 provenance into `source_capture_event` (event ID, URL, start/complete UTC,
SHA-256, HTTP status 200, size, cardlists count) and `observation`. Historical C079 rows and
timestamps remain untouched (`NULL` stays `NULL`, never backfilled). Unlisted comparison cards
are stored with `DataClass.UNKNOWN` and snapshot `NOT_LISTED_IN_NEW_CARDLIST_UNKNOWN`.

Card facts shown in the builder (color identity, legality, type, text, mana value) come from
the public card data once a card is linked; the workbook stays the source of what is owned.
`import-scryfall` reports every card whose workbook facts differ.

Only image requests leave the machine, and they name single public cards (Owner exception in
`AGENTS.md` §12). The image host is fixed in `images.py`.

### Alles importieren

`import-all` runs the importers above in the right order for one commander and checks the
result: collection (`--inventory`, required), public card facts (`--scryfall`), roles
(`--roles`), rulings (`--rulings FILE`, repeatable; without it the curated
`card_rulings_*.jsonl` of `data/research/deckbuilder_1655` is used), deck lists
(`--decklists`, with `--decklist-format edhrec|archidekt`, default
`edhrec`), usage signals (`--signals FOLDER`, repeatable) and marks (`--marks`). Each step
runs inside the commander scoping of `importing_for`; a step that was not given is reported
as `NOT_PROVIDED`, a step that fails stops the rest (`SKIPPED_AFTER_ERROR`, exit code 1).
Without `--signals`, every folder under `data/research` that holds signal files is used
(today `deckbuilder_1655` and `topdeck_20261112`).

At the end it prints the counts-only data report (`data-report`) and one completeness table:
per layer the rows, the cards of the commander's legal pool that the layer covers, the pool
size and the status `COMPLETE` (the whole pool), `PARTIAL` or `MISSING` (no row). A layer
that is `PARTIAL` is not an error: not every card has a role, a signal, a deck or a
published ruling. With
`--expect-pool N` the command exits with code 3 when the legal pool has another size than
`N`, so a wrong collection or card-fact import is caught before anything is built on it.

Windows PowerShell (from the repository folder; the data folder is the one the starter uses):

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m commander_lab.studio --data "$env:LOCALAPPDATA\CommanderStudio" import-all `
  --commander "<Name des Commanders>" `
  --inventory "<Pfad>\Sammlung.xlsx" `
  --scryfall "<Pfad>\scryfall_oracle.jsonl.gz" `
  --roles "<Pfad>\rollen.json" `
  --decklists "<Pfad>\decklisten" `
  --marks "<Pfad>\marks.json" `
  --expect-pool <erwartete Poolgröße>
```

`--data` is a global option and comes before `import-all`. Leave out every line you do not
have; the table then shows that layer as `MISSING`.

## Start

`python -m commander_lab.studio serve --open` (Windows: `scripts/studio_start.ps1`, Linux/WSL: `scripts/studio_start.sh`). The
server listens on `127.0.0.1` only, rejects other host names, and accepts writes only from its
own page.

The page files in `studio/static/` are read from the source tree (editable install, as the
starter uses it). `pyproject.toml` is bound by a qualification manifest and is not changed for
this; shipping the page inside a wheel is a later step.

## What the builder shows

- The legal pool for the commander with full card images or as a table with selectable
  columns; filters for text, color, type, mana value, free copies, favorites, and simulator
  readiness (`sim_status`, `CODE_DERIVED`).
- The deck list by card type, with the data check (100 cards, commander, color identity,
  singleton, legality, ownership, free copies) and per-card simulator readiness (`OK`,
  `NO_CARD_FACTS`, `KNOWN_MISSING_IN_XMAGE`, `NO_PILOT_KNOWLEDGE`). The check reads stored
  facts; the Rules Core stays the binding check before play.
- Counts of the deck: curve, types, color symbols and mana sources, and role counts (ramp,
  card draw, removal ...) next to the median of the chosen group of source decks. Roles are
  public community labels, not ratings, and not every card is labelled.
- Comparison with the source decks: per group (all, play groups, named cohorts) the number of
  decks that play a card, always with the denominator, and median and middle half of lands,
  creatures and mana value. Groups below 30 decks are marked. These are frequencies, not
  ratings.
- Card detail view: per-cohort source deck inclusion, co-occurring collection cards in the
  same source decks (`both_hits / card_decks`, `DERIVED_DESCRIPTIVE`), neutral non-mainboard
  batch sections (`MAYBEBOARD`, `CUTS`, `SIDEBOARD` with section and batch denominators, never
  mixed with mainboard frequencies), EDHREC cohorts (keeping `lift` and `synergy_pct` separate
  and unverified per-card denominators `unbekannt`), and `SIMULATED_RESULT` cast statistics.
- Exact hypergeometric land-draw probabilities (`DERIVED_DESCRIPTIVE`), variant/revision diffs
  (`Varianten-Diff`, including land-draw probability deltas, role deltas, and on-demand
  `HEURISTIC_MODEL` commander castability / mana-base pre-filtering via `POST /api/prefilter`),
  and 4P XMage simulation run summaries (`Simulation`).
- Search ranks by fit (exact name, name prefix, word prefix, name contains, then type and
  text), alphabetical inside a rank. Sort options include EDHREC share (from the older
  tables, else the stored `import-signals` inclusion with numerator and denominator),
  Synergie and Stärke-Index (the tier page's `/api/strength`, with the settings the tier page
  remembers); an unknown value always sorts last.
- "Nur Decks mit diesen Karten" (tabs Zahlen and Vergleich, `GET /api/deck-filter`): the
  source-deck figures count only the commander's decks that contain all chosen cards, labelled
  "Teilmenge: N von M Decks"; the chosen cards are "Filterkarte" and not ranked. Only cards of
  the commander's pool can be chosen. Same machinery as the universe `must_contain` filter.
- Pages show a data-state box (`GET /api/layers`): which data layers exist for the commander
  and the exact `import-all` call for each missing one. Both pages share one header (Deckbau,
  Tierliste, Partien, chosen commander, light/dark toggle remembered in the browser).
- Drafts are kept automatically; a saved state is an immutable revision. Variants are named
  branches of a deck. Export as text list or as deck snapshot for the simulator.
