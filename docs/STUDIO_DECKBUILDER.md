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
per commander of the files, `edhrec_global_inclusion`, `spellbook_variants`,
`spellbook_two_card_variants` and `spellbook_partners_in_collection` commander
independent (commander name empty), and
`tournament_lists` (lists of the commander that contain the card over all its lists, main and
commander section only) under `--commander` (default: the standard commander). The counted
research file `topdeck_card_conversions.csv` stores `topdeck_card_conversion` under each
commander of its own commander column: the value is the published conversion rate (decks
with the card that reached the top cut over the decks whose top-cut outcome is known), the
stored denominator is that known-outcome base — never the appearances, which also count
decks of unknown outcome — and where the source publishes no rate (base below 10, the
literal `NULL` in the file) the value stays NULL while numerator and denominator are
stored as counted. Tournament
files are any `topdeck_*_decks.csv` (split parts `_1`, `_2` allowed); the commander of a
file is taken from its commander section and matched case-insensitively against the commander
names of the store, so a file of another commander is never stored under the wrong name. The commander
file's lift column is not stored: no strength component reads it, and the value remains
in the source file (and in the observation pipeline). The spellbook file's partner count
and variant ids are stored (as the two signals above; the two-card count is derived from
the ids, one id per card slot of a variant): the combos component of the strength index
ranks variant count, two-card variant count and partners in the collection together, so
combo quality counts, not the raw variant count alone. What the spellbook file does not
publish — the result a combo produces, the partners of one single variant — is not
stored either; it stays unknown. A value the
source does not publish is NULL (unknown), never 0; a card a source does not list has no row;
rows of a source fetch that was not `AVAILABLE` are not stored. The tournament player column
is never stored. Re-importing replaces the rows of the signals it writes.

Formula, per commander (`strength.py`, pure):

