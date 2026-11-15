# Corpus fill — counted Chulane corpus as decklist universes (#1387)

Provenance: **counted locally from the repository corpus** (`data/research/chulane_corpus`,
in a built Studio store). These are **not EDHREC figures**: nothing here was published by
EDHREC, and the file is imported under its own signal family
(`decklist_universe:corpus:<bracket>`), never under an `edhrec_*` signal. It fills the
cards EDHREC's commander page does not list (its publication threshold, #1377) with a
counted value of the local corpus instead of leaving them unknown.

## File

`chulane_corpus_decklist_inclusion_20261115.csv` — the counted deck-list format of
`signals.import_signals` (columns `card_name, source, bracket, decks_with_card,
universe_decks, share, universe_snapshot`), counted 2026-11-15 with
`scripts/build_corpus_fill.py` from a store built by `import-all --from-repo`
(Scryfall oracle bulk as the card catalog). One file, six universes, all with
`source = corpus`:

| bracket | decks (denominator) | cards with a row | snapshot |
|---|---|---|---|
| `1-5` (whole corpus) | 2,823 | 9,043 | `universe:efd06eb1bffcbb5e:2823` |
| `1` | 66 | 2,298 | `universe:35cc9a8f89218feb:66` |
| `2` | 647 | 6,635 | `universe:9f35d6f9db2a3c54:647` |
| `3` | 959 | 5,548 | `universe:c7aa3e1df7876e27:959` |
| `4` | 891 | 3,980 | `universe:6d4cea074c5d3739:891` |
| `5` | 267 | 1,347 | `universe:e11f1264894b2a8c:267` |

## Method (the repo's own counting rules)

- Universe: `universe_choice.local_spec` resolved by `universe.resolve_universe`
  (decks bound to exactly this commander, deduplicated by content fingerprint);
  bracket universes resolve the same spec plus the `bracket:<n>` cohort, exactly as
  `corpus_signals` counts its cohorts. Bracket denominators therefore do **not** sum
  to 2,823 (they sum to 2,830): seven duplicate twins carry different stated
  brackets, and a cohort resolution keeps a twin the whole-corpus resolution
  deduplicates into another cohort. Cohorts are never added (AGENTS.md §1).
- A deck counts for a card when a row of a counted section (`main`, `mainboard`,
  `commander`, `companion` — `store.COUNTED_SECTIONS`) names it with quantity > 0.
  Rows are grouped by oracle id; the 160 counted rows without an oracle id (74
  distinct listed names, mostly token names that deck lists carry in their main
  section — the 2026-11-12 counted file lists the same names) keep their listed name.
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
python scripts/build_corpus_fill.py --data <store>
```
