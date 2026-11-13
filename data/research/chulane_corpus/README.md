# Chulane decklist corpus — the full counted decklists

The canonical Chulane corpus itself: 3,004 public decklists
(2,285 EDHREC + 719 Archidekt) as normalized per-deck JSON files —
266,539 card rows in the Studio store, 2,845 canonical decks
(159 exact duplicates). This is the deck population the counted
spread ("Verbreitung, gezählt") and, per the Owner decision of
2026-11-13, the decklist component of the strength index are computed
from. Until now only the derived inclusion count file
(`data/research/chulane_decklist_inclusion_20261112.csv`, a subset
export of 1,862 decks) was in the repository; the corpus itself
existed only locally, so no fresh checkout could recount it.

## Layout

```text
edhrec/     cedh 233 · core 557 · exhibition 45 · optimized 695 · upgraded 755
archidekt/  bracket1 28 · bracket2 117 · bracket3 267 · bracket4 261 · bracket5 46
```

The files are the harvest's normalized form (no author fields; deck
titles are the sources' public titles). Bracket/variant folders are
cohorts — never merge them into one denominator silently; the store
keeps them as separate `corpus_cohort` rows.

## Load (fresh store, in this order)

```bash
# 1) all ten folders via the corpus loader script (uses the import-decklists
#    API directly; see the script header for why the CLI guard cannot be used:
#    22 Archidekt lists state a different commander and carry Chulane in the
#    mainboard — they belong to this corpus and have no commander binding)
python scripts/import_chulane_corpus.py
# 2) fill corpus_deck_card.oracle_id (needs card + scryfall_card present,
#    i.e. inventory and Scryfall imports done first)
python scripts/map_corpus_oracle_ids.py
```

Acceptance: `corpus_deck` = 3,004 (2,845 with `duplicate_of IS NULL`),
`corpus_deck_card` = 266,539, `corpus_cohort` = 11,297; after step 2,
266,366 of 266,539 card rows carry an `oracle_id` (99.94%, measured on
the live store; the residue is names with no unambiguous catalog
match). Re-importing a folder replaces its decks by `deck_id`.

## Notes

- The counted universe used by the tier list (2,823 decks) is this
  corpus minus the decks the universe profile filters out — a store
  view, not a different dataset.
- The all-commander harvest (issue #1210) stays paused by Owner
  decision; its raw local material is intentionally not part of this
  dataset.