1. Share signals (inclusion, bracket inclusion, deck lists, tournament lists, tournament
   conversion, global) use the
   share measure from the settings: the lower bound of the 95 % Wilson interval of
   numerator/denominator (recommended) or the raw share. Caveat: at one fixed denominator
   the Wilson bound is monotone in the numerator, so it keeps the raw order; it does not
   protect against small samples by itself, and `wilson_lower(0, n)` is exactly 0.0. The
   protection is the **minimum denominator per signal**: a share whose denominator is below
   the minimum is not ranked (component status `BELOW_MIN_DENOMINATOR`, a missing
   observation). Synergy is used as published. The combos component value is a quality
   mixture, not a published count: the mean of the card's percentile ranks in variant
   count, two-card variant count and partners in the collection (`strength.combo_quality`);
   that mixture is then ranked like every other value.
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
   `min_components` weighted components are present, or (rule `require_commander_signal`) no
   commander-specific component has a ranked value; otherwise S/A/B/C/D by the index cuts
   (default 90/75/55/35, editable). A card absent from a source is a missing observation: it
   lowers the coverage, never the percentile. The setting "missing value" decides per share
   signal what a card without a value does: `skip` (recommended, the component is left out)
   or `lowest` (counts as the lowest percentile, 0; an explicit choice, never the default). With
   `min_coverage` 0 a card with a single weak signal can outrank a card listed by a source at
   1 of 755 decks, which is why the recommendation is a minimum (0.3, see below).
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
universe 2, synergy 1, tournament lists 1, tournament conversion 1, global inclusion 1, combos 1, simulation 0), the
bracket (`core`, `upgraded`, `optimized`, `cedh`, `none`), the universe profile (the page uses
the Universum selector), the comparison group (`rank_group`: `pool`), the share measure
(`share_measure`: `wilson`), the minimum denominators (`min_denominators`: EDHREC 30,
tournament 5, conversion 20; the deck-universe minimum is the universe's own `min_universe`), the missing
value per share signal (`skip`), commander and basics (`rank_commander_and_basics`: off), other commanders in the pool (`rank_other_commanders`: on, ranked like any card),
`min_coverage` (0.3, "Mindest-Datenlage"), `min_components` (2), `universe_source` (`auto`), `require_commander_signal` (on) and the editable cuts (`tier_cuts` 90/75/55/35).
The page also filters by tier (S/A/B/C/D/U) and sorts by the percentile of any single
component. Presets (weights commander inclusion / bracket / deck universe / synergy / tournament /
global / combos / Playgroup observation; simulation is 0 in all):
Ausgewogen 3/2/2/1/1/1/1/1 (the defaults), Commander-nah 3/2/3/2/1/1/0/0 (bracket upgraded),
Turniernah 1/2/2/0/3/1/1/1 (bracket cedh). Every preset counts the deck universe, the most
commander-specific source. The Playgroup observation (`playgroup_observed`, from 25 games,
shrunk towards zero) is commander independent: it is not one of the signals
`require_commander_signal` asks for. Owner settings are saved by name. Simulation results
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

### Rating layers ("Bewertungsebenen")

Additional, objectively derivable layers that rank cards next to the strength tier. Each is
its own column on the tier list page (a per-viewer column chooser, remembered in the browser;
each column sorts by its percentile; a filter for the pod scaling class) and a small table in
the card window of the tier list and of the builder. A layer never changes the tier on its own:
the settings group "Zusätzliche Ebenen" gives each of four layers an optional weight in the
strength index, **default and recommendation 0** (all three presets keep 0). With every weight
at 0 the tier and the index of every card are bit-identical to a run without layers (pinned by
`tests/unit/test_studio_layers_view.py`; on the Chulane store of the repository the tier counts
stay S5 A83 B259 C253 D322 U0 N5 and every card's index, coverage and present count equal the
run before the change). A weighted layer joins like any other component: its percentile among the ranked
pool cards (rank group setting applies), its weight counts in the coverage, a card without a value
lowers the coverage and never the card. No layer is commander specific, so none satisfies
`require_commander_signal`. A weighted layer with no value for any card is named in `notices`
and leaves the coverage of every card alone. The commander and basic lands get no layer value
(same exemption as tier `N`). Names are matched by oracle id, else exact oracle (or engine) name,
else the FRONT face only; a back half never matches.

Every value has a status: `OK`, `UNKNOWN` (reason `NO_RECORD`, `NO_COUNT`, `NO_VALUE_PUBLISHED`,
`SAMPLE_TOO_SMALL`, `INSUFFICIENT_SAMPLE`, `NO_TEXT`) or `NOT_APPLICABLE` (`NOT_A_PERMANENT`,
`NOT_RANKED`). **Unknown is shown as "–" with its reason and is never 0.** Per card the tier
endpoint returns `layers` (value, raw share, Wilson bound, `n`, percentile 0 to 100, status,
reason, note) and per result `layer_summary` (per layer: pool cards with a value, unknown, not
applicable, source, denominator, measured or derived). `GET /api/rating-layers?commander=&pod_size=`
serves the same layers without the index for the builder. The percentile shown per layer
is pool-wide (all valued pool cards, ties share the mean rank; a single valued card is 50); only
the index component of a weighted layer follows the `rank_group` setting. "Sieg-Abstand" shows
the damped gap the index reads first and the measured gap beside it; the column sorts by the
damped value. A weighted `pod_scaling` has a value for every card with oracle text, so it counts
as a present component for nearly every card and raises their coverage: a card can pass the
"Mindest-Datenlage" on a text rule alone. That is why its recommended weight stays 0.

| Layer (key) | Source | Denominator | Kind |
|---|---|---|---|
| "Großpod-Wirkung" (`pod_scaling`) | oracle text of all faces | none | derived by rule, no measurement |
| "Tempo" (`tempo`) | Playgroup atlas `on_curve_count` | `on_curve_denominator` | measured correlation |
| "Ausspielquote" (`playability`) | `drawn_to_played_pct` | `ever_drawn_n` | measured correlation |
| "Standfestigkeit" (`staying`) | `battlefield_survival_pct` | `reached_battlefield_n` | measured correlation, permanents only |
| "Sieg-Abstand" (`win_gap`) | the Playgroup observed gap | `winrate_when_cast_n` | measured correlation, column only |

**Measured share layers** (tempo, playability, staying). A value counts only from `n >= 25` and
when the atlas record is not flagged `insufficient_sample`. The ranking value is the 95 %
Wilson lower bound of the published share (`strength.wilson_lower`, the function the index
uses); the raw share, `n` and the bound are all shown. The source publishes whole percents, so
the count behind the bound is `round(share * n)`. Missing or thin is `UNKNOWN`. Limits:
these are correlations observed in other players' multiplayer games (Playgroup.gg, CC BY 4.0),
not causal card strength, not a win rate of the Owner's games, and the source has no breakdown by
pod size. The playability share is cast-over-drawn: its denominator is the funnel count
`ever_drawn_n` (games in which the card was drawn), not `first_cast_n` (its numerator); a
record without `ever_drawn_n` has no value (`NO_COUNT`), no other count stands in. In the repository atlas
(1,655 records) 73 playability percents differ from `first_cast_n / ever_drawn_n` by more than
one percentage point, all of them legendary creatures (a cast from the command zone is not a
draw). Tempo: the share is the record's own `on_curve_count / on_curve_denominator` (that is the
share the Wilson bound and `n` belong to); the percent the source printed (`on_curve_pct`) is
not used. When it differs from that share by more than one point (361 of 674 records) the
tooltip says "Quelle nennt X %" and the layer summary counts such records; the cell carries no
marking. A record without count or denominator is `UNKNOWN` (`NO_COUNT`), never the published
percent.

