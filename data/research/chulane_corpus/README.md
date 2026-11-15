# Chulane decklist corpus — the full counted decklists

The canonical Chulane corpus itself: 10,551 public decklists
(2,300 EDHREC bracket-classified + 7,528 EDHREC unclassified + 723 Archidekt)
as normalized per-deck JSON files —
913,063 card rows in the Studio store, 10,150 canonical decks
(401 duplicates: 384 within the classified corpus — 162 spelling-identical,
and 222 that are the same physical deck under the other source's spelling
of a two-part card; since #1394 the content fingerprint is re-derived over
oracle ids at link time, so the two spellings collapse — plus 17 involving
the unclassified cohort). This is the deck population the counted
spread ("Verbreitung, gezählt") and, per the Owner decision of
2026-11-13, the decklist component of the strength index are computed
from. Until now only the derived inclusion count file
(`data/research/chulane_decklist_inclusion_20261112.csv`, a subset
export of 1,862 decks) was in the repository; the corpus itself
existed only locally, so no fresh checkout could recount it.

## Layout

```text
edhrec/     cedh 233 · core 558 · exhibition 45 · optimized 700 · upgraded 764 · unclassified 7528
archidekt/  bracket1 28 · bracket2 117 · bracket3 269 · bracket4 263 · bracket5 46
```

The `unclassified` folder (added 2026-11-15, issue #1388) holds the EDHREC
decks whose index entry carries no bracket: their files state
`"bracket": null` and they join no bracket cohort in the store — only
`source:edhrec`, `variant:unclassified` and `commander:chulane`. They widen
the whole-corpus universe; every bracket cohort and bracket universe is
exactly as large as before them.

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

Acceptance: `corpus_deck` = 10,551 (10,150 with `duplicate_of IS NULL`),
`corpus_deck_card` = 913,063, `corpus_cohort` = 33,953; after step 2,
912,890 of 913,063 card rows carry an `oracle_id` (99.98%, measured on a
fresh store built 2026-11-15; the residue is names with no unambiguous
catalog match). Re-importing a folder replaces its decks by `deck_id`.

## Notes

- Refresh 2026-11-15 (issue #1388): +19 lists harvested since the first
  capture (15 EDHREC-classified, 4 Archidekt with `edhBracket`); report:
  `docs/research/CORPUS_REFRESH_1388_20261115.md`. Decks that fall out of
  EDHREC's rolling two-year index window are never removed from the corpus.
- The counted universe used by the tier list (10,128 decks) is this
  corpus minus the decks the universe profile filters out — a store
  view, not a different dataset. Its bracket universes are unchanged
  by the unclassified cohort (bracket 1–5: 59 / 608 / 889 / 814 / 256).
- The all-commander harvest (issue #1210) stays paused by Owner
  decision; its raw local material is intentionally not part of this
  dataset.
