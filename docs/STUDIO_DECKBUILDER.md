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
| `import-printings FILE.xlsx --bulk PATH` | collection printings (`card_printing`) matched locally against a Scryfall default-cards bulk file or folder | original |
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
| `ranking-check --commander NAME [--profile NAME \| --preset NAME] [--json]` | objective quality check of the strength-index ranking (`ranking_check.py`): Spearman correlation against counted deck lists, marginal cards at top, staples at bottom, thin coverage at top, tier and land distribution, leave-one-out stability, counter-checks against bracket 5 and EDHTop16, redundancy matrix, log-scale sensitivity | none (report) |
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

#### Where the old marks come from, and the per-row report

The importer takes a local file the Owner provides; the old HTML studio files themselves are
not in the repository and are not read. Two file formats are accepted (nothing else; a file
of another shape is refused with "not a marks file"):

1. The export of the old studio: one JSON object `{"app": "chulane-studio", "state": {...}}`.
   Only `state.fav` (card id or name to true) and `state.notes` (card id or name to text) are
   read. `wish`, `variants` and `tierOverride` are counted as ignored; a tier value is never
   imported. The Owner produces this file with the export function of his old studio page
   (it saves the page state as JSON). If the old page wrote another form, the Owner puts his
   favorites, exclusions and notes into the second format.
2. `studio-marks-1`: `{"format": "studio-marks-1", "marks": [{"card_name": "Forest",
   "favorite": true, "excluded": false, "note": "text"}]}`. A key an entry leaves out stays as
   it is. `card_id` is tried first, `card_name` second.

```
python -m commander_lab.studio import-owner-marks MARKS.json --rows
```

Without `--rows` the report holds counts only (entries, resolved, unresolved, conflicts,
changed). With `--rows` it adds one line per entry of the file (`row`, `name`, `status`,
`reason`):

| status | meaning |
|---|---|
| `IMPORTED` | the card was found; the mark is applied (or was already stored) |
| `NOT_FOUND` | no card of the Studio store has this id or name; nothing is applied |
| `CONFLICT` | card id and name name different cards, or the file states different values for one card; nothing of that card is applied |
| `IGNORED` | the entry states no favorite, exclusion or note |

The step only writes `card_mark`; observations, ratings, tiers and the strength index are not
touched (a marks file is private data and does not go into the repository). `import-all
--marks FILE` runs the same import inside the all-in-one run.

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
independent (commander name empty), the rubric (`rubric_h_mean`, `rubric_h_sd`, `rubric_raters`;
imported by `import-all --from-repo`, below) under the commander of its folder, and
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
   protect against small samples by itself, and `wilson_lower(0, n)` is exactly 0.0.
   The protection is the **minimum denominator per signal**: a share whose denominator is
   below the minimum is not ranked (component status `BELOW_MIN_DENOMINATOR`, a missing
   observation); the same minimum gate applies to `playgroup_observed` (default 200 games).
    Synergy (`synergy`) has default weight 0 (moved into its own layer column
    `commander_fit`); when weighted positively, negative synergy (`< 0`) is treated as
    `NEGATIVE_NEUTRAL` (missing observation / no penalty, never lowers the index). The combos
    component reads either the commander's EDHREC combo deck counts (`combo_source = "commander"`,
    default, commander-specific) or Commander Spellbook quality (`combo_source = "spellbook"`,
    the mean of the card's percentile ranks in variant count, two-card variant count and
    partners in the collection via `strength.combo_quality`; with the shell file of #1366
    imported, in shell count, two-card shell count and commander shell count instead, see
    "Combo shells"); that value is then ranked like every other component.
2. Share signals become a scaled value in `0..1` according to `share_scale` (recommended
   `share` = $\sqrt{v / v_{\max}}$ within the comparison group, preserving the magnitude gap
   between 3 % marginal cards and 60 % staples so long zero tails do not push marginal cards to
   percentile `0.89`; `rank` = percentile rank `0..1`, bit-identical to the legacy ranking).
   Non-share components (`synergy`, `combos`, `playgroup_observed`, and weighted rating layers)
   always use percentile ranks (`0..1`). The `rubric` component (below) is neither: its
   `(H - 1) / 9` is used directly as the `0..1` score, so its magnitude is kept. The comparison
   group is the whole legal pool
   (recommended) or the card's type group, mana-value band or function role; a group of fewer
   than 5 cards falls back to the whole pool and the card says so. Lands and spells are scaled
   apart (`separate_lands`, recommended on, #1353 part A): $v_{\max}$ and every percentile
   rank are taken within the group "Länder" and within the group "Zauber" (every non-land),
   so a land does not set the scale of the spells and the other way round; a group with
   fewer than 5 valued cards keeps the joint scale and says so in the row. A comparison group
   by type, mana band or function never mixes the two either. Ties share the mean rank. The
   commander card and the basic lands are not ranked by default (tier `N`, "nicht
   bewertet"); the setting can include them. Cards the universe requires (card filter,
   `must_contain`) are filter cards: status `FILTER_CARD`, not ranked, labelled
   "Filterkarte".
3. Index = weighted mean of the present scaled values x 100 (one decimal); a missing component
   is left out and the weights are renormalised. `coverage` = weight of present components /
   weight of all components with a weight above 0.
4. Tier `U` ("zu wenig Daten") when coverage is below `min_coverage` or fewer than
   `min_components` weighted components are present, or (rule `require_commander_signal`) no
   commander-specific component has a ranked value; otherwise S/A/B/C/D by the index cuts
   (default 47/17/9/4 since #1358, editable; before 70/55/35/20; legacy rank-mode cuts were
   90/75/55/35). A card absent from a source is a missing observation: it
   lowers the coverage, never the percentile. The setting "missing value" decides per share
   signal what a card without a value does: `skip` (the component is left out) or `lowest`
   (counts as the lowest score, 0). Recommended since #1350: `lowest` for the commander
   inclusion and the bracket inclusion (EDHREC lists every card above its listing threshold,
   so "not listed" means "below the threshold"), `skip` for the deck universe (it already
   counts a card in no deck as a real 0 of N). With `skip` and
   `min_coverage` 0 a card with a single weak signal can outrank a card listed by a source at
   1 of 755 decks, which is why the recommendation is a minimum (0.25, see below).
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
universe 2, synergy 0, tournament lists 1, tournament conversion 1, global inclusion 1, combos 1, Playgroup observation 0, rubric 3.5, simulation 0), the
bracket (`core`, `upgraded`, `optimized`, `cedh`, `none`), the combo source (`combo_source`: `commander` default, or `spellbook`), the universe profile (the page uses
the Universum selector), the comparison group (`rank_group`: `pool`), the share measure
(`share_measure`: `wilson`), the share scale (`share_scale`: `share`, or `rank` for pure percentile ranks), lands apart from spells (`separate_lands`: on), the minimum denominators (`min_denominators`: EDHREC 30,
tournament 20, conversion 20, playgroup 200; the deck-universe minimum is the universe's own `min_universe`), the missing
value per share signal (`lowest` for commander and bracket inclusion, `skip` for the deck universe), commander and basics (`rank_commander_and_basics`: off), other commanders in the pool (`rank_other_commanders`: on, ranked like any card),
`min_coverage` (0.25, "Mindest-Datenlage"), `min_components` (2), `universe_source` (`auto`), `require_commander_signal` (on) and the editable cuts (`tier_cuts` 47/17/9/4).
The page also filters by tier (S/A/B/C/D/U) and sorts by the percentile of any single
component. Presets (weights commander inclusion / bracket / deck universe / synergy / tournament /
conversion / global / combos / Playgroup observation; simulation is 0 in all):
Ausgewogen 3/2/2/0/1/1/1/1/0 (the defaults), Commander-nah 3/2/3/0/1/1/1/0/0 (bracket upgraded),
Turniernah 1/2/2/0/3/1/1/1/0 (bracket cedh); the rubric weight is 3.5 / 4 / 2.5 (see the rubric
section). Every preset counts the deck universe, the most
commander-specific source. The Playgroup observation (`playgroup_observed`, import minimum
25 games, index minimum 200 games, shrunk towards zero via $n / (n + 200)$) is commander
independent: it is not one of the signals `require_commander_signal` asks for. Owner settings are saved by name. Simulation results
do not count in the tier list and are for now neither collected nor processed for it (Owner
decision B11, 2026-11-12): the `simulation` weight stays as an option, is 0 in the defaults
and in every preset, and the component is `NOT_COLLECTED`. The page's layer count ("Schichten",
sort key and coverage list) does not count the simulation layer either.

The Owner's marks (favorite, excluded, note) never enter the index (Owner decision B4;
pinned by a test). On the page the settings panel "Stärke-Index" holds preset, bracket, one
input per weight, the minimum coverage and a named save; the choice is remembered in the
browser. The new column sorts by index with tier U last; the card drawer lists every
component with value, numerator/denominator, Wilson bound, percentile, weight and status.
The tier page has a filter "Länder und Zauber / nur Zauber / nur Länder" and shows the tier
counts of lands and spells next to the pool total.

Routes: `POST /api/strength` (body `commander` plus at most one of `preset`, `profile`,
`settings`; needs the `X-Studio` header like every non-GET route, 422 without commander),
`GET /api/strength/presets`, `GET /api/strength/profiles`,
`GET|PUT|DELETE /api/strength/profiles/{name}`.

The page names two different things and never mixes them: "Stärke-Index (Schätzung aus
Nutzungsdaten)" (this index) and "Ergebnis aus Partien (noch nicht bewertet)" (the outcome
evidence, `UNRATED`).

### Strength index v3: purely empirical ("Tierliste v3", #1364)

This section supersedes the weights, scale, cuts and missing-value defaults named above (the
older text keeps the formula steps and the history). Owner decisions E1 to E5 of 2026-11-15.

**What counts.** Only objective data with provenance. The rubric (`rubric`) is subjective: its
weight is 0 in the defaults and in every preset, the component, importer and column stay
(label "subjektiv, Gewicht 0, kein objektives Signal"). Simulation, layers, favorites,
exclusions and notes never count. TopDeck tournament lists and conversion keep weight 0.

**Weights** (Ausgewogen / Commander-nah / Turniernah): `deck_universe` 4.0 / 4.5 / 2.5,
`corpus_tuned` 1.5 / 1.0 / 2.5, `corpus_log_lift` 1.0 / 2.0 / 0.5, `corpus_bracket_slope`
1.0 / 0.5 / 2.0, `global_inclusion` 1.0 / 0.5 / 0.5, `tournament` 0.5 / 0.0 / 2.0,
`edhrec_theme_reach` 0.5 / 1.0 / 0.0, `combos` 0.5 / 0.5 / 1.0; `commander_inclusion` 3 and
`bracket_inclusion` 2 are requested but see rule E2.a; `playgroup_observed`, `rubric`,
`simulation` 0.

**New components** (`corpus_signals.py`, all from the counted local corpus of the commander,
`DERIVED_DESCRIPTIVE`, numerator and denominator shown; Chulane-only sources are
`NOT_COLLECTED` without a coverage penalty for other commanders):

