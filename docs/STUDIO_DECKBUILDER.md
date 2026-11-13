# Commander Studio: deck builder (BUILD)

Scope: `docs/OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md`. The deck builder is a
local web application in `src/commander_lab/studio/`. It works on the Owner's collection and
currently on one commander (Chulane, `docs/OWNER_DECK_FOCUS_CURRENT.md`).

## Erste Einrichtung

Ein Befehl füllt das Studio mit allen Datenschichten eines Commanders und schreibt einen
Vollständigkeitsbericht. Es wird nichts aus dem Netz geladen; alle Eingaben sind Dateien auf der
Festplatte.

### Voraussetzungen

- Python 3.12 oder neuer. Die Pakete aus `pyproject.toml` müssen installiert sein
  (`pip install -e .` im Repository-Ordner).
- Java 17 oder neuer wird nur für Spiele und Simulationen gebraucht (`scripts/studio_start.ps1`
  warnt, wenn es fehlt). Für den Import und das Deckbauen ist es nicht nötig.
- Der Studio-Datenordner liegt außerhalb des Repositorys (`COMMANDER_LAB_STUDIO_DATA`, sonst
  setzen ihn die Startskripte: Windows `%LOCALAPPDATA%\CommanderStudio`, Linux
  `~/.local/share/commander-studio`).

### Woher die Scryfall-Datei kommt

Die öffentliche Kartendatei von Scryfall: auf `https://scryfall.com/docs/api/bulk-data` die
Datei **Oracle Cards** herunterladen (eine einzige Datei, `oracle-cards-<Datum>.json`). Sie wird
unverändert übergeben; eine mit gzip gepackte Datei (`.gz`) wird ebenfalls gelesen. Die Datei
enthält nichts über die Sammlung.

### Aufbau der Sammlungs-Arbeitsmappe (`.xlsx`)

Die erste Zeile jedes Blatts ist die Kopfzeile. Gelesen werden genau diese beiden Blätter
(`importers.py`):

| Blatt | Pflichtspalten | Weitere Spalten (leer = unbekannt) |
|---|---|---|
| `01_CARD_IDENTITY` | `card_id`, `oracle_name` | `oracle_id`, `color_identity`, `mana_cost`, `mana_value`, `type_line`, `oracle_text`, `is_basic_land`, `commander_legal`, `legality_verified_at`, `identity_evidence_type` |
| `05_INVENTORY_CURRENT` | `card_id`, `observed_quantity`, `physical_owned_quantity_lower_bound`, `reserved_for_opponents_quantity`, `available_for_own_decks_quantity_lower_bound` | `oracle_name`, `quantity_exact`, `number_of_lots`, `last_verified_at` |

`card_id` verbindet die beiden Blätter. Fehlt ein Blatt oder eine Pflichtspalte, bricht der
Import ab und sagt welche.

### Der Befehl

Im Repository-Ordner. Der Commander muss in der Sammlung stehen; die Schreibweise darf von der
der Daten abweichen (Groß-/Kleinschreibung wird nicht unterschieden).

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m commander_lab.studio import-all `
  --collection "C:\Pfad\Sammlung.xlsx" `
  --scryfall "C:\Pfad\oracle-cards-20261113.json" `
  --research data\research `
  --commander "Chulane, Teller of Tales"
```

POSIX-Shell (Linux, macOS, WSL):

```sh
export PYTHONPATH=src
python3 -m commander_lab.studio import-all \
  --collection /pfad/Sammlung.xlsx \
  --scryfall /pfad/oracle-cards-20261113.json \
  --research data/research \
  --commander "Chulane, Teller of Tales"
