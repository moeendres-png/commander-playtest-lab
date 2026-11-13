# Role claims for the 1,655-card collection (`roles_1655`)

The curated role-claim files behind the Studio store's `card_role_claim`
table (4,280 claims over 983 cards, 17 roles). Until now they existed only
in local working folders; the coverage report in
`data/research/chulane_role_coverage_1261.{json,md}` describes them but
does not contain them.

## Files

| File | Origin (`role_origin`) | Scope | Claims |
|---|---|---|---:|
| `roles_s1_tagger_bulk_crosswalk.json` | `CROSSWALK_NORMALIZED` | `COLLECTION1655` | 1,627 |
| `roles_s2_tagger_search_wug.json` | `SCRYFALL_TAGGER_ORIGINAL` | `WUG` | 1,626 |
| `roles_s3_oracle_heuristic.json` | `ORACLE_TEXT_REVIEW` | `COLLECTION1655` | 1,027 |
| `gap_list_chulane_pool.csv` | — (analysis artifact) | Chulane pool | 369 cards without any role |

The three JSONs are in the `studio-roles` format that
`commander_lab.studio.roles.read_role_file` parses. Fetched/built
2026-11-12 from the Scryfall Tagger bulk, Tagger searches and an
oracle-text review pass; see `docs/` research notes for the method.

## Load

```bash
python -m commander_lab.studio import-roles data/research/roles_1655/roles_s1_tagger_bulk_crosswalk.json
python -m commander_lab.studio import-roles data/research/roles_1655/roles_s2_tagger_search_wug.json
python -m commander_lab.studio import-roles data/research/roles_1655/roles_s3_oracle_heuristic.json
```

Acceptance after loading into a store that holds the collection:
`card_role_claim` = 4,280 rows, `card_role` = 1,750 rows (983 distinct
cards). Importing the same file twice leaves the store unchanged.

## Notes

- The 369-card gap in `gap_list_chulane_pool.csv` is proven not closable
  from the permitted sources (both closure routes yield 0 new claims,
  PR #1269); the honest UI fallback is "no known function", not 0.
- The older `data/research/deckbuilder_1655/card_tagger_bulk_1655.csv`
  is the Tagger bulk export these files were derived from; the importer
  takes the JSON form above, not the CSV.