- `corpus_tuned`: decks with the card over the decks of the brackets 4 and 5.
- `corpus_log_lift`: $\log_{10}$ of the card's corpus share over its global EDHREC inclusion,
  damped by $n/(n+5)$ on the hit count, capped at $\pm 2$, mapped to `0..1` by $(x+2)/4$ (0.5 =
  neutral); no value for 0 hits (a tiny count cannot score high). The index score is
  $\max(0, 2v - 1)$: only an above-neutral lift adds, neutral or below counts 0 (a value of 0.3
  would otherwise still raise a card whose other scores are near 0). The row keeps the raw
  value `v` and the signed log value in its note.
- `corpus_bracket_slope`: the same damped log ratio of the share in brackets 4+5 against
  bracket 2 (half-deck smoothing), only with at least 5 hits in total, with the same
  $\max(0, 2v - 1)$ index score.
- `tournament`: the EDHTop16 play rate (numerator derived as `round(value * denominator)` when
  the published row has only the rate; the stored row stays NULL) pooled with the corpus
  bracket 5 as one share (sum of numerators over sum of denominators). A card without an
  EDHTop16 row counts with bracket 5 alone (not listed is unknown, never 0).
- `edhrec_theme_reach`: the highest inclusion share of the card over the EDHREC theme pages of
  the commander, each theme share shrunk first (prior from all theme rows) and then the maximum
  of the posterior means taken, so a small noisy theme does not win on its raw share (base page and the bracket or price variants `core`, `upgraded`, `optimized`,
  `cedh`, `budget`, `exhibition` left out; a theme row needs the EDHREC minimum denominator).

**Rule E2.a (`strength.apply_corpus_rule`, shown in the result as `weight_rule`).** With a
counted local corpus of at least `min_universe` decks (30) the weights of `commander_inclusion`
and `bracket_inclusion` are 0 (rule `CORPUS_ZERO`, requested and effective weights are both
returned). Without such a corpus the EDHREC weights apply (`EDHREC_FALLBACK`). The setting
`edhrec_with_corpus` keeps them (`EDHREC_KEPT`).

**Empirical Bayes.** A share with a denominator below 500 (`EB_MAX_DENOMINATOR`) is shrunk to
the Beta-Binomial posterior mean $(k + m M)/(n + M)$; prior mean $m$ and strength $M$ come from the
pool per component by the method of moments ($M$ clamped to 2..200, at least 5 cards) and are
reported (`shrinkage`, `prior_mean`, `prior_strength` per component row). Larger denominators
(the 2,823 counted decks) keep the Wilson path; the minimum-denominator gates
(`BELOW_MIN_DENOMINATOR`) are unchanged.

**Zero counts (E4.b, switchable E4.a).** 0 of N in the complete counted corpus is a counted
value: status `ZERO_COUNT`, it counts fully, and a card whose only commander evidence is that
zero plus global inclusion gets tier `D` (setting `zero_count_tier`: `D` default, `U` for E4.a,
reason `ZERO_COUNT_ONLY`). A card an EDHREC source does not list is `NO_VALUE` with
`NOT_LISTED`; the `missing_value` default is `skip` for every signal again. Tier `U` is only for
real gaps and always carries a reason code.

**Scale and cuts (E5.a).** `share_scale = "log"` (default): $\ln(1 + k v)/\ln(1 + k v_{\max})$
with $k = 150$ (`strength.LOG_SHARE_K`), lands and spells apart, comparison group `pool`, cuts
54 / 35 / 20 / 5 (re-derived once in #1366, see "Tier cuts of #1366"; Stand #1371: 72 / 50 / 28 / 14).
`rank_other_commanders` stays on (geprüft und bestätigt 2026-11-15).

**Saved profiles on reload.** A profile stores only the keys it was saved with; they stay
(an old rubric weight 3.5, `share_scale`, cuts, `missing_value`). Every key it lacks takes the
new default, so the E2.a rule applies to old profiles too (their EDHREC weights become 0
effective as soon as the corpus exists) and the new components enter with their default weights.
Re-save the profile or press "Empfohlene Werte" to adopt the new defaults completely. The
result says so: a loaded profile with a positive rubric weight gets the notice "subjektives
Signal aktiv", and stored EDHREC weights that the corpus rule sets to 0 are named with stored
and effective value (`strength_view.compute(saved_weights=...)`, route `POST /api/strength`).

**Ranking-check additions** (sections 7 to 9 of the text, keys `counter_checks`, `redundancy`,
`sensitivity`, `weight_rule`, `shrinkage` in the JSON): Spearman of the index against the
corpus bracket 5 share and against the EDHTop16 play rate (spells and lands apart, unknown
where no value exists, never 0). These counter-checks OVERLAP with the index (bracket 5 is a
subset of the corpus and feeds `tournament`, EDHTop16 feeds `tournament`), so each carries a
held-out variant (`held_out`, text row "ohne Überlappung"): the index recomputed with the
overlapping components at weight 0 (bracket 5: `deck_universe`, `corpus_tuned`, `tournament`,
`corpus_bracket_slope`; EDHTop16: `tournament`) against the same reference; it covers only the
cards that keep a value (564 of 922 for bracket 5). `corpus_log_lift` stays in both (bracket 5
is a small part of its whole-corpus share). A redundancy matrix (Spearman between the rank values of the
active weighted components over the cards where both have a value, pairs above 0.90 flagged as
double counting); and the tier counts for $k$ = 100 / 150 / 200.

Measured on the repository store, **Stand #1371** (cuts 72 / 50 / 28 / 14; the table of #1366 with
the new cuts follows below) (Chulane pool 927, 922 ranked, 2,823 counted lists; bracket 5
has 267 decks, brackets 4+5 have 1,155; only 16 pool cards have an EDHTop16 row), after the
review fixes (lift and slope above neutral only, theme reach shrunk per theme):

| Metric | `Ausgewogen` | `Commander-nah` | `Turniernah` |
|---|---|---|---|
| Spearman all / spells / lands vs counted lists, before #1364 | `0.7388 / 0.7135 / 0.9465` | `0.7481 / 0.7230 / 0.9543` | `0.7627 / 0.7373 / 0.9572` |
| Spearman all / spells / lands vs counted lists, after | `0.9226 / 0.9117 / 0.9891` | `0.9368 / 0.9276 / 0.9902` | `0.9282 / 0.9182 / 0.9894` |
| Randkarten oben, before / after | `59 / 134` / `0 / 45` | `62 / 139` / `0 / 44` | `66 / 145` / `0 / 34` |
| Stammkarten unten, after | `0 / 27` | `0 / 27` | `0 / 27` |
| Counter-check bracket 5 (n 267), overlapping, all / spells / lands | `0.6281 / 0.5798 / 0.9120` | `0.6256 / 0.5773 / 0.9098` | `0.6452 / 0.5963 / 0.9255` |
| Counter-check bracket 5, held out (564 cards) | `0.6699 / 0.6174 / 0.9025` | `0.6577 / 0.6066 / 0.8915` | `0.6639 / 0.6102 / 0.8911` |
| Counter-check EDHTop16 (16 spells), overlapping / held out | `0.6406 / 0.6381` | `0.5845` / no held-out (tournament weight 0) | `0.8059 / 0.7861` |
| Tiers `S / A / B / C / D / U / N`, after | `8 / 37 / 49 / 53 / 775 / 0 / 5` | `7 / 37 / 52 / 48 / 778 / 0 / 5` | `8 / 26 / 36 / 53 / 799 / 0 / 5` |
| Leave-one-out, tier changes of 927 per weighted signal | `deck_universe` 74, `corpus_tuned` 12, `corpus_log_lift` 29, `corpus_bracket_slope` 33, `tournament` 15, `edhrec_theme_reach` 12, `global_inclusion` 18, `combos` 1 | `deck_universe` 86, `corpus_tuned` 12, `corpus_log_lift` 75, `corpus_bracket_slope` 20, `edhrec_theme_reach` 20, `global_inclusion` 6, `combos` 0 | `deck_universe` 49, `corpus_tuned` 27, `corpus_log_lift` 7, `corpus_bracket_slope` 58, `tournament` 28, `global_inclusion` 11, `combos` 1 |
| Tier changes for $k$ 100 / 200 against 150 | `24 / 25` | `13 / 22` | `18 / 19` |

No pair of active components exceeds $r$ = 0.90 (`deck_universe` against `corpus_tuned`:
0.8481), so `corpus_tuned` stays the share in brackets 4+5. Open against the acceptance
criteria: the `combos` signal changes 0 to 1 tiers when left out (a value for only 13 pool
cards; 0 in `Commander-nah`), and the distribution is bottom-heavy with the cuts
72 / 50 / 28 / 14 (775 to 799 cards are `D`, after the lift and slope fix more than before it);
the cuts are re-derived below.
The agreement with the counted lists stays above 0.90 for spells and lands in all presets.

