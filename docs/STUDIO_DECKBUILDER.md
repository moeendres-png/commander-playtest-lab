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
| `import-edhrec FILE.csv` | EDHREC rows with numerator, denominator, page | original |
| `import-edhrec-cardrecs FILE.csv` | normalized EDHREC recommendations across cohorts (`cardrecs_alle.csv`) | normalized |
| `import-edhrec-delta PATH` | EDHREC delta JSONL files (`10_EDHREC_STATISTICS_DELTA_*.jsonl`, preserving `NULL` per-card denominators and separate `synergy_pct`) | normalized |
| `import-selection FILE.json --deck-id ID --name NAME --commander NAME` | a saved selection as first deck revision (marking `reserve` entries in `card_mark`) | original |
| `import-lab-deck FILE.json [--deck-id ID] [--name NAME] [--branch BRANCH]` | an on-disk Lab deck snapshot (`DECKBAU_INTERFACE.md`) as a revision | original |
| `import-simulation PATH [--engine-pin PIN] [--pilot-policy POLICY]` | `deckbau_eval.py` JSON simulation reports into `simulation_run` / `simulation_card` | simulated result |
| `fetch-roles --identity WUG --out FILE.json [--replace-scope]` | public role tags (Scryfall tagger) for a color identity, written as a full snapshot of that identity and imported; the query names only the colors | original (public, community labels) |
| `import-roles FILE.json [--replace-scope]` | a role file (format below) as claims | original, normalized or derived, by the file's origin |
| `check-role-labels FILE` | compares the role query slugs with a list of official tagger labels (JSON list or one label per line) and names every slug that is not a label | none (report) |
| `fetch-images --commander NAME` | card images of the legal pool into the local cache | public images |
| `data-report` | counts-only report: what the store has, lacks and does not know (collection coverage, public card data age, roles per origin, corpus, observations with unknown times and small denominators, marks, simulation runs) plus hashes of the role tables | none (report) |

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
