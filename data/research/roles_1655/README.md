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
| `roles_s4_tagger_expansion_wug.json` | `SCRYFALL_TAGGER_ORIGINAL` | `WUG` | 15,422 |
| `roles_s5_oracle_expansion.json` | `ORACLE_TEXT_REVIEW` | `COLLECTION1655_RULES_1` | 1,570 |
| `gap_list_chulane_pool.csv` | — (historic #1261 analysis artifact, 17-role baseline) | Chulane pool | 369 cards without any role |

`roles_s1`–`roles_s3` hold the 17 initial Studio roles (2026-11-12);
`roles_s4` and `roles_s5` (2026-11-15, issue #1353 part C) expand the
Studio vocabulary (`commander_lab.studio.roles.ROLES`) from 17 to 34
roles using canonical Scryfall `otag:` queries (`id<=wug f:commander`)
plus deterministic Oracle-text rules (`classify_oracle_roles`).

## Load

```bash
python -m commander_lab.studio import-roles data/research/roles_1655/roles_s1_tagger_bulk_crosswalk.json
python -m commander_lab.studio import-roles data/research/roles_1655/roles_s2_tagger_search_wug.json
python -m commander_lab.studio import-roles data/research/roles_1655/roles_s3_oracle_heuristic.json
python -m commander_lab.studio import-roles data/research/roles_1655/roles_s4_tagger_expansion_wug.json
python -m commander_lab.studio import-roles data/research/roles_1655/roles_s5_oracle_expansion.json
```

Acceptance after loading all five files (`import-all --from-repo` discovers
`roles_*.json` automatically):
- 21,272 `card_role_claim` rows (before: 4,280);
- Chulane 927-card pool coverage rises from **558 / 927 (60.2 %)** to
  **817 / 927 (88.1 %)** (34 roles: 20 with ≥ 30 pool cards, 11 with
  10–29, 3 with < 10);
- Importing any file twice leaves the store unchanged (0 added, 0 removed).

## Notes

- Because `roles_s4` only lists the 17 expansion roles (disjoint from
  `roles_s2`) and `roles_s5` uses its own `COLLECTION1655_RULES_1` scope
  key (disjoint from `roles_s3`), all five files import together cleanly
  without `--replace-scope`.
- Remaining gap (110 / 927 cards) consists of vanilla creatures with empty
  Oracle text, pure mana-producing lands without additional utility, and
  keyword-only / static cards without an active functional role; the UI
  fallback stays "no known function" (`unbekannt`, never 0).
- `counters` in `roles_s4` merges `otag:gives-pp-counters` and
  `otag:gains-pp-counters` under canonical slug `gives-pp-counters`.
- The older `data/research/deckbuilder_1655/card_tagger_bulk_1655.csv`
  also contains `mill`, `sacrifice_outlet`, `anthem`, and `discard`;
  `import-tagger-roles` imports the CSV directly for roles in `ROLES`.