**Confidence and borderline mark (#1365).** Every ranked card carries `confidence` (0..1),
`confidence_level` and a mark `borderline`:

- `confidence` = `coverage` $\times$ $\sum_i w_i \, n_i/(n_i+30) \,/\, \sum_i w_i$ over the weighted
  components with a value and a denominator $n_i$ (a counted zero included; `strength.CONFIDENCE_K`
  = 30). Coverage is the weight share of the signals that have a value; a large denominator
  (the 2,823 counted decks) counts almost fully, a small one (a theme page with 40 decks) about
  0.57. A card without an index has no confidence (`null`). It is a hint about the evidence, not
  about the card, and it never changes the index or the tier.
- `confidence_level`: `high` from 0.60, `medium` from 0.35, else `low`.
- `borderline` is true when the index lies strictly closer than `borderline_distance` index
  points to a tier cut (S, A, B, C); `borderline_cut` names the nearest cut, `cut_distance` the
  distance. The setting `borderline_distance` (0..50, recommended 2, 0 = off) is in the settings
  panel under "Tier-Grenzen". A card with tier `U` or `N` is never borderline.

The result also carries `tier_counts_by_kind` (`spells` and `lands`, the same keys as
`tier_counts`), `unknown_breakdown` (`total`, `zero_count` = U cards with reason
`ZERO_COUNT_ONLY`, i.e. "gezählt 0 von N" (only with `zero_count_tier` = U), `missing_data` = the
others with their `by_reason` codes, and `denominator` = the deck count of those cards' own counted-zero rows, `null` when they name more than one) and
`borderline_count`. Each card has `is_land`.

#### Tier cuts of #1366

The bottom-heavy distribution of Stand #1371 (775 to 799 of 927 cards in `D`) is corrected once,
with a rule fixed in advance, applied to the default `Ausgewogen` index and not tuned to any
named card:

- **C** = the smallest whole number above the highest index of any card whose only commander
  evidence is a counted 0 (every weighted commander-specific component is `ZERO_COUNT`: 358 pool
  cards, highest index 4.2 at Stand #1371; 357 pool cards, highest index 4.1 after #1390/#1395),
  so these cards all stay `D`: 5.
- **A** = the smallest whole number that keeps every card with less than 5 % in the counted lists
  out of `S` and `A` (the highest index of such a card is 34.4): 35.
- **S** = the whole number nearest to 3 % of the 857 ranked non-lands in `S` (25.7 cards), never
  below A + 1: 54 (26 cards).
- **B** = the rounded midpoint of A and C: 20.

Result **54 / 35 / 20 / 5**, the same for lands and for all presets (Stand #1371: 72 / 50 / 28 / 14).
The rule gave no degenerate result (A 35 is below the S target 54). A first quantile rule
(cumulative shares 3 / 13 / 35 / 65 %, cuts 54 / 14 / 3 / 1) was discarded: it put 67 of 147
`S`/`A` cards below 5 % in the counted lists and lifted 54 zero-count cards out of `D`.
Measured on a store rebuilt from the repository (`import-all --from-repo --expect-pool 927`,
2,839 counted lists after #1390 and #1395):

| Metric | `Ausgewogen` | `Commander-nah` | `Turniernah` |
|---|---|---|---|
| Tiers `S / A / B / C / D / U / N`, Stand #1371 (72 / 50 / 28 / 14, 2,823 lists) | `8 / 37 / 49 / 53 / 775 / 0 / 5` | `7 / 37 / 52 / 48 / 778 / 0 / 5` | `8 / 26 / 36 / 53 / 799 / 0 / 5` |
| Tiers `S / A / B / C / D / U / N`, Stand #1366 (54 / 35 / 20 / 5, 2,839 lists) | `38 / 33 / 47 / 151 / 653 / 0 / 5` | `38 / 37 / 46 / 129 / 672 / 0 / 5` | `27 / 29 / 45 / 106 / 715 / 0 / 5` |
| Lands `S / A / B / C / D` (65), Stand #1366 | `12 / 13 / 9 / 13 / 18` | `11 / 14 / 9 / 12 / 19` | `6 / 11 / 13 / 12 / 23` |
| Spearman all / spells / lands vs counted lists (unchanged by the cuts) | `0.9235 / 0.9115 / 0.9912` | `0.9377 / 0.9277 / 0.9919` | `0.9291 / 0.9182 / 0.9911` |
| Randkarten oben, Stand #1371 / #1366 | `0 / 45` / `0 / 71` | `0 / 44` / `2 / 75` | `0 / 34` / `0 / 56` |
| Stammkarten unten (> 30 %, tier C or D) | `0 / 27` | `0 / 27` | `0 / 27` |
| Cards with only a counted 0 outside `D` (357 cards) | 0 | 0 | 0 |
| Leave-one-out, tier changes of 927 per weighted signal, Stand #1366 | `deck_universe` 116, `corpus_tuned` 41, `corpus_log_lift` 49, `corpus_bracket_slope` 42, `tournament` 17, `edhrec_theme_reach` 9, `global_inclusion` 64, `combos` 2 | `deck_universe` 138, `corpus_tuned` 20, `corpus_log_lift` 94, `corpus_bracket_slope` 20, `edhrec_theme_reach` 25, `global_inclusion` 25, `combos` 1 | `deck_universe` 80, `corpus_tuned` 48, `corpus_bracket_slope` 62, `corpus_log_lift` 18, `tournament` 36, `global_inclusion` 27, `combos` 2 |
| Tier changes for $k$ 100 / 200 against 150, Stand #1366 | `46 / 38` | `36 / 40` | `45 / 36` |

`Commander-nah` has 2 marginal cards in `S`/`A` (the preset weights differ from the default the
cuts were derived on); the other presets have none.

#### Combo shells (#1366)

The Spellbook count of a card was a count of variants: a combo whose flexible slot has many
printed equivalents inflates it (Shrieking Drake: 397 variants in the link file, 2 qualifying
shells; the three bounce-land recipes of the Chulane combo are one shell). `data/research/deckbuilder_1655/spellbook_shells.csv` counts distinct combos ("shells")
instead, built by `scripts/build_spellbook_shells.py` from the public Commander Spellbook bulk
export (`variants.json.gz`; only the variant ids of the committed link file are looked up locally
and deterministically from the downloaded bulk file; source, date, version and SHA-256 are in the
README of the folder). Rules (module `spellbook_shells`):

- A shell is the combo behind a variant (`of`); combos that share a variant are one shell
  (union-find, named by the smallest combo id), so the result does not depend on the order of `of`.
- A variant qualifies when its colour identity fits WUG (colourless `C` fits) and every card it
  uses is in the Chulane pool of 927. A shell with a qualifying variant counts 1, however many
  variants it has; outside WUG or with a partner outside the pool it counts 0 (a counted 0).
- 2 cards against 3 or more (template slots count as cards), and commander involvement
  (`mustBeCommander`, or the commander card itself is in the combo).
- The importer reads the file like every other signal (`spellbook_shells`, `spellbook_two_card_shells`,
  `spellbook_commander_shells`, scoped by `commander_name` to the imported commander, SHA-256 of
  the file in the source row; a re-import writes the same rows and the same source). With these
  signals stored for the active commander, the `spellbook` combo source ranks the shell parts
  (`signal: spellbook_shells`) and the variant count is only shown; for another commander without
  its own shell rows it falls back to the variant mixture (`spellbook_variants`). The detail row
  of a card shows "n Combo-Shells (davon a mit 2 Karten, b mit 3+ Karten, c mit
  Commander-Beteiligung)" or explicitly marks missing/out-of-bounds breakdowns as `unbekannt`.

Measured result, bulk version 7.4.2: of 123,149 variants only 4 have all cards in the pool and a
fitting identity, 2 shells (the Chulane bounce-land recipe with Tireless Provisioner and Shrieking
Drake, the Lonis recipe with Academy Manufactor), 8 cards with a shell. The default combo source
stays `commander` (13 cards with an EDHREC combo row), so the default tier list does not move; with
`combo_source = "spellbook"` (counted zeros give all 927 cards a value, measured on 2,839 counted lists):

| `combo_source = "spellbook"` | `Ausgewogen` | `Commander-nah` | `Turniernah` |
|---|---|---|---|
| Distinct combo values, variants / shells | `133 / 4` | `133 / 4` | `133 / 4` |
| Spearman all vs counted lists, variants / shells (counted zeros score 0) | `0.8657 / 0.9235` | `0.8692 / 0.9388` | `0.8283 / 0.9303` |
| Leave-one-out `combos`, tier changes, variants / shells | `143 / 23` | `144 / 15` | `178 / 37` |
| Tiers `S / A / B / C / D`, shells | `32 / 36 / 46 / 145 / 663` | `33 / 38 / 48 / 128 / 675` | `24 / 25 / 43 / 101 / 729` |

Top of the combos value before (variants): Shrieking Drake, Adrix and Nev, Whitemane Lion,
Lightning Greaves, Clever Impersonator, Kor Skyfisher, Rite of Replication (cards whose partners
are mostly not in the pool); after (shells): Shrieking Drake (2 shells), then Azorius Chancery,
Chulane, Selesnya Sanctuary, Simic Growth Chamber, Tireless Provisioner (1 shell each with the
commander), then Academy Manufactor and Lonis (1 shell); every other card holds a counted 0.
The signal is therefore almost empty for this pool and stays a weak one under `Ausgewogen`;
that is a property of the owned pool, not of the source.

A counted 0 (no qualifying shell or variant) scores 0 in the combos component, below every card
that has a combo, like a card without an EDHREC combo row counts for nothing under the default source
(`strength.zero_floor_ranks`, `combo_quality`); before, the tie-mean rank of the zero group (about
0.5 for 919 of 927 cards) lifted every card above the low cuts. Under the default source
(`commander`, 13 cards, no zero values) the ranks are unchanged.

### Rating layers ("Bewertungsebenen")

Additional, objectively derivable layers that rank cards next to the strength tier. Each is
its own column on the tier list page (a per-viewer column chooser, remembered in the browser;
each column sorts by its percentile; a filter for the pod scaling class) and a small table in
the card window of the tier list and of the builder. A layer never changes the tier on its own:
the settings group "Zusätzliche Ebenen" gives each of four layers an optional weight in the
strength index, **default and recommendation 0** (all three presets keep 0). With every weight
at 0 the tier and the index of every card are bit-identical to a run without layers (pinned by
`tests/unit/test_studio_layers_view.py`). A weighted layer joins like any other component: its percentile among the ranked
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
damped value. "Passt zum Commander" (`commander_fit`) shows EDHREC's per-commander synergy as a
column only (without index weight). A weighted `pod_scaling` has a value for every card with oracle text, so it counts
as a present component for nearly every card and raises their coverage: a card can pass the
"Mindest-Datenlage" on a text rule alone. That is why its recommended weight stays 0.

| Layer (key) | Source | Denominator | Kind |
|---|---|---|---|
| "Großpod-Wirkung" (`pod_scaling`) | oracle text of all faces | none | derived by rule, no measurement |
| "Tempo" (`tempo`) | Playgroup atlas `on_curve_count` | `on_curve_denominator` | measured correlation |
| "Ausspielquote" (`playability`) | `drawn_to_played_pct` | `ever_drawn_n` | measured correlation |
| "Standfestigkeit" (`staying`) | `battlefield_survival_pct` | `reached_battlefield_n` | measured correlation, permanents only |
| "Sieg-Abstand" (`win_gap`) | the Playgroup observed gap | `winrate_when_cast_n` | measured correlation, column only |
| "Passt zum Commander" (`commander_fit`) | `edhrec_commander_synergy` | none (percentage-point deviation) | measured correlation, column only |

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
`playgroup_observed`: import minimum 25 games in which the card was cast, shrinkage
`gap * n / (n + 200)` (`OBSERVED_SHRINKAGE = 200`, index minimum 200 games); there is no second
implementation. It has no weight of its own, because the index can optionally count it (a second
weight would count it twice); it is a column only.

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

### Prüfzahlen für die Rangfolge (`ranking-check`, #1349)

`ranking_check.check_ranking` (pure function) and the command
`python -m commander_lab.studio --data <ordner> ranking-check --commander "Chulane, Teller of Tales" [--profile <name> | --preset <name>] [--json]`
report six objective diagnostic figures (plus the counter-checks, redundancy matrix and log-scale sensitivity of Tierliste v3, above) for any strength-index setting (both as human-readable
German text and as JSON `studio-ranking-check-1`):

1. **Agreement with the counted deck lists (Spearman $r$):** rank correlation between the
   strength index and the card's share in the counted lists of the commander (denominator
   2,823 for Chulane), over all ranked cards (`S`–`D`), for non-lands and for lands. Because
   the counted lists are themselves an index signal, the report labels this figure explicitly
   as a plausibility anchor ("wird für diesen Commander wirklich gespielt"), never as a proof
   of causal card strength.
2. **Marginal cards at the top ("Randkarten oben"):** count, denominator (all cards in `S` or
   `A`) and names of cards in `S` or `A` with strictly less than 5 % share in the counted
   lists.
3. **Staples at the bottom ("Stammkarten unten"):** count, denominator (all cards above 30 %
   share) and names of cards with strictly more than 30 % share in the counted lists that
   stand in `C` or `D`.
4. **Thin data coverage at the top ("Dünne Datenlage oben"):** count and signal-count
   breakdown of cards in `S` or `A` with fewer than 5 present weighted signals.
5. **Tier distribution ("Stufen-Verteilung"):** per tier (`S, A, B, C, D, U, N`) the card
   count, pool denominator, non-land and land counts, and land share (`unbekannt` / `null`
   when a tier holds 0 cards).
6. **Leave-one-out stability ("Stabilität"):** for each active weighted signal, how many pool
   cards change tier when that signal alone is given weight 0, plus the single signal with the
   largest impact.

Baseline on the repository store (`import-all --from-repo`, Chulane pool 927, 922 ranked
cards, 2,823 counted lists, before any index change of #1350–#1353):

| Metric | `Ausgewogen` (default) | `Commander-nah` | `Turniernah` |
|---|---|---|---|
| Spearman $r$ (all ranked, 922 / 922) | `0.8785` | `0.9182` | `0.8956` |
| Spearman $r$ (non-lands, 857 / 857) | `0.8809` | `0.9217` | `0.8963` |
| Spearman $r$ (lands, 65 / 65) | `0.5322` | `0.5024` | `0.5415` |
| Randkarten oben (`S`/`A` with `< 5 %` share) | `65 / 87` | `130 / 164` | `65 / 94` |
| Stammkarten unten (`> 30 %` share in `C`/`D`) | `0 / 27` | `0 / 27` | `2 / 27` (`Counterspell`, `Canopy Vista`) |
| Dünne Datenlage oben (`S`/`A` with `< 5` signals) | `72 / 87` (`4 Signale: 72`) | `145 / 164` (`2 Signale: 144, 3 Signale: 1`) | `72 / 94` (`4 Signale: 72`) |
| Tier counts `S / A / B / C / D / U / N` (of 927) | `6 / 81 / 257 / 256 / 322 / 0 / 5` | `30 / 134 / 221 / 171 / 366 / 0 / 5` | `9 / 85 / 254 / 253 / 321 / 0 / 5` |
| Land share in `S / A / B / C / D` | `33.3 % / 12.3 % / 12.8 % / 7.0 % / 0.6 %` | `46.7 % / 13.4 % / 9.0 % / 4.7 % / 1.4 %` | `22.2 % / 14.1 % / 13.0 % / 6.3 % / 0.6 %` |
| Largest leave-one-out tier impact | `deck_universe` (`879 / 927`), `combos` (`578 / 927`), `global_inclusion` (`560 / 927`) | `deck_universe` (`889 / 927`), `global_inclusion` (`857 / 927`) | `deck_universe` (`884 / 927`), `combos` (`581 / 927`), `global_inclusion` (`561 / 927`) |

#### Share scaling (`share_scale`: `share` vs `rank`, #1351)

In the Chulane pool (922 ranked cards), 564 cards have at least 1 of 2,823 counted lists and 358 have exactly 0 of 2,823; 756 cards are below 1 % (corrected 2026-11-15, #1364: an earlier version of this sentence said "756 cards have 0 of 2,823"). Under pure
percentile ranks (`share_scale = "rank"`), the zeros and near-zeros share a low mean rank (`0.409`, `377.5 / 921`, as measured then),
and a card played in only 3 % of decks jumps to percentile `0.89`, right next to a 60 % staple.
Consequently, among the 166 cards actually played in $\ge 1\,\%$ of counted lists, the rank-mode
index had a slightly negative Spearman correlation (`r = -0.0357`) with counted-list share, and
65 of 87 `S`/`A` cards had `< 5 %` share (`Psychosis Crawler` 4.1 %, `Mystic Sanctuary` 3.1 %,
`Rite of Replication` 1.6 % in Tier `S` ahead of `Sol Ring` 73.2 % and `Llanowar Elves` 60.0 %).

Four share-scaling candidates were evaluated against `rank` on the 927-card Chulane store:

| Variant (`Ausgewogen`) | Cuts `S/A/B/C` | Spearman $r$ (all 922) | Spearman $r$ (lands 65) | Spearman $r$ ($\ge 1\,\%$ share, $n=166$) | Spearman $r$ ($\ge 5\,\%$ share, $n=84$) | Randkarten oben (`< 5 %` in `S`/`A`) | Stammkarten unten (`> 30 %` in `C`/`D`) | Dünne Datenlage oben (`< 5` signals in `S`/`A`) | Tier counts `S/A/B/C/D` |
|---|---|---|---|---|---|---|---|---|---|
| `rank` (legacy) | `90/75/55/35` | `0.8785` | `0.5322` | `-0.0357` | `0.5020` | `65 / 87` | `0 / 27` | `72 / 87` | `6 / 81 / 257 / 256 / 322` |
| `linear` ($v / v_{\max}$) | `70/55/35/20` | `0.6771` | `0.8400` | `0.5153` | `0.7851` | `0 / 2` | `2 / 27` | `0 / 2` | `1 / 1 / 46 / 199 / 675` |
| `blend` ($0.5\,\text{rank} + 0.5\,v/v_{\max}$) | `70/55/35/20` | `0.8588` | `0.6748` | `0.2218` | `0.7082` | `36 / 59` | `0 / 27` | `38 / 59` | `12 / 47 / 266 / 275 / 322` |
| `log` ($\log_{10}(1 + 9 v / v_{\max})$) | `70/55/35/20` | `0.7520` | `0.8414` | `0.7871` | `0.9260` | `0 / 27` | `0 / 27` | `0 / 27` | `11 / 16 / 97 / 267 / 531` |
| **`share` ($\sqrt{v / v_{\max}}$, recommended)** | **`70/55/35/20`** | **`0.8013`** | **`0.8423`** | **`0.7589`** | **`0.9063`** | **`0 / 20`** | **`0 / 27`** | **`0 / 20`** | **`8 / 12 / 103 / 272 / 527`** |

Across all three presets after `#1351` (`share_scale = "share"`, `tier_cuts = 70 / 55 / 35 / 20`):

| Metric | `Ausgewogen` (default) | `Commander-nah` | `Turniernah` |
|---|---|---|---|
| Spearman $r$ (all ranked, 922 / 922) | `0.8013` | `0.9408` | `0.8024` |
| Spearman $r$ (non-lands, 857 / 857) | `0.7867` | `0.9439` | `0.7878` |
| Spearman $r$ (lands, 65 / 65) | `0.8423` | `0.8535` | `0.8424` |
| Randkarten oben (`S`/`A` with `< 5 %` share) | `0 / 20` | `0 / 19` | `0 / 18` |
| Stammkarten unten (`> 30 %` share in `C`/`D`) | `0 / 27` | `0 / 27` | `0 / 27` |
| Dünne Datenlage oben (`S`/`A` with `< 5` signals) | `0 / 20` | `0 / 19` | `0 / 18` |
| Tier counts `S / A / B / C / D / U / N` (of 927) | `8 / 12 / 103 / 272 / 527 / 0 / 5` | `5 / 14 / 37 / 87 / 779 / 0 / 5` | `8 / 10 / 103 / 274 / 527 / 0 / 5` |
| Land share in `S / A / B / C / D` | `12.5 % / 33.3 % / 9.7 % / 6.2 % / 6.3 %` | `20.0 % / 28.6 % / 18.9 % / 6.9 % / 6.0 %` | `12.5 % / 30.0 % / 10.7 % / 5.8 % / 6.5 %` |
| Largest leave-one-out tier impact | `combos` (`182 / 927`), `synergy` (`157 / 927`), `deck_universe` (`48 / 927`) | `synergy` (`96 / 927`), `deck_universe` (`40 / 927`) | `combos` (`180 / 927`), `synergy` (`160 / 927`), `deck_universe` (`47 / 927`) |

#### Signal cleanup (`#1352`)

Four per-signal defects identified on the 927-card Chulane store were cleaned up in `#1352`:

1. **`synergy` (`weight = 0`, `< 0` neutral, layer `commander_fit`):** EDHREC synergy measures relative enrichment over all decks rather than card strength (`Sol Ring -0.0738`, `Arcane Signet -0.1722`, `Farseek -0.2089`). Its default weight in all presets is `0.0`, it is exposed as the weightless layer column `"Passt zum Commander"` (`commander_fit`), and when weighted positively any value `< 0` gets `status = NO_VALUE`, `reason = NEGATIVE_NEUTRAL` (never penalizing).
2. **`playgroup_observed` (`weight = 0`, $k = 200$, `min_denominators.playgroup = 200`):** already shown as layer `"Sieg-Abstand"` (`win_gap`); shrinkage $k$ was raised from `25` to `200`, the index gate was set to `200` games (import minimum remains `25`), and its default weight in all presets is `0.0`.
3. **`tournament_lists` (`min_denominators.tournament = 20`):** Chulane has 7 tournament lists, which stayed noisy despite top-deck sharing; raising the default gate from `5` to `20` disables `tournament_lists` for Chulane while keeping commanders with $\ge 20$ lists active.
4. **`combos` (`combo_source = "commander"` default, `min_coverage = 0.25`):** replaces the generic Spellbook mixture (`spellbook`) by default with `edhrec_combo_decks` (which counts as commander-specific under `require_commander_signal`), and lowers `min_coverage` from `0.30` to `0.25` so cards with `deck_universe(2) + global_inclusion(1) = 3 / 11 = 0.2727` stay ranked (`U = 0`).

Measured isolated steps (`k = 200` baseline on the 927-card Chulane store) and all three final `#1352` presets:

| Step / Preset | Spearman $r$ (all 922) | Non-lands (857) | Lands (65) | Randkarten oben | Stammkarten unten | Dünne oben (`< 5`) | Tier counts `S / A / B / C / D / U / N` |
|---|---|---|---|---|---|---|---|
| Baseline `#1351` (`Ausgewogen`, $k=25$) | `0.8013` | `0.7867` | `0.8423` | `0 / 20` | `0 / 27` | `0 / 20` | `8 / 12 / 103 / 272 / 527 / 0 / 5` |
| Baseline mit $k = 200$ | `0.8135` | `0.7965` | `0.8778` | `0 / 27` | `—` | `—` | `9 / 18 / 96 / 249 / 550 / 0 / 5` |
| Only `synergy = 0` | `0.8137` | `0.7967` | `0.8809` | `0 / 26` | `—` | `—` | `9 / 17 / 97 / 249 / 550 / 0 / 5` |
| Only `min_denominators.playgroup = 200` | `0.8184` | `0.7983` | `0.8883` | `0 / 22` | `—` | `—` | `9 / 13 / 75 / 225 / 600 / 0 / 5` |
| Only `playgroup_observed = 0` | `0.8124` | `0.7905` | `0.9207` | `0 / 23` | `—` | `—` | `9 / 14 / 52 / 227 / 620 / 0 / 5` |
| Only `min_denominators.tournament = 20` | `0.8133` | `0.7964` | `0.8779` | `0 / 26` | `—` | `—` | `10 / 16 / 95 / 251 / 550 / 0 / 5` |
| Only `combo_source = "commander"` (`min_coverage = 0.30`) | `0.7935` | `0.7537` | `0.9155` | `0 / 23` | `—` | `—` | `9 / 14 / 53 / 136 / 223 / 487 / 5` |
| **`Ausgewogen` (final `#1352`)** | **`0.9255`** | **`0.9147`** | **`0.9864`** | **`0 / 23`** | **`0 / 27`** | **`17 / 23`** | **`9 / 14 / 24 / 50 / 825 / 0 / 5`** |
| **`Commander-nah` (final `#1352`)** | **`0.9410`** | **`0.9319`** | **`0.9917`** | **`0 / 24`** | **`0 / 27`** | **`24 / 24`** | **`9 / 15 / 23 / 48 / 827 / 0 / 5`** |
| **`Turniernah` (final `#1352`)** | **`0.9255`** | **`0.9148`** | **`0.9840`** | **`0 / 20`** | **`0 / 27`** | **`15 / 20`** | **`7 / 13 / 31 / 46 / 825 / 0 / 5`** |

Land shares across `S / A / B / C / D` in final `#1352`: `Ausgewogen` `33.3 % / 42.9 % / 37.5 % / 30.0 % / 3.9 %`, `Commander-nah` `33.3 % / 46.7 % / 34.8 % / 31.3 % / 3.9 %`, `Turniernah` `14.3 % / 38.5 % / 38.7 % / 32.6 % / 3.9 %`. Largest leave-one-out tier impact: `deck_universe` (`857 / 927` in `Ausgewogen` & `Commander-nah`, `889 / 927` in `Turniernah`), `global_inclusion` (`855 / 856 / 862`), `commander_inclusion` (`6 / 6 / 6`).

#### Rubric, missing EDHREC values, lands apart, new cuts (`#1358`, `#1350`, `#1353` part A)

After `#1352` the index followed the counted deck lists closely (Spearman `0.9255`) but it had
three weaknesses on the Chulane pool of 922 ranked cards: 756 cards are below 1 % of the 2,823
counted lists (358 of them in none), so for them the index rested on a handful of near-zero signals; about 850 cards
had no EDHREC row, so the weight of that signal simply vanished for them (`skip`); and lands
(65 ranked) shared the scale of the spells, so the land with the most decks (`Command Tower`)
set $v_{\max}$ for everybody. Four changes, one PR; the cuts were re-derived once at the end.

**1. Rubric component (`rubric`, "Raster-Bewertung (Chulane)", #1358).** A structured, subjective
rating of every rankable Chulane card, frozen in `data/research/chulane_rubric_20261114/`
(`GUIDE.md`, `ratings.csv`, `summary.csv`, `README.md`). The question: how much better does a
tuned Chulane deck (Bracket 3, four players) get when the card takes a slot, as a holistic value
H from 1 to 10 from five criteria (efficiency, fit with Chulane, table impact, reliability, win
contribution). Three independent automated raters (`R1`, `R2`, `R3`, not people) rated blind to
usage (name, cost, type line, rules text and the guide only); ten anchors keep fixed values.
`H_mean` is the mean of the raters.

- Method in the index: the observation is $(H_{\text{mean}} - 1) / 9$ in `0..1`, used **directly**
  as the component score. It is not a share (no Wilson bound, no `share_scale`) and not a
  percentile rank, so the magnitude of the rating is kept. The row names `H`, the spread of the
  raters and their number (anchors: "fester Ankerwert"). The signal is
  commander-specific: it counts for `require_commander_signal`, and for any other commander it
  is a missing source (`NOT_COLLECTED`, never 0) that does not lower the coverage.
- Import: `import-all --from-repo` reads `summary.csv` into `rubric_h_mean`, `rubric_h_sd` and
  `rubric_raters` of "Chulane, Teller of Tales" (explicit folder-name table, no guessing),
  with source and SHA-256, idempotent. All 922 rows match a pool card by name (`rows_unmatched`
  0); the header is checked exactly and a changed layout fails the import (tests).
- Reliability (from the data README, over the 912 rated cards): ICC(2,1) of one rater `0.84`,
  ICC(2,3) of the mean of three (the value used) `0.94` (95 % interval `0.93` to `0.95`),
  Krippendorff's $\alpha$ `0.84`; pairwise Spearman of the raters `0.79` / `0.80` / `0.89`.
  The single criteria reach ICC(2,3) `0.88` to `0.91`.
- Validity: Spearman of `H_mean` with the card's share in the counted lists `0.62` (all 922
  cards; `0.44` among the 162 cards in at least 1 % of the lists), with global EDHREC inclusion
  `0.52`, with the Playgroup win gap `-0.19` (as found in `#1352`, that gap is not a strength
  signal).
- Limits: the raters share a model family, so part of their agreement can be shared bias;
  validity against real deck lists is the check on that, and the index never uses the rubric
  alone. They judge rules text and play knowledge, not testing; `H_sd` (five cards have a spread
  of 2 or more, e.g. `Psychosis Crawler`) shows where a rating is unsure. The rubric covers
  Chulane only. It is the one subjective input of the index and is a frozen file: no rank is
  assigned by hand, no weight or cut was tuned to move a named card. Owner marks and simulation
  results play no part.

**2. Missing EDHREC values (`missing_value`, #1350).** For the commander inclusion and the
bracket inclusion the recommended value is now `lowest` (`skip` stays selectable; the deck
universe stays `skip`, its zeros are counted). EDHREC lists every card above its listing
threshold, so a card that is not listed is below it. What `lowest` yields under
`share_scale = "share"`: the component score 0.0, which is at or below the score of the smallest
listed card ($\sqrt{v / v_{\max}} \geq 0$ for every listed card, so never above it; a listed
card with a count of 0 gets the same 0). That is the meaning intended ("below the smallest listed
share"), so no code fix was needed, only the default and the per-signal panel recommendation.
Pinned by a test for both scales and both comparison groups. Consequence: an unlisted card now
counts as a present component (its weight is in the coverage), which is why the coverage no
longer separates cards that EDHREC lists from those it does not.

**3. Lands apart (`separate_lands`, #1353 part A).** Recommended on: share scaling and percentile
ranks are computed within "Länder" and within "Zauber"; the tier cuts are the same for both.
Basic lands and the commander stay unranked (tier `N`). A group below five valued cards keeps the
joint scale and says so. The tier page filters "nur Länder" / "nur Zauber" and shows the tier
counts of both groups. A land's score does not change when a spell's share changes and the
other way round (test); with the setting off the old joint scale is restored exactly.

**4. Default weights and tier cuts.** The Owner allowed only "a little" subjectivity, so the
rubric is about 30 % of the present weight for a typical Chulane card. In `Ausgewogen` it
weighs 3.5: for 909 of the 922 ranked cards the usage block present is commander (3) + bracket
(2) + deck universe (2) + global (1) = 8 (the 13 cards with a combo row have 9; Chulane has no
tournament lists above the minimum), and 3.5 / (8 + 3.5) = 30.4 %. `Commander-nah` uses 4
(usage 9) and `Turniernah` 2.5 (usage 6) by the same rule. A first version used 50 %; there the
index followed the rubric almost entirely (Spearman with `H` `0.98`), see the sensitivity table.
The tier cuts were derived once from the resulting default index of the 857 ranked non-lands
with the targets fixed in advance (S about 3 %, A about 10 %, B about 22 %, C about 30 %, D the
rest): the whole numbers whose cumulative shares (3.0 / 12.8 / 34.1 / 62.4 %) come closest to
3 / 13 / 35 / 65 % are **47 / 17 / 9 / 4** (before 70 / 55 / 35 / 20). Achieved on the
non-lands: S `3.0 %`, A `9.8 %`, B `21.2 %`, C `28.4 %`, D `37.6 %` (26 / 84 / 182 / 243 / 322
of 857); on the 65 lands (same cuts) 12 / 12 / 15 / 17 / 9. Whole-number cuts are coarse at the
low end (cut 4 gives C a cumulative 62.4 %); the page's cut fields step by 1.

**5. Stored profiles.** A saved profile has no `rubric` key (and no `separate_lands` key) if it
was written before this change: on load such a profile gets the default weight (3.5) and the
default setting, so it changes its result. A profile that was saved with all keys keeps them.

Measured on a fresh store from the repository (`import-all --from-repo`, pool 927, 922 ranked,
2,823 counted lists), `ranking-check --commander "Chulane, Teller of Tales"`. "Before" is main's
default (`#1352`), reproduced exactly by the new code with the old settings.

| Metric (`Ausgewogen`) | Before (`#1352`, cuts 70/55/35/20) | After (rubric 3.5, cuts 47/17/9/4) |
|---|---|---|
| Spearman with counted share, all / non-lands / lands | `0.9255 / 0.9147 / 0.9864` | `0.7388 / 0.7135 / 0.9465` |
| Spearman with counted share among cards with $\ge 1\,\%$ share (n = 162) | `0.9699` | `0.8661` |
| Spearman with rubric `H`, all / non-lands / lands | `0.6101 / 0.6009 / 0.7453` | `0.9670 / 0.9760 / 0.8794` |
| Randkarten oben | `0 / 23` | `59 / 134` |
| Stammkarten unten | `0 / 27` | `0 / 27` |
| Dünne Datenlage oben (`< 5` signals) | `17 / 23` | `0 / 134` |
| Tiers `S / A / B / C / D / U / N` | `9 / 14 / 24 / 50 / 825 / 0 / 5` | `38 / 96 / 197 / 260 / 331 / 0 / 5` |
| Land share `S / A / B / C / D` | `33.3 / 42.9 / 37.5 / 30.0 / 3.9 %` | `31.6 / 12.5 / 7.6 / 6.5 / 2.7 %` |
| Leave-one-out tier changes | `deck_universe` 857, `global_inclusion` 855, `commander_inclusion` 6 | `rubric` 504, `commander_inclusion` 270, `bracket_inclusion` 177, `deck_universe` 121, `global_inclusion` 42, `combos` 0 |

Each change on its own, added one after the other:

| Step (`Ausgewogen`) | Spearman counted all / non-lands / lands | $\ge 1\,\%$ (n = 162) | vs rubric `H` (all) | Randkarten oben | Dünne oben (`< 5`) | Tiers `S / A / B / C / D / U / N` |
|---|---|---|---|---|---|---|
| Before | `0.9255 / 0.9147 / 0.9864` | `0.9699` | `0.6101` | `0 / 23` | `17 / 23` | `9 / 14 / 24 / 50 / 825 / 0 / 5` |
| + unlisted = lowest (#1350) | `0.9255 / 0.9148 / 0.9860` | `0.9638` | `0.6109` | `0 / 23` | `17 / 23` | `9 / 14 / 23 / 19 / 857 / 0 / 5` |
| + lands apart (#1353 A) | `0.9297 / 0.9198 / 0.9856` | `0.9652` | `0.6122` | `0 / 27` | `21 / 27` | `13 / 14 / 22 / 20 / 853 / 0 / 5` |
| + rubric weight 3.5 (old cuts) | `0.7388 / 0.7135 / 0.9465` | `0.8661` | `0.9670` | `0 / 25` | `0 / 25` | `10 / 15 / 27 / 46 / 824 / 0 / 5` |
| **+ cuts 47/17/9/4 (after)** | **`0.7388 / 0.7135 / 0.9465`** | **`0.8661`** | **`0.9670`** | **`59 / 134`** | **`0 / 134`** | **`38 / 96 / 197 / 260 / 331 / 0 / 5`** |

The other presets, before then after (same new cuts and settings):

| Preset | Spearman counted all / non-lands / lands | $\ge 1\,\%$ (n = 162) | vs rubric | Randkarten oben | Dünne oben | Tiers `S / A / B / C / D / U / N` |
|---|---|---|---|---|---|---|
| `Commander-nah` before | `0.9410 / 0.9319 / 0.9917` | `0.9805` | `0.6142` | `0 / 24` | `24 / 24` | `9 / 15 / 23 / 48 / 827 / 0 / 5` |
| `Commander-nah` after (rubric 4) | `0.7481 / 0.7230 / 0.9543` | `0.8727` | `0.9648` | `62 / 139` | `0 / 139` | `38 / 101 / 206 / 250 / 327 / 0 / 5` |
| `Turniernah` before | `0.9255 / 0.9148 / 0.9840` | `0.9660` | `0.6099` | `0 / 20` | `15 / 20` | `7 / 13 / 31 / 46 / 825 / 0 / 5` |
| `Turniernah` after (rubric 2.5) | `0.7627 / 0.7373 / 0.9572` | `0.8670` | `0.9577` | `66 / 145` | `0 / 145` | `26 / 119 / 200 / 260 / 317 / 0 / 5` |

Sensitivity to the rubric's share of the weight (`Ausgewogen`, usage weights unchanged, the
cuts 47/17/9/4 kept for every row, so the tier counts of the other rows are not re-derived):

| Rubric share (weight) | Spearman counted all / non-lands / lands | $\ge 1\,\%$ (n = 162) | vs rubric all / non-lands / lands | Randkarten oben | Dünne oben | Tiers `S / A / B / C / D` | Largest leave-one-out |
|---|---|---|---|---|---|---|---|
| 20 % (2) | `0.7804 / 0.7552 / 0.9634` | `0.9002` | `0.9466 / 0.9579 / 0.8506` | `15 / 85` | `0 / 85` | `37 / 48 / 144 / 281 / 412` | `rubric` `408` |
| **30 % (3.5, default)** | `0.7388 / 0.7135 / 0.9465` | `0.8661` | `0.9670 / 0.9760 / 0.8794` | `59 / 134` | `0 / 134` | `38 / 96 / 197 / 260 / 331` | `rubric` `504` |
| 40 % (5.33) | `0.7134 / 0.6887 / 0.9319` | `0.8322` | `0.9765 / 0.9838 / 0.8986` | `115 / 191` | `0 / 191` | `37 / 154 / 233 / 222 / 276` | `rubric` `567` |
| 50 % (8) | `0.6965 / 0.6737 / 0.9110` | `0.7889` | `0.9829 / 0.9884 / 0.9270` | `171 / 251` | `0 / 251` | `34 / 217 / 238 / 185 / 248` | `rubric` `608` |
| 60 % (12) | `0.6847 / 0.6644 / 0.8879` | `0.7332` | `0.9877 / 0.9915 / 0.9513` | `217 / 295` | `0 / 295` | `41 / 254 / 242 / 195 / 190` | `rubric` `671` |

Reading it plainly: a weight share is not an equal share of influence. Of the 922 ranked cards
756 are below 1 % of the counted lists (358 in none), so the usage block is close to 0 for most cards and the rubric's
spread decides their order; even at 30 % the index correlates `0.97` with the rubric, and the
agreement with the counted lists falls from `0.93` to `0.74` (the rubric alone reaches `0.62`;
among the 162 cards in at least 1 % of the lists from `0.97` to `0.87`). The usage block still
decides among the top: only 80 ranked cards have a counted share of at least 5 %, so "Randkarten
oben" cannot stay at 0 once `S`/`A` holds 134 cards (at least 54 of them must be below 5 %). A
higher rubric share lets more marginal cards reach `S`/`A`. "Dünne Datenlage oben" is `0`
because the rubric and the lowest-rank default give every `S`/`A` card five or more present
signals; it no longer tells thin from thick data. The share is a setting; the weight and the
cuts are the recommended starting point, not a validated optimum.

Ranks of eleven named cards (rank within lands or within spells by index; spells 857, lands 65):

| Card | Before: tier, index, rank | After: tier, index, rank |
|---|---|---|
| `Sol Ring` | `S`, 91.6, 1 | `S`, 100.0, 1 |
| `Swords to Plowshares` | `S`, 80.5, 2 | `S`, 89.0, 2 |
| `Arcane Signet` | `S`, 76.9, 3 | `S`, 82.7, 3 |
| `Counterspell` | `A`, 66.0, 8 | `S`, 71.1, 9 |
| `Farseek` | `B`, 51.3, 16 | `S`, 56.2, 16 |
| `Cultivate` | `A`, 58.2, 13 | `S`, 58.2, 13 |
| `Mystic Sanctuary` (land) | `C`, 23.0, 30 | `C`, 8.5, 41 |
| `Psychosis Crawler` | `D`, 19.2, 66 | `B`, 15.6, 125 |
| `Zuran Orb` | `D`, 6.3, 230 | `D`, 1.7, 693 |
| `Command Tower` (land) | `S`, 99.3, 1 | `S`, 100.0, 1 |
| `Maze's End` (land) | `D`, 7.7, 45 | `D`, 2.1, 60 |

`ranking-check` reports the agreement of the index with the rubric as block `1b` (key
`spearman.vs_rubric`): the rubric is itself a component, so it shows how much of the order the
rubric sets, not that the order is right. The tier cuts and the 30 % weight rest on a rule fixed
in advance, not on a validation; judging them is the Owner's decision.

#### EDHREC cardlist audit & role expansion (`#1353` parts B and C)

- **EDHREC Chulane cardlists (part B, `data/research/edhrec_observations_chulane/edhrec_chulane_threshold_audit.json`):**
  Both `commander_card_signals_*.csv` and the `chulane-teller-of-tales` theme cohort of
  `edhrec_table_chulane_1..3.csv` already contain **all 12 cardlists** of the EDHREC Chulane
  page (`241` distinct cards in the `2026-11-12` snapshot, `0` symmetric difference; live
  verification `2026-11-15`: `242` distinct cards, only `Carpet of Flowers` added outside the
  collection). Pool coverage stays **68 / 922 ranked cards** (**71 / 927** including 3 basic
  lands) before and after; the listed share threshold is **~5.0 %** (`505 / 9,824 = 5.1405 %`
  on regular lists with a 50-card cap on `creatures` and `lands`, `29 / 1,221 = 2.3751 %` on
  `newcards`; brackets `5.0179 %–5.1502 %` regular, `2.0833 %–3.4783 %` `newcards`), while
  non-tag subpages (`/creatures.json`, `/top-cards.json`, `/lands.json`, `/average-deck.json`)
  return HTTP 403.
- **Role gap closure (part C):** `roles.ROLES` expands from `17` to **34** canonical Scryfall
  `otag:` roles (`roles_s4_tagger_expansion_wug.json`, 15,422 `SCRYFALL_TAGGER_ORIGINAL` claims)
  plus deterministic Oracle-text classification (`roles.classify_oracle_roles`,
  `roles_s5_oracle_expansion.json`, 1,570 `ORACLE_TEXT_REVIEW` claims). Chulane 927-pool
  coverage rises from **558 / 927 (60.2 %)** to **817 / 927 (88.1 %)** (20 roles `≥ 30`
  cards, 11 roles `10–29`, 3 roles `< 10`). Measuring `ranking-check` (`Ausgewogen`) shows that
  `rank_group = "pool"` stays recommended (Spearman `0.9297` vs `0.8819` for `"function"`,
  Randkarten oben `5 / 71` vs `19 / 94` because small-role leaders with `< 5 %` deck share
  scale to `S/A` inside isolated role groups).
- **Reminder text and own draws (#1404, #1413):** the Oracle-text rules `cantrip`, `card_advantage`
  and `hate` read the text without parenthesised reminder text (nested parentheses included), so a
  Clue's "Draw a card" or a Split second "players can't cast spells" no longer counts; `card_advantage`
  needs a draw for the card's own controller ("that player draws", "each player draws" do not
  count, "target player draws" does). `card_draw` and `utility_land` still read the full text.
  `roles_s5_oracle_expansion.json` and `roles_s6_oracle_corpus.json` were regenerated with the
  unchanged `fetched_at` `2026-11-16`: 9 / 1,884 and 101 / 16,338 claims dropped, none added.


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
`expected_signals(commander)` lists the rubric signal `rubric_h_mean` only for a commander that
has a rubric file (`RUBRIC_COMMANDERS`, today Chulane); for every other commander the rubric is
neither a missing layer in the completeness table nor an import command offered.

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
inclusion, deck universe, synergy, tournament lists, or `combos` with `combo_source = "commander"`)
has a ranked value with a weight above 0. A value that stands in only because of
`missing_value = lowest` (the card is in none of the commander's lists, #1350) is not such
evidence: it counts for the index and the coverage, but a card with nothing else than global
inclusion stays at tier `U`. Global inclusion, Spellbook combos (`combo_source = "spellbook"`)
and the Playgroup observation are the same for every commander and never give a tier alone
(tier `U`, reason `NO_COMMANDER_SIGNAL`, "kein Signal speziell für diesen Commander"; simulation
never counts). The recommended minimum data situation (`min_coverage`, shown as
"Mindest-Datenlage") is 0.25. With the default `missing_value` (commander and bracket
inclusion lowest) an unlisted card has commander inclusion 3 + bracket inclusion 2 + global 1 =
6 of 11 (0.5455) and, with a counted universe, deck universe 2 as well: the coverage threshold
no longer separates it, the commander-specific rule above does. With `missing_value = skip` an
unlisted card with a counted universe has deck universe 2 + global 1 = 3 of 11 = 0.2727 (total
weight 11 with synergy and Playgroup observation at 0).

### Combos in the deck (schema 14)

The combo list of a commander (`edhrec_<commander>_combos.csv`: `cards` separated by `;`,
`num_decks`) is stored twice by the signal import: per card as the signal
`edhrec_combo_decks` (used by `combos` under the default `combo_source = "commander"`) and, since schema 14, as full
card sets in the table `commander_combo`. A replacing import swaps the commander's list, an
appending one only adds sets that are not stored yet.

The deck check (`POST /api/check`, and a stored revision) returns `combos`: the listed combos
the deck holds completely and the ones that lack exactly one card, each with the source's deck
count. The statistics tab shows them under "Kombos im Deck" and says for a missing card whether
it is in the pool, and names the source of the combo list (the title and snapshot date or import day of the imported file, `sources` in the result). Names match by the full card name, then by the front face of a two-part card,
never by the back half. Limits: only listed combos are known; without a stored list the section
says so and never claims "no combos"; the deck count is the source's count over all its decks,
not a count for this commander; it is a comparison of card sets, not a rating.

Template-slot queries are evaluated offline and exactly, or the count is `unbekannt` (never 0).
`t:` is a case-insensitive substring match on the type line (a quoted phrase is one substring;
whitespace is trimmed and collapsed on both sides). `id:`/`identity:` take a colour word, a guild,
shard, wedge or college name, or letters of `wubrgc` only, with `=`, `<=`, `>=`, `<`, `>` as set
comparisons; `:` only for colourless, anything else is unknown. `c:`/`color:` is always unknown:
the colour of a card is not exact from the mana cost alone (colour indicator, Prepare layout,
faces of a two-sided card) and needs the Scryfall `colors` field. A slot with a commander or
zone condition is flagged `partially_checked` (only the card-text query was checked); an unknown
slot has `matches_in_pool_total` `null`.

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
  The same cache holds the cohort shapes, the land advisor's source-deck groups, the corpus
  deck sets behind the pool counts and the packages, the layer overview and the data report
  (per commander, group and day); concurrent identical requests share one computation, a failed
  computation is never cached, and entries of an older store state are dropped. `serve` fills
  these in the background for the commanders with source data, so the builder page starts its
  requests side by side and only the very first load after an import pays for the counting.

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

Public card images and public MTG metadata requests follow `AGENTS.md` §12 (image loads omit
referrers via `referrerpolicy="no-referrer"`, fixed host in `images.py`).

### Which printing is shown (schema 16, #1342)

A card is pictured as the printing the collection itself holds when that printing is
identifiable, and as a plain standard printing otherwise — never as a full-art or
promo variant chosen by chance. The precedence is:

1. **Exact collection printing** (`EXACT_COLLECTION`): the inventory import reads the
   workbook's lot sheet into `card_printing` (one primary printing per card: the
   printing of the most copies; a reference that names no single printing stays
   `UNRESOLVED` and is counted, never guessed). `import-printings <workbook>
   --bulk <default-cards file>` resolves that printing's image addresses deterministically
   against the downloaded public default-cards bulk file (`AGENTS.md` §12 permits both offline
   bulk matching and public MTG metadata lookups since 2026-11-15). The same
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

### Pasting a deck list

`parse_decklist_text` reads plain, Arena, MTGO, Moxfield, Archidekt and CSV lists. It strips a
leading byte-order mark once, normalises typographic quotes, non-breaking and zero-width spaces
and dashes, and also matches the back-face name of a two-faced card. A quantity must be 1 to 99:
other values are listed as `unreadable`. Every unrecognized line carries a `status`. A line
longer than 300 characters (for CSV: quantity and name cells together) is listed as `zu lang`, and a
list of more than 2000 lines is refused with a German error (HTTP 422), never truncated silently.
For CSV only the quantity and name cells are ever returned, never the whole row. Amount tokens
anywhere in a line (currency symbols or ISO codes before or after the figure, in brackets, with
thousands separators) are removed before matching and noted only as `Betragsangabe (ignoriert)` in
`ignored_annotations`; every returned text field is passed through the same removal, and a line
that consists only of an amount is `unreadable`. Enclosing double quotes are tried against the
original name first. Sideboard, `Maybe`/maybeboard, cuts, `sb:` lines are not part of the deck but no longer
vanish silently: each is noted as `Sideboard-Zeile übersprungen (nicht im Deck)` in `ignored_annotations`
(line number only, no card name, no amount) and counted in `summary.sideboard_lines_skipped`. `#` and `//` comment lines stay
skipped silently.

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
Playgroup atlas (`playgroup`, three parts), the rating rubric (`chulane_rubric_<date>`, step
"Raster-Bewertung (Repo)": `summary.csv` as three signals of the commander the folder name
stands for, recorded as a source with its SHA-256, idempotent, replacing only its own signals
of that commander; the folder name is looked up in an explicit table
(`research_import.RUBRIC_COMMANDERS`), a folder that is not in it is not imported; the file's
header must be exactly the known columns and every row is checked, otherwise the step fails;
`rows_unmatched` counts rating rows whose card the store does not know, expected 0), signals (every signal folder below `data/research`
and `data/research` itself for the counted deck-list file) and marks. The completeness table
adds the layers "Korpus (Decks, alle)", "EDHREC-Beobachtungen (Themen)" and "Playgroup-Atlas".
The loaders are the functions of `studio/repo_import.py`; the scripts
`scripts/build_inventory_workbook.py`, `scripts/import_chulane_corpus.py` and
`scripts/map_corpus_oracle_ids.py` call them.

### Engine check ("Prüfung durch die Engine")

The tab "Prüfung" has two separately named checks. "Datenprüfung (gespeicherte Fakten)" reads
stored card facts. "Prüfung durch die Engine" (button "Mit der Engine prüfen",
`POST /api/engine-check`, `engine_check.py`) runs the full-game runner's own deck construction
validation (`_validate_deck_construction`: content hash, duplicates, colour identity) on the
current list, plus the cards the pinned engine cannot load (`launch.cards_unsupported_by_engine`,
`launch.cards_unknown_to_pilots`, the logic of `/api/engine/missing-cards`). It starts no game and
XMage's own deck import still runs at game start. Result: `FAIL` when anything is found. `PASS`
needs all three: the construction validation really ran and found nothing, the engine's card
list was read and names no card of the deck, and the engine is provisioned (the configured
command resolves and the file after `-jar` exists; a Java that cannot be read counts as not
provisioned). Everything else is `UNKNOWN`, never shown as green, with one of four headlines:
"nicht geprüft: Voraussetzung nicht erfüllt" (the list is not exactly 100 cards, has no
commander or more than two; the reason is named, e.g. "Das Deck hat 5 statt 100 Karten."),
"nicht geprüft: Deck-Aufbau nicht prüfbar", "nicht geprüft: Engine nicht bereitgestellt" and
"nicht geprüft: Kartenliste der Engine nicht lesbar".

### Play from the builder

The button "Mit diesem Stand eine Partie spielen" opens `partie.html?neu=1&revision=ID` with the
saved revision preselected in the new-game dialog. It plays the saved revision only: with an
unsaved draft the button reads "Erst als Stand speichern, dann spielen" and a click explains it
instead of using an older revision. The Partien page has no series start yet; series come with
issue #1170.

### Land advisor ("Länder im Vergleich zu den Farbsymbolen")

Section of the tab "Zahlen" (`POST /api/land-advisor`, `land_advisor.py`): an observation, never
a recommendation. Per colour: coloured symbols in the costs of the non-land cards (count and
share), lands that can produce the colour, other sources (mana rocks, creatures) apart, next to
median and middle half of the chosen comparison group of source decks for the same figures,
with the land count. Groups below 30 decks are flagged. Rules: land means front type line Land;
a modal spell-land is a spell (its land side is shown apart); a hybrid symbol counts for each of
its colours, Phyrexian and "2 or colour" symbols for the colour, `{C}` as colourless, `{X}` and
generic mana not at all; a split card counts both halves, other two-faced cards the front; a
land counts for every colour it produces; a land with unknown colours is "unbekannt", never 0;
the commander's own cost and its colour identity are named apart. Source decks with cards the
card data does not know are left out and counted.

### Card allocation ("Belegung", #1419)

`GET /api/allocation` (`studio/allocation.py`) shows per card where its copies are bound, for
display only (nothing is locked, no deck is changed). A saved deck binds the copies of its
`main` variant (without one, of its most recently saved variant); other variants are
alternatives of the same physical deck and are listed without binding; drafts never bind. A
card is marked **überbucht** when the copies bound by all saved decks exceed the copies free
for own decks (`available_lower_bound`); without an inventory row no overbooking is claimed.
Copies reserved for opponents' decks (`reserved`) stay a separate figure. Storage locations
come only from the inventory workbook's lot sheet (`02_PHYSICAL_LOTS.location_id`, names from
`03_LOCATIONS`) and are stored per card and location in `card_location` at the inventory import
(summed lower-bound quantities; "mindestens" when a lot is only a lower bound, and lots without
any quantity counted apart, never as 0; the card window says how many of the owned copies have a
location);
a card without location rows shows no location field. The pool tiles show "in N Decks
(n gebunden)" and the overbooking; the card window lists the decks, the other variants, the
reserved copies and the locations in the data's own wording.

### Build list by storage location ("Bauliste nach Standort", #1404)

`POST /api/build-list` (`studio/build_list.py`, body like the sibling list routes: at most 300
cards, optional `deck_id`; unknown card 404, empty list or oversize 422, header `X-Studio`
required) groups the current list by storage location, to put a deck together physically. The
button "Bauliste nach Standort" sits in the export dialog and opens a large dialog with one table
per location (alphabetical, "Standort unbekannt" last, "n Karten" per group), a tick box per card
(local to this browser, `localStorage` per deck state, never sent anywhere), "Als Text kopieren"
(without any price words) and "Drucken" (print rules show only the list).

Locations come from the same `card_location` rows as the allocation above. The needed copies of
a card are placed on its known locations, largest known stock first (name as tie-break); what
they do not cover stays "Standort unbekannt" with the copies still missing (k of n). A location
row marked "mindestens" (lower bound, or lots without a quantity) is shown as "Bestand
mindestens"; the name "Unbekannt / nicht direkt belegt" is no box and counts as unknown. A card
bound by another saved deck, with fewer free copies than needed, carries the note "in <Deck>
gebunden (n)": a fact, no lock. Basic lands form their own block without a location, the
commander is listed on top. The sum of the groups, the commander and the basic lands must equal
the list size; if not, the page shows an error line, never a silent difference. The header counts
the non-land, non-commander cards with fully exact, only lower-bound, partly unknown and wholly
unknown location. No prices, no rating, no simulation; favourites and other marks are not read.
Measured on the QA store copy (Chulane baseline, 100 cards): commander 1, basic lands 20, 79 of
79 other cards with an exact location (A Box 14, L Box 5, M Box 60), 0 lower-bound, 0 unknown.

### Variant comparison with counted deltas ("Varianten-Diff", #1414, #1404 option 8)

`POST /api/diff` (`studio/deck_diff.py`, on top of `builder.diff_lists`) compares a stored
revision with the current list: added, removed and changed cards; land, creature and nonland
counts; average mana value; land-draw probabilities; role deltas; the mana curve per mana value;
coloured pips and coloured land sources per colour; listed combos complete before and after
(with the combos that became or stopped being complete; without a stored list: unknown); the
overlap as shared card slots of both totals. Per swapped card it shows roles, mana value and
how many source decks of the commander in the chosen comparison group play it (`decks` of
`of`; unknown when no source deck names the card). The comparison base can be the previous
state, any saved state of the deck, another variant or the current state of another deck. No
score, bracket or power delta: the stored revisions are the version snapshots, so no second
deck store is needed.

### Bracket facts and data gaps ("Bracket & Lücken", #1404 options 1 and 10)

The deck tab "Bracket & Lücken" (`POST /api/deck-facts`, `studio/deck_facts.py`) counts, with
names and origin, what the published Commander Brackets talk about: Game Changers (card data
flag `game_changer`; a card without the flag is counted apart as unknown), extra turns and mass
land denial (oracle text patterns, shown as candidates with the matching rule), tutors (public
role `tutor`; the tagger counts land search too, so "davon Land-Suche" is shown apart) and
two-card combos complete in the deck (stored combo list; without a list: unknown). Only the
Game Changer count has a published number per bracket (0 in brackets 1 and 2, at most 3 in
bracket 3, no limit in 4 and 5); the page shows each bracket's limit next to the count
("passt", "über der Grenze", "unbekannt" when unknown flags could cross it) and never says
which bracket the deck is in. Sources: the Commander Brackets updates of 2025-10-21 and
2026-02-09 (tutor limits removed on 2025-10-21).

"Without oracle text" (`text_unknown`): an empty `oracle_text` of a creature is a fact when the
card facts exist (`fact_source` set and not the bare workbook): a vanilla creature has no rules
text, so it counts as read (no match) and is not a gap. The text stays unknown when the card facts
are missing (`fact_source` empty or `workbook`) and for a non-creature without text. Measured on the QA store
copy (1,655 card facts): 40 creature rows have a NULL text; a 100-card probe (those 40 plus 60 with text)
counted 40 of 100 as unknown before and 0 of 100 now.

The same tab lists the data gaps per card of the deck (the commander excluded): no public card
data, unknown mana value, no role (nonland cards), unknown land colours, no source deck of the
commander names the card, no EDHREC observation for the commander (commander or bracket pages).
Each reason carries its count and the number of cards it was checked for; a source the store
lacks for the commander is reported once, not per card. A gap means unknown, never 0.
EDHREC observations are found by card id and by card name (casefolded; a front face of
"A // B" credits a card only when no other card owns it, as in `universe._card_name_index`),
because many stored rows carry no card id. For Chulane the `no_edhrec` text cites `edhrec_chulane_threshold_audit.json`
(snapshot 2026-11-12): EDHREC lists cards on the card lists of the commander page only above a
minimum share, so a missing
row stays a gap, not a statement about the card. The note "dünn belegt" shows n of N source
decks for the derived group `tuned` (brackets 4 and 5) and for `all` where the card's n is below 30; the
groups are never added, 0 of N is a real count, and a card no source deck names stays unknown.
It is a note on the sample, not counted in `cards_with_gaps`.

### Colours on curve ("Farben auf Kurve", #1415, #1404 option 2)

The tab "Zahlen" shows, for every distinct coloured requirement of the deck's nonland cards
(pips per colour of the front cost, at the turn of the card's mana value), the exact
probability to hit the land drops by that turn and, only among those draws, to hold the
coloured sources the cost needs (`POST /api/castability`, `studio/castability.py`). Method:
Frank Karsten, 2022 update. Missing the land drop is reported apart; two pips of one colour and
several colours are one joint event computed over land groups by produced colours (a dual land
counts for both colours of one draw), never a product of single probabilities; every value
carries its condition ("bedingt auf mindestens T Länder unter 7 + T gezogenen Karten"). Sources
are lands only; lands without coloured mana per card data (fetch lands) and lands without card
data are counted as lands but not as sources and are listed; hybrid and Phyrexian symbols are
not part of the requirement and the cards are named. No mulligan, no extra draws. The opening
hand figure is the exact share of 7-card hands with 2 to 4 lands and at least one nonland card
of mana value at most 2. A description, never a land count recommendation.

### Card duel ("Karten-Duell", #1404 option 3)

In the card window, "Karten-Duell" sets a second pool card next to the open one
(`POST /api/card-duel`, `studio/card_duel.py`): whether each is in the deck, type, mana value,
roles, how many source decks of the commander in the chosen group play it (`decks` of `of`), and
the observed fit with the rest of the deck: the average share of the deck's other cards
(without the two duel cards, the commander and basic lands) in the source decks that play the
card, next to the baseline, the same share over all source decks of the group. A card no source
deck names has frequency and fit unknown (never 0); fits from fewer than 30 decks are flagged.
It is an observation of co-occurrence, never a statement that one card is better. Counting
reuses the cached source-deck index of the similar-decks view.

### Evidence per deck card ("Belege", #1404)

The deck tab "Belege" (`POST /api/deck-evidence`, `studio/deck_evidence.py`, `static/deckevidence.js`)
is one table with one row per deck card and one column per kind of evidence that exists today.
Every cell is a counted value of one source with its numerator and denominator, and the group
(cohort) is named in the column header: source decks of the commander in the groups "alle" and
"tuned" (derived from bracket 4 and 5; the two overlap and are never one number), the EDHREC
commander page (share with its denominator, else "keine Zeile"), the Spellbook shells (a count
per commander without a denominator; shells are stored per commander, within its colour
identity and pool), "Kombo-beteiligt" (n of the commander's stored combos), the Playgroup
observed win-rate gap with its 95 % interval and n (all commanders, multiplayer), the tournament
lists (TopDeck and EDHTop16; the columns appear only when values exist, the header shows the
tiny N, and the EDHTop16 numerator is derived from the published rate), the roles and their
count, and the fit with the other cards of the deck next to the baseline of the group
(the `card_duel` figure for this card against the rest of the deck, computed for the whole deck
in one pass over the cached source-deck index of the similar-decks view; the counts are the
same as the builder's `decks`). The commander and basic lands have the row "nicht anwendbar".
Unknown is never 0: a card no source deck names, a card without a stored row and a card without
role data show their own neutral text. Groups under 30 are flagged.

The table has no sum, no score and no combined rating, and the page says so. The default order is
the thinnest evidence first (fewest source decks in "alle"); every column can be sorted
ascending or descending by its own value only, unknown values always come last, ties are broken
by name. The Owner's marks (favourites, exclusions, notes) are not read and change neither the
order nor any figure, and simulation results do not enter. Controls: choose columns (remembered
per browser), filter by card name, "Große Ansicht" (the same table in the wide dialog), and
"Als Text kopieren" (tab separated plain text of the visible table). A note lists the ten
cards with the fewest source decks with n/N.

### Series in the history ("Serien im Verlauf", #1404)

The "Verlauf" dialog shows, per saved revision of the deck, the stored paired series
(`games/paired-*.paired.json`) in which that revision was base (A) or variant (B).
`GET /api/decks/{deck_id}/series` (module `deck_series.py`) only reads those files and keeps the
ones that name a revision of the deck (at most the newest 200 revisions and 200 series; 404 for
an unknown deck). Each series shows the date, the other side, `n` completed pairs of `N`
planned, the difference (B - A) with the 95 % interval and the look interval exactly as the
series stored them, the status, seeds, seats (shown from 1), pilots, bridge jar and
qualification state, and "Serie öffnen" (the existing paired view). A revision without a series
reads "keine gespeicherte Serie", never 0.

- Status: "abgeschlossen", "vorzeitig gestoppt nach Regel" (decided by the stop rule before the
  planned pairs were played), "abgebrochen", "fehlgeschlagen", "nicht abgeschlossen" (running,
  interrupted or without a result). Only the first two count as a result; for the others the
  figures stay unknown and are not shown as numbers.
- A corrupt, foreign (other schema) or misnamed file is skipped and counted in `skipped`.
- Counts only: no verdict, no ranking, no price, and `SIMULATED_RESULT` never enters the tier
  list or the strength index (weight 0). The route writes nothing.

### Guided cut ("Kürzen", #1418)

The deck tab "Kürzen" brings a list of more than 100 cards to exactly 100 (`POST /api/cut-lab`,
`POST /api/cut-lab/what-if`, `POST /api/cut-lab/finish`, `studio/cut_lab.py`). It serves one
suggestion at a time (Kürzen, Ablehnen, Später, Sperren). The order comes only from measured
figures: cards with a known source-deck frequency first, the least played share first (n/N of
the chosen comparison group), then cards no source deck names (frequency unknown, a separate
group, never 0); ties by role redundancy, then name. A cut that would drop a role below its
minimum (guardrail, default the comparison group's lower quartile rounded down, editable on the
page) comes after the others and says which role; deferred cards come last. Locked cards (kept
per deck in the browser), rejected cards, the commander and basic lands (separate counter) are
never suggested; favourites and other marks never change the order. Each suggestion shows only
the change of the deck figures (curve bucket, roles before and after with the minimum, coloured
pips, land count) and a "Kombo-Teil" badge for cards of a listed combo complete in the deck (no
automatic lock). "Was, wenn stattdessen …" shows the counted deltas of swapping in a free pool
card (`deck_diff.diff_impact`) and changes nothing until confirmed. At exactly 100 the page shows
the ADD/CUT patch against the starting list and the list text and saves the list as a new state.

### Archetype labels (schema 15)

Free-form labels the Owner puts on a card (card window, "Archetyp-Marken") and on a saved deck
(button "Marken" next to the deck choice). Tables `card_label` and `deck_label` in the Studio
store; opening a schema 14 store creates them (nothing else changes, idempotent). Routes:
`PUT /api/cards/{id}/labels`, `PUT /api/decks/{id}/labels` (`{"labels": [...]}`, at most 20 of
at most 40 characters, unique ignoring case), `GET /api/labels`. The pool table filters by label
("alle Marken", "ohne Marke") and has an optional column. Like favorites they never enter a tier,
the strength index, the rating layers or any evidence figure (`archetype_label` in
`evidence.TIER_POLICY["never_inputs"]`; `test_labels_never_change_tier_index_layers_or_evidence`).

### Source state per layer ("Quellenstand", #1404)

The data-state box shows one line per source layer (Quelldecks, EDHREC Commander and Bracket,
Playgroup, TopDeck / EDHTop16, Universum-Kohorten, Spellbook, Scryfall-Fakten, Rulings, Rollen,
Sammlung, Weitere Quellen) from the `source` table (`source_layers.py`; Quelldecks are the sources a corpus deck row names, the other layers follow the registered file
title): `n datiert von N` and the oldest/newest real date. Only a real ISO date counts as a
date; labels such as `universe:<id>` are identifiers, counted apart ("nur mit Kennung") and
never part of the span. A layer without any date in the store says "Datum nicht im Store";
no date is invented and nothing is called fresh. The date is what the importer registered (file name or default), not checked against the
content. Other snapshot text ("2026-11") is not evaluable and counts as undated. `GET /api/status` returns these counts plus `sources`: the 25 newest dated rows (a sample, not the full list)
(it carried all 10,665 rows, 1.7 MB, on every page load; now about 7 KB). The card window's
commander-level co-occurrence pass is remembered per store state, commander list and cohort
(`builder._cohort_deck_sets`, sharing `corpus_deck_sets`), so the second open of a card is a
lookup; the figures are the same as counting the cohort's decks directly (tested).

### Not built: purchase mode

"Kauf-Modus" (try cards outside the collection) is explicitly later (issue #1174 item 7).

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