**"Sieg-Abstand"** is `strength.observed_gap`, the function behind the index component
`playgroup_observed`: the same minimum of 25 games in which the card was cast and the same
shrinkage `gap * n / (n + 25)`; there is no second implementation. It has no weight of its own,
because the index already counts it (a second weight would count it twice); it is a column only.

**"Großpod-Wirkung"** is derived from the oracle text by fixed rules
(`layers.classify_pod_scaling`, table-driven test with 68 real card texts). Reminder text in
parentheses is removed first; matching is on the lower-cased text. Classes, strongest first (the
rank value is the ordinal 3, 2, 1, 0):

1. `SCALES` "wirkt auf jeden Gegner": "each opponent", "each other player", "each player",
   "for each opponent", "number of opponents", "each of your opponents", the plural "your
   opponents", an effect on or a count of the permanents "your opponents control" ("creatures
   your opponents control ...", "number of/for each ... your opponents control"; a protective
   clause on "spells or abilities your opponents control" is no match), the keywords "Overload",
   "Extort", "Myriad" and "Melee" (also inside a keyword line such as "Flying, myriad") and the attack taxes "can't attack you unless" and
   "creatures can't attack you" (Ghostly Prison, Propaganda, Sphere of Safety).
2. `OPPONENT_TRIGGER`: "whenever an opponent", "whenever a player", "whenever ... an opponent
   controls", "at the beginning of each opponent's/other player's/player's ...". These are
   matched first and removed, so the "each player" in "at the beginning of each player's" does not
   count as a scaling clause.