```

Optional dazu: `--decklists ORDNER` (wiederholbar; Ordner mit den normalisierten Deck-Dateien im
EDHREC- oder Archidekt-Format, das Format wird erkannt), `--playgroup-atlas DATEI`,
`--disambiguation CSV` (`name,selected_oracle_id`), `--data ORDNER` (Studio-Datenordner). Das
aktuelle eigene Deck ist ein eigener Schritt:
`python -m commander_lab.studio import-lab-deck data/decks/deckbau/chulane_current.json`.

Der Befehl läuft in dieser Reihenfolge: Sammlung, Scryfall-Karten (verknüpft die Sammlung),
Deck-Listen, Signale (EDHREC, Spellbook, Turnier, Salt, Combos), Rollen aus dem Tagger-Bulk,
Rulings, Playgroup-Atlas, Verknüpfung der Quell-Decks mit den Karten, ein Standard-Deck-Universum
(`Alle Decks: <Commander>`), Bericht. Die Reihenfolge der Importe untereinander ist egal: die
Verknüpfung der Quell-Decks läuft am Ende von `import-scryfall`, `import-decklists` und von
`import-all`. Wiederholen ändert nichts (jeder Schritt ersetzt nur seinen eigenen Bereich).

Sammlung und Scryfall-Datei sind Pflicht: schlägt einer dieser Schritte fehl, bricht der Lauf ab
(Exit-Code 1). Alles andere ist optional: ein fehlender Eingang steht im Bericht als
`NICHT GELIEFERT`, ein fehlgeschlagener optionaler Schritt als `FEHLER` (Exit-Code 2), und der
Lauf geht weiter. Dateien im Forschungsordner, die kein Importer liest (Drucke, Auswertungen,
Listen anderer Commander), werden mit Grund aufgelistet.

### Starten

`scripts/studio_start.ps1` (Windows) oder `scripts/studio_start.sh` (Linux/WSL); beide rufen
`python -m commander_lab.studio serve --open` auf. Danach ist der Bericht auch unter
`GET /api/import-report` lesbar.

### Den Vollständigkeitsbericht lesen

Der Bericht steht im Terminal und als `import_report.json` im Studio-Datenordner. Pro Schicht
(Bestand, Kartendaten, Legalität, Rollen, Einsatzrate beim Commander, je Bracket und global,
Synergie, Combos, Salt, Turnier, Rulings, Quell-Decks, Deck-Universen, Playgroup) steht:

- **Commander**: `n von N`, wie viele der legalen Karten des Commanders Daten dieser Schicht
  haben. `N` wird aus dem Studio gerechnet (Sammlungskarten, die Commander-legal sind und in der
  Farbidentität des Commanders liegen), nie angenommen. Karten mit unbekannter Legalität zählen
  nicht mit; ihre Zahl steht unter `legality.unknown` im JSON.
- **Sammlung**: dieselbe Zählung über die ganze Sammlung.
- **Status**: `VOLLSTÄNDIG` (alle Karten), `TEILWEISE` (einige), `FEHLT` (die Schicht hat Zeilen,
  aber keine für diese Karten), `NICHT GELIEFERT` (das Studio hat keine Zeile dieser Schicht).
- **Quelle / Stand**: Dateiname und Abrufdatum (aus der Quelle, sonst aus der README der
  Lieferung, sonst `Stand unbekannt`).

Ein unbekannter Wert (leer in der Quelle) zählt nicht als Datum und wird nie als 0 gespeichert.
Rulings: die Quelle führt nur Karten mit Rulings, eine Karte ohne Eintrag hat keines
veröffentlicht; die Schicht gilt deshalb als `VOLLSTÄNDIG`, sobald sie importiert ist, und `n`
sagt, wie viele Karten Rulings haben.

### Was unbekannt bleibt

- Die Zählung sagt nichts über die Güte der Daten, nur ob die Quelle für die Karte einen Wert hat.
- Salt gibt es nur für die veröffentlichte Top-Liste; die Salt-Spalte der Kartenseiten-Datei wird
  nicht gelesen (andere Skala, nicht geprüft).
- Commander-Kennzahlen der Playgroup, Turnier-Präsenz je Commander, Drucke (MTGJSON) und die
  Probeabrufe haben im Studio keinen Abnehmer und werden nicht importiert.
- Der Playgroup-Kartenatlas kommt nur über `--playgroup-atlas`; ohne Datei bleibt die Schicht
  `NICHT GELIEFERT`.
- Neue Daten sind Momentaufnahmen: EDHREC- und Turnierwerte ändern sich; das Abrufdatum steht im
  Bericht.

### Einzelbefehle

`import-all` ruft nur die vorhandenen Importer auf; jeder lässt sich einzeln nutzen:
`import-inventory`, `import-scryfall`, `import-decklists ORDNER --format edhrec|archidekt
--commander NAME`, `import-signals ORDNER --commander NAME [--append]`,
`import-tagger-roles DATEI` (Tagger-Bulk-CSV; eine Datei ohne Rollen-Zeile ändert nichts, eine Datei, die mehr als die Hälfte der alten Zuordnungen entfernen würde, braucht `--force`; nur die Rollen des Studios, andere Kategorien werden
gezählt und genannt), `import-rulings DATEI...` (ersetzt die Rulings je Quelldatei, andere Dateien bleiben;
`GET /api/cards/{card_id}/rulings`), `relink-corpus`, `data-report`.

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
| `import-tagger-roles FILE.csv` | the tagger bulk (`oracle_id`, `category`, `bulk_label`) as a full snapshot of its own scope, origin `CROSSWALK_NORMALIZED`; only the Studio roles, other categories are counted | normalized |
| `import-rulings FILE.jsonl [...]` | official rulings (JSON lines) into `card_ruling` (schema 13); replaces the stored rulings of each given file (by file name) and keeps those of other files; a file without a ruling is refused; `GET /api/cards/{card_id}/rulings` | normalized |
| `relink-corpus` | gives source-deck cards without an oracle id theirs by name and rebuilds deck statistics and roles per deck (also runs at the end of `import-scryfall` and `import-decklists`) | derived |
| `import-all --collection X.xlsx --scryfall BULK --research DIR --commander NAME [--decklists DIR ...]` | every step above in order, then the completeness report (`import_report.json`, `GET /api/import-report`); see "Erste Einrichtung" | none (report) |
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
`GET /api/cards/{card_id}/universe?profile=NAME`,
`GET /api/cards/{card_id}/cooccurrence?profile=NAME&limit=25`.

### Strength index ("Stärke-Index", schema 11)

A configurable estimate of card strength per commander, built from usage signals. It is
`DERIVED_DESCRIPTIVE`. It is not a measured win rate and not a statement about outcomes; the
outcome-based evidence field stays `UNRATED`, and the counted "Verbreitung" column is unchanged.

Import (all files optional, split parts `<name>_1.csv`, `_2.csv` are read in number order;
price columns are never read):

```
python -m commander_lab.studio import-signals FOLDER --commander NAME [--append]
```

The command reports rows read, written and skipped per file. Signals are stored in
`card_signal(commander_name, signal, card_name, value, numerator, denominator, source_id)`:
`edhrec_commander_inclusion|synergy` and `edhrec_bracket_inclusion:<core|upgraded|optimized|cedh>`
per commander of the files, `edhrec_global_inclusion` and `spellbook_variants` commander
independent (commander name empty), and
`tournament_lists` (lists of the commander that contain the card over all its lists, main and
commander section only) under `--commander` (required; matched case-insensitively against the
commander names the store already knows), `edhrec_salt` (published top list, commander
independent) and `edhrec_combo_decks` (combos EDHREC lists for the commander; `numerator` is the
number of combos of the card, `value` the largest deck count). The tournament and combo files of
a commander are found by its name (`topdeck_chulane_decks.csv`, `edhrec_chulane_combos.csv`) or
named with `--tournament-file` and `--combos-file`. The commander
file's lift column and the spellbook file's partner count are not stored: no strength
component reads them, and the values remain in the source files (the lift also in the
observation pipeline). Stores imported earlier keep the rows of the two signals they
already hold until `card_signal` is rebuilt; nothing reads them. A value the
source does not publish is NULL (unknown), never 0; a card a source does not list has no row;
rows of a source fetch that was not `AVAILABLE` are not stored. The tournament player column
is never stored. Re-importing replaces the rows of the signals and commanders it writes
(`--append` only adds and updates). A file with no importable row is reported as `NO_ROWS` and
changes nothing; rows of the same signals that remain from other source files are counted as
`stale_rows`; skipped rows and the reasons a value stayed unknown are counted per reason;
a BOM at the start of a CSV is accepted; each part of a split file keeps its own source.

Formula, per commander (`strength.py`, pure):

1. Share signals (inclusion, bracket inclusion, deck lists, tournament lists, global) use the
   lower bound of the 95 % Wilson interval of numerator/denominator, so a small sample does
   not rank high by chance. Synergy and combo counts are used as published.
2. Each value becomes a percentile rank (0..1) among the commander's legal pool cards that
   have a value for that signal; ties share the mean rank.
3. Index = weighted mean of the present percentiles x 100 (one decimal); a missing component
   is left out and the weights are renormalised. `coverage` = weight of present components /
   weight of all components with a weight above 0.
4. Tier `U` ("zu wenig Daten") when coverage is below `min_coverage` or fewer than
   `min_components` weighted components are present; otherwise S/A/B/C/D by the index cuts
   (default 90/75/55/35). A card absent from a source is a missing observation: it lowers
   the coverage, never the percentile.

Settings: a weight per component (commander inclusion 3, bracket inclusion 2, deck-list
universe 2, synergy 1, tournament lists 1, global inclusion 1, combos 1, simulation 0), the
bracket (`core`, `upgraded`, `optimized`, `cedh`, `none`), the universe profile (the page uses
the Universum selector), `min_coverage` (0.4), `min_components` (2) and the cuts. Presets:
Ausgewogen, Commander-nah, Turniernah. Owner settings are saved by name. The simulation
component is `NOT_COLLECTED`: stored simulation rows are not an outcome model.

The Owner's marks (favorite, excluded, note) never enter the index (Owner decision B4;
pinned by a test). On the page the settings panel "Stärke-Index" holds preset, bracket, one
input per weight, the minimum coverage and a named save; the choice is remembered in the
browser. The new column sorts by index with tier U last; the card drawer lists every
component with value, numerator/denominator, Wilson bound, percentile, weight and status.

Routes: `POST /api/strength` (body `commander` plus at most one of `preset`, `profile`,
`settings`; needs the `X-Studio` header like every non-GET route, 422 without commander),
`GET /api/strength/presets`, `GET /api/strength/profiles`,
`GET|PUT|DELETE /api/strength/profiles/{name}`.

### Data report

`data-report` prints JSON with numbers only: every figure is a count with its denominator, a
missing value is counted as unknown (never as zero), and no card name, deck address or note text
is included, so the output can go into an issue or a shared document. `roles.fingerprint` holds
hashes of `card_role_claim` (in total and per origin and scope), `card_role` and
`corpus_deck_role`: run the report before and after an import. An import limited to one scope
must leave the hash of every other scope unchanged, and an identical second import must leave
all hashes unchanged. The report states what
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
- Drafts are kept automatically; a saved state is an immutable revision. Variants are named
  branches of a deck. Export as text list or as deck snapshot for the simulator.
