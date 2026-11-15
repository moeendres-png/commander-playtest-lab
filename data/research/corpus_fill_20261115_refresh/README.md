# Corpus fill, refreshed — counted Chulane corpus as decklist universes (#1388 step 5)

Provenance: **counted locally from the repository corpus** (`data/research/chulane_corpus`,
in a built Studio store). These are **not EDHREC figures**: nothing here was published by
EDHREC, and the file is imported under its own signal family
(`decklist_universe:corpus:<bracket>`), never under an `edhrec_*` signal. It fills the
cards EDHREC's commander page does not list (its publication threshold, #1377) with a
counted value of the local corpus instead of leaving them unknown.

This is the refresh of `data/research/corpus_fill_20261115/` (#1387) after the corpus
completion of #1388 (PR #1405): the 7,528 bracket-less EDHREC decks now sit in the corpus
as their own cohort (`edhrec/unclassified`), so the whole-corpus universe covers the full
local stock. The 2026-11-15 first fill stays untouched as the record of the earlier
corpus. On a store build the two folders import in name order and this file **replaces**
the first fill's rows for the six corpus universes (the decklist import replaces per
(commander, signal)); the counted universes then carry this file's snapshots.

## File

`chulane_corpus_decklist_inclusion_20261115.csv` — the counted deck-list format of
`signals.import_signals` (columns `card_name, source, bracket, decks_with_card,
universe_decks, share, universe_snapshot`), counted 2026-11-15 with
`scripts/build_corpus_fill.py` from a store built by `import-all --from-repo`
(Scryfall oracle bulk as the card catalog; corpus stand: 10,551 corpus decks,
10,150 canonical). One file, six universes, all with `source = corpus`:

| bracket | decks (denominator) | cards with a row | snapshot |
|---|---|---|---|
| `1-5` (whole corpus) | 10,128 | 13,248 | `universe:5932ada7f8e25813:10128` |
| `1` | 59 | 2,298 | `universe:40a64995966ebe71:59` |
| `2` | 608 | 6,643 | `universe:1087ca4c1b48c977:608` |
| `3` | 889 | 5,584 | `universe:ec17ecc84300b3f1:889` |
| `4` | 814 | 3,986 | `universe:20598a8994588940:814` |
| `5` | 256 | 1,347 | `universe:9472b4cd2a300df9:256` |

33,106 rows in total (first fill: 28,851 over a whole-corpus denominator of 2,823).

## Method (the repo's own counting rules)

- Universe: `universe_choice.local_spec` resolved by `universe.resolve_universe`
  (decks bound to exactly this commander, deduplicated by content fingerprint);
  bracket universes resolve the same spec plus the `bracket:<n>` cohort, exactly as
  `corpus_signals` counts its cohorts. The bracket denominators do **not** sum to
  10,128 (they sum to 2,626): the unclassified cohort carries no bracket, and a few
  duplicate twins carry different stated brackets, so a cohort resolution keeps a
  twin the whole-corpus resolution deduplicates into another cohort. Cohorts are
  never added (AGENTS.md §1).
- A deck counts for a card when a row of a counted section (`main`, `mainboard`,
  `commander`, `companion` — `store.COUNTED_SECTIONS`) names it with quantity > 0.
  Rows are grouped by oracle id; the 160 counted rows without an oracle id in the
  whole-corpus universe keep their listed name — the same token-name class as the
  first fill (the import notice counts 167 stored rows across the six universes,
  68 of them in the whole-corpus universe, whose listed names match no catalog card:
  Food, Beast, Copy, Saproling, Clue, …).
- The count is complete: a card without a row in a universe is a **counted zero**
  of that universe's decks, not unknown (the decklist semantics). The commander's
  own card counts in every deck of every universe (verified at build and import).
- No synergy column: EDHREC synergy is a published figure against EDHREC's
  color-identity population; a single-commander local corpus has no such baseline,
  so no corpus synergy exists (see the report `docs/research/CORPUS_FILL_1387_20261115.md`).

## Regenerate

```bash
python -m commander_lab.studio --data <store> import-all --commander "Chulane, Teller of Tales" \
    --from-repo --scryfall <scryfall oracle bulk file>
python scripts/build_corpus_fill.py --data <store> \
    --out-dir data/research/corpus_fill_20261115_refresh --date 20261115
```

Verification of this refresh (cross-check against the EDHREC aggregates, fill and
tier-signal differences): `docs/research/CORPUS_FILL_REFRESH_1388_20261115.md`.