3. `SINGLE_TARGET`: none of the above, and the card names "target opponent" (a "target
   player" alone is often aimed at yourself and stays `NEUTRAL`), or has one removal or counter on one target ("destroy/exile/counter/gain control of target
   creature|permanent|spell|artifact|enchantment|planeswalker|battle", "return target ... to its
   owner's hand", "deals N damage to any target/target ...", "target ... gets -X/-X").
4. `NEUTRAL`: nothing of the above.

The strongest class that applies wins; a mode of a modal card counts like a sentence, so a card
with "target opponent" and "each opponent" stays `SCALES`. The extra flag `SYMMETRIC` marks a
matched phrase that also hits you ("each player", "whenever a player", "at the beginning of each
player's"). The matched phrases are returned (`detail.phrases`) and shown, so the page says why. The
pod size setting "Pod-Größe" (2 to 6, default and recommendation 4) only changes the displayed factor
"wirkt auf N-1 Gegner" of a `SCALES` card; no class, rank or index depends on it. The page labels
the layer "aus dem Regeltext abgeleitet, keine Messung". Limits: it is a rule on text, not a
measurement; it cannot see what a card does through a keyword or a static ability it does not
spell out (Fireball, whose damage is divided among any number of targets, is `NEUTRAL`); a keyword
is matched on its keyword line, its reminder text is removed like any other; a card without oracle text in the store is `UNKNOWN`
(`NO_TEXT`), a vanilla card with empty text is `NEUTRAL`. Favorites, exclusions and notes are not read, and
no price data is involved.

### Counted deck-list universes, `universe_source` and the commander-signal rule

The repository holds complete deck lists that were counted, as one file per commander:
`<slug>_decklist_inclusion_<date>.csv` (numbered parts allowed; today
`data/research/chulane_decklist_inclusion_20261112.csv`) with the columns `card_name, source,
bracket, decks_with_card, universe_decks` (plus `share`, `universe_snapshot`). One universe is
one `(source, bracket)` pair. `import-signals FOLDER` (and `import-all`, which also reads
`data/research` itself when it holds such a file) stores per universe one signal
`decklist_universe:<source>:<bracket>` (value = share, numerator, denominator; the snapshot id of
the file is kept in the title of the universe's source row). The file has no commander column,
so the commander is the `--commander` of the import and is **checked per universe**: in a
universe the commander's own card must be in every deck (`decks_with_card == universe_decks`),
otherwise that universe alone is refused (reason `COMMANDER_NOT_IN_EVERY_DECK`) and nothing of
it is stored; the other universes of the file are stored. Mixed denominators inside one
universe (`MIXED_DENOMINATORS`) and an invalid count (`INVALID_COUNT`) refuse that universe the
same way. The report names every refused universe (`universes_refused`: source, bracket,
reason, the commander's decks, the universe's decks; `import-all` prints it in the step
detail); the file is `REFUSED` only when none of its universes can be stored. A refused
universe is never an option of `universe_source`. Duplicate
card rows keep the first and are counted. `expected_signals()`, the completeness table and
`/api/layers` list the stored universes, or one generic row `Signal decklist_universe` as
`MISSING` while none exists.

The deck-universe component takes its counts from ONE universe, chosen by the setting
`universe_source` (`universe_choice.choose`, the one place that decides; the builder asks the
same function with the universe source and bracket the tier page remembers in the browser,
the recommended settings when it has none). When the used counted universe holds rows that
match no card of the store, the tier result carries a notice. `auto` (recommended): (1) a stored universe profile that is selected on the
tier page; (2) all local deck lists of the commander when there are at least `min_universe`
(default 30); (3) the counted universe whose bracket matches the bracket setting (core 2,
upgraded 3, optimized 4, cedh 5; the larger denominator among sources); (4) without a match (or
bracket `none`) the counted universe with the largest denominator; (5) none. Other values:
`profile` (only the selected stored profile), `counted:<source>:<bracket>` (exactly that one),
`none`. Two universes are never combined and signals are read for this commander only. Because
all of them are complete lists, a pool card that is in none of the decks is a **counted zero**
(`ZERO_COUNT`: 0 of N, ranked, with the universe denominator, labelled as counted in the card's
signal row); a card whose name is ambiguous stays unknown. A stored profile and the local deck
lists treat such cards the same way. Names are matched by oracle name, then by the FRONT face
only; the back half of a two-part name is never a spelling of the card. The result's
`universe_choice` names the universe used (kind, label, denominator, snapshot, reason,
automatic) and the tier page prints it in "Index berechnet mit". The deck-universe weight
(recommended 2; 0 switches it off and then it adds neither value nor coverage) is set like any
other (Owner decision B12). Without a profile the builder asks the same function
(`universe_choice.choose`): when the automatic choice is a counted universe (fewer local deck
lists than `min_universe`) it shows that universe in the frequency column, always labelled
"Verbreitung (gezählt): <source>, Bracket <n>, <N> Decks"; with enough local deck lists the
builder and the tier list both use those.

Tier rule "commander-specific evidence" (`require_commander_signal`, recommended on): a card
gets a tier only if at least one commander-specific component (commander inclusion, bracket
inclusion, deck universe, synergy, tournament lists) has a ranked value with a weight above 0;
global inclusion, combos and the Playgroup observation are the same for every commander and
never give a tier alone
(tier `U`, reason `NO_COMMANDER_SIGNAL`, "kein Signal speziell für diesen Commander"; simulation
never counts). The recommended minimum data situation (`min_coverage`, shown as
"Mindest-Datenlage") is 0.3: with a counted universe an unlisted card has deck universe 2 +
global 1 + combos 1 = 4 of 12 = 0.33 (total weight 12 with the Playgroup observation at 1; the
minimum is reached without a Playgroup observation, with one it is 5 of 12).

### Combos in the deck (schema 14)

The combo list of a commander (`edhrec_<commander>_combos.csv`: `cards` separated by `;`,
`num_decks`) is stored twice by the signal import: per card as the signal
`edhrec_combo_decks` (a marker layer, never a rated component) and, since schema 14, as full
card sets in the table `commander_combo`. A replacing import swaps the commander's list, an
appending one only adds sets that are not stored yet.

The deck check (`POST /api/check`, and a stored revision) returns `combos`: the listed combos
the deck holds completely and the ones that lack exactly one card, each with the source's deck
count. The statistics tab shows them under "Kombos im Deck" and says for a missing card whether
it is in the pool. Names match by the full card name, then by the front face of a two-part card,
never by the back half. Limits: only listed combos are known; without a stored list the section
says so and never claims "no combos"; the deck count is the source's count over all its decks,
not a count for this commander; it is a comparison of card sets, not a rating.

### Tier list and builder work together

The tier list has a column "Favorit / Deck" and the same two buttons in its card window. The
star sets or clears only the favorite mark (`PUT /api/cards/{id}/favorite` with
`{favorite}`, `builder.set_favorite`): the page never sends a whole mark, so the note and the
exclusion stay as stored, also for a card outside the commander's pool. A mark never changes a
rating. "+ Deck" puts one copy into the target deck
("Ziel-Deck" and "Variante" in the page header, preset to the deck the builder had open),
"✓ im Deck" takes it out again. Both call
`POST /api/decks/{deck}/branches/{branch}/draft/card` with `{card_id, delta: 1 | -1}`
(`builder.change_draft_card`): the change starts from the working list (draft), else from the
saved state, and is written as a draft, never as a saved state. Read and write are one write
transaction (`BEGIN IMMEDIATE`), so changes at the same time lose no card; the page also sends
its clicks one after the other. The builder's limits hold on the server: only a card of the
commander's pool (in the collection, commander legal, inside the colour identity of the deck's
commanders; the button is disabled for other cards, for example in the global view), one copy, any number only for basic lands and "any number of cards named" cards, never
more than the free copies; the commander is refused. A refusal is HTTP 409 with a German sentence,
an unknown deck, variant or card is 404. The builder shows the draft when it is opened next; a
builder tab that was open in the background takes over the stored draft when it is looked at
again, but only while every change of its own has reached the server (changes are counted;
a change that is waiting, being sent or whose save failed keeps the tab's own list).

The builder shows the current tier of every card (pool tiles, deck list, card window) while
"Stufe zeigen" is ticked (default on, remembered in the browser as `studio.builder.show-tier`).
It is the tier of the strength index with the settings the tier list remembers; "–" means too
little data or not rated (commander, basic lands), never a low tier.

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
- Coverage of the strength index keeps its main definition (present weight over the weight of
  every weighted component, see the "Mindest-Datenlage" above): a source never imported for the
  commander still counts against a card. Not taken over from the follow-up branch (open
  Owner decision, tests of both sides contradict): a denominator of only the sources that have
  data for the commander. A filter card leaves the deck-universe component out of its
  denominator. The minimum number of signals never exceeds what the weighted components allow.
  The reason of a card is `NO_POSITIVE_WEIGHT` (no weight above 0), `NO_SOURCE_FOR_COMMANDER`
  (no weighted component has usable data for the commander), `NO_COMMANDER_SIGNAL`,
  `TOO_LITTLE_DATA` or `ENOUGH_DATA`; the tier follows the index as shown (rounded to one decimal), so a card shown at a cut has the tier of that cut. Other commanders
  known to the store are ordinary cards of the 99 and ranked by default; with
  `rank_other_commanders` off they are not ranked (tier `N`, `NOT_RANKED_OTHER_COMMANDER`).
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

### Which printing is shown (schema 15, #1342)

A card is pictured as the printing the collection itself holds when that printing is
identifiable, and as a plain standard printing otherwise — never as a full-art or
promo variant chosen by chance. The precedence is:

1. **Exact collection printing** (`EXACT_COLLECTION`): the inventory import reads the
   workbook's lot sheet into `card_printing` (one primary printing per card: the
   printing of the most copies; a reference that names no single printing stays
   `UNRESOLVED` and is counted, never guessed). `import-printings <workbook>
   --bulk <default-cards file>` resolves that printing's image addresses by matching
   locally against the public default-cards bulk file — nothing about the collection
   leaves the machine. The same
   precedence applies inside the Scryfall fold below: a candidate whose set and
   collector number (and language, when the reference names one) match an owned
   printing wins before every other criterion.
2. **Standard rule** (`STANDARD_RULE`): among the remaining candidates of an oracle,
   a standard printing beats a non-standard one. Standard means: not `full_art`, not
   `border_color = borderless`, no `showcase` or `extendedart` frame effect, and no
   promo marking (`promo` false, `promo_types` empty). Paper, non-digital, English,
   image present and commander-legal keep their previous order after that.
3. **Scryfall default** (`SCRYFALL_DEFAULT`): a single candidate, or no standard one,
   keeps the choice the criteria above make; the stored `printing_basis` says which
   of the three rules produced the picture, and the import report counts all three
   (`printings_exact` / `printings_standard` / `printings_default`).

The rule can only choose when the import actually sees several printings: it needs
the **default-cards** bulk file (all printings). The oracle-cards file carries one
preselected printing per oracle, so with it every card is `SCRYFALL_DEFAULT` unless
it matches an owned printing.

The image cache is bound to the chosen printing by an address stamp: next to each
cached file (`images/<oracle_id>-<face>.jpg`) lies a `<oracle_id>-<face>.stamp` file
holding the exact address the picture was downloaded from. A cached file whose stamp
names another address is replaced on the next fetch; a file without a stamp (cached
before the stamp existed) counts as valid and is stamped in place. `fetch-images`
is stricter: there an unstamped or differently stamped file is fetched and stamped
once, so after `import-printings` changes any picture, one `fetch-images` run brings
the whole cache onto the new printings.

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

Optional additions: `--tagger-roles "<CSV>"` (the tagger bulk `oracle_id,category,bulk_label` as a
full role snapshot of its own scope; only the Studio roles are taken, other categories are
counted; a file without a role row fails the step and changes nothing, a file that would remove
more than half of the scope's earlier claims is a `WARNING` and changes nothing unless `--force`
is given). The signal folders may also hold `edhrec_salt.csv` (published top list; a card not on
it is unknown, not 0) and `edhrec_<commander>_combos.csv` (EDHREC combo lists of the commander;
per card the number of combos and the largest deck count): layers `Signal edhrec_salt` and
`Signal edhrec_combo_decks`. `import-signals` needs `--commander` and takes `--append` (only add
and update; the default replaces each signal and commander the files write); CSV files with a
byte order mark are read; the reasons a stored value stayed unknown are counted per file
(`null_value_reasons`). Any failure of a step (a cut `.gz`, a file that is not a workbook) is
shown as `FAILED` with its type and message, and the table still follows; an unknown commander
exits with code 4 and names the commanders of the collection. `relink-corpus` (also run at the
end of `import-scryfall` and `import-decklists`) gives deck-list cards their oracle ids, so deck
statistics work in any import order.

`--data` is a global option and comes before `import-all`. Leave out every line you do not
have; the table then shows that layer as `MISSING`.


### Alles aus dem Repo importieren

Since the Owner decision of 2026-11-13 the repository holds all data (collection, corpus, roles,
EDHREC observations, Playgroup atlas, signals, rulings). `import-all --from-repo` runs every
importer from those files with no further file argument except the public card facts:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m commander_lab.studio --data "$env:LOCALAPPDATA\CommanderStudio" import-all `
  --commander "<Name des Commanders>" `
  --from-repo `
  --scryfall "<Pfad>\oracle-cards.jsonl.gz" `
  --expect-pool <erwartete Poolgröße>
```

`--scryfall` is required with `--from-repo`: the public card facts (Scryfall "Oracle Cards"
bulk file) are not in the repository and are never downloaded; without the option the command
stops before any step with a German message that says so. Steps, in order (each reported as
`IMPORTED`, `NOT_PROVIDED` when its repo folder is absent, or `FAILED`): collection (the workbook
is built into a temporary file from `data/research/collection_1655`; `--inventory` replaces it),
Scryfall card facts, roles (`roles_1655`; `--roles` replaces them), rulings, the deck list corpus
(`chulane_corpus`, all ten folders, then the oracle id mapping of its card rows; `--decklists`
replaces the corpus step), EDHREC observations (`edhrec_observations_chulane`, three parts),
Playgroup atlas (`playgroup`, three parts), signals (every signal folder below `data/research`
and `data/research` itself for the counted deck-list file) and marks. The completeness table
adds the layers "Korpus (Decks, alle)", "EDHREC-Beobachtungen (Themen)" and "Playgroup-Atlas".
The loaders are the functions of `studio/repo_import.py`; the scripts
`scripts/build_inventory_workbook.py`, `scripts/import_chulane_corpus.py` and
`scripts/map_corpus_oracle_ids.py` call them.

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
