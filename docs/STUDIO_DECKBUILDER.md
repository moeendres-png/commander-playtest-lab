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
| `import-scryfall oracle-cards.jsonl.gz` | public card data; links the collection by exact name | original (public) |
| `import-corpus-register FILE.csv`, `import-corpus-cards FILE.csv` | source decks and their cards | normalized |
| `import-cohort FILE.csv --name NAME` | a named group of source decks | normalized |
| `import-edhrec FILE.csv` | EDHREC rows with numerator, denominator, page | original |
| `import-selection FILE.json --deck-id ID --name NAME --commander NAME` | a saved selection as first deck revision | original |
| `fetch-roles --identity WUG --out FILE.json` | public role tags (Scryfall tagger) for a color identity; the query names only the colors | original (public, community labels) |
| `fetch-images --commander NAME` | card images of the legal pool into the local cache | public images |

Card facts shown in the builder (color identity, legality, type, text, mana value) come from
the public card data once a card is linked; the workbook stays the source of what is owned.
`import-scryfall` reports every card whose workbook facts differ.

Only image requests leave the machine, and they name single public cards (Owner exception in
`AGENTS.md` §12). The image host is fixed in `images.py`.

## Start

`python -m commander_lab.studio serve --open` (Windows: `scripts/studio_start.ps1`). The
server listens on `127.0.0.1` only, rejects other host names, and accepts writes only from its
own page.

## What the builder shows

- The legal pool for the commander with full card images or as a table with selectable
  columns; filters for text, color, type, mana value, free copies, favorites.
- The deck list by card type, with the data check (100 cards, commander, color identity,
  singleton, legality, ownership, free copies). The check reads stored facts; the Rules Core
  stays the binding check before play.
- Counts of the deck: curve, types, color symbols and mana sources, and role counts (ramp,
  card draw, removal ...) next to the median of the chosen group of source decks. Roles are
  public community labels, not ratings, and not every card is labelled.
- Comparison with the source decks: per group (all, play groups, named cohorts) the number of
  decks that play a card, always with the denominator, and median and middle half of lands,
  creatures and mana value. Groups below 30 decks are marked. These are frequencies, not
  ratings.
- Drafts are kept automatically; a saved state is an immutable revision. Variants are named
  branches of a deck. Export as text list or as deck snapshot for the simulator.
