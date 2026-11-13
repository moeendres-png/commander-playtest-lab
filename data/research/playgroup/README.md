# Playgroup.gg Card Atlas — raw records for the 1,655-card collection

The full Card Atlas harvest behind the Studio store's Playgroup tables
(`playgroup_card_atlas` 1,655 rows, `playgroup_top_commander` 8,901 rows,
`playgroup_final_zone` 3,494 rows), collected 2026-11-12 with
`scripts/collect_playgroup_card_atlas.py` (whose default `--out-dir` is
this folder). Until now the records existed only in local working
folders; the repository held only the commander aggregates
(`data/research/deckbuilder_1655/playgroup_commander_stats.csv`, which
no importer reads) and the derived strength-signal file (PR #1274).

## Files

`playgroup_card_atlas_1.jsonl`, `_2.jsonl`, `_3.jsonl` — one JSON card
record per line (725 / 712 / 218 records, sorted by card name), split
because of per-file upload limits. Each record carries its nested
`top_commanders` and `final_zones` lists, which is the form
`import-playgroup-atlas` expects; the flat per-table TSV exports from
the harvest cannot populate the two nested tables and are therefore
not the canonical form.

Fetch status in this snapshot (updated 2026-11-13 for the 71 unobserved cards):
724 OK, 861 PARTIAL (small sample, `insufficient_sample`), 69 NO_DATA, 1 NOT_FOUND (Craftwork Crusher).
All 71 rechecked cards carry their explicit `retrieved_at_utc` timestamp; Infectious Rage
moved from NO_DATA to PARTIAL (times_brought=1, decks_running=1); 69 cards confirmed quellenleer (NO_DATA)
and 1 card confirmed not found (NOT_FOUND).
The 71 dated recheck records are also provided as `playgroup_card_atlas_recheck_71.jsonl`.

## Load

```bash
python -m commander_lab.studio import-playgroup-atlas data/research/playgroup/playgroup_card_atlas_1.jsonl
python -m commander_lab.studio import-playgroup-atlas data/research/playgroup/playgroup_card_atlas_2.jsonl
python -m commander_lab.studio import-playgroup-atlas data/research/playgroup/playgroup_card_atlas_3.jsonl
```

Acceptance: `playgroup_card_atlas` = 1,655, `playgroup_top_commander`
= 8,901, `playgroup_final_zone` = 3,494 rows. The parts hold disjoint
cards, so the three imports compose; re-importing a part upserts its
cards and rebuilds their nested rows.

## Notes

- Observed Playgroup values are measurements from real games; the
  PARTIAL rows carry `insufficient_sample` and must not be read as 0.
- The strength-index component derived from this data
  (`playgroup_card_atlas_signals.csv`, shrinkage below n = 25) is a
  separate dataset in PR #1274.
