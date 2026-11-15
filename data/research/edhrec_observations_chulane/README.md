# EDHREC theme-table observations for Chulane (`edhrec_observations_chulane`)

The source table behind the Studio store's `observation` layer:
27,139 card × theme rows harvested from the EDHREC Chulane theme pages
(147 cohorts of the form `edhrec:chulane-teller-of-tales/<theme>`).
Each row yields two observations (`inclusion_pct` and `lift`), i.e.
54,278 observations in the store. Until now the file existed only in
local working folders (its store `source` title is
`edhrec_table_chulane.csv`).

## Files

`edhrec_table_chulane_1.csv`, `_2.csv`, `_3.csv` — one logical CSV
(header `card_id, card_name, theme, url, snapshot_utc, num_decks,
potential_decks, inclusion_pct, lift`) split into three parts of
9,047 / 9,047 / 9,045 data rows because of per-file upload limits.
Concatenating the data rows of the three parts in order reproduces the
original file exactly.

## Load

```bash
python -m commander_lab.studio import-edhrec data/research/edhrec_observations_chulane/edhrec_table_chulane_1.csv
python -m commander_lab.studio import-edhrec data/research/edhrec_observations_chulane/edhrec_table_chulane_2.csv
python -m commander_lab.studio import-edhrec data/research/edhrec_observations_chulane/edhrec_table_chulane_3.csv
```

Acceptance: `observation` = 54,278 rows (27,139 per metric), all with
`data_class = ORIGINAL_SOURCE`. An empty `lift` in the source stays
unknown (never 0). Re-importing a part replaces exactly that part's
observations (the importer deletes by source id first).

## Notes

- Snapshot date 2026-11-11/12. A second snapshot is only meaningful at
  roughly monthly distance (see the snapshot/time-series item in
  issue #1261); do not overwrite this snapshot with a fresher harvest —
  add a new dated folder instead.
- Observations are source data for analysis views; they are not a
  strength-index component of their own.
- **Listing completeness & threshold audit (#1353 part B,
  `edhrec_chulane_threshold_audit.json`):** The 2026-11-12 harvest in
  `commander_card_signals_*.csv` and the `chulane-teller-of-tales`
  theme rows here hold **all 12 cardlists** of the EDHREC Chulane page
  with exact parity (241 distinct cards, symmetric diff = 0; live check
  on `2026-11-15`: 242 cards, only `Carpet of Flowers` added outside the
  1,655 collection). Pool coverage is **68 / 922 ranked cards**
  (**71 / 927** including 3 basic lands), before and after. Non-tag
  subpages (`/creatures.json`, `/top-cards.json`, `/lands.json`,
  `/average-deck.json`) return HTTP 403. Regular cardlists enforce a
  **~5.0 %** minimum share (`505 / 9,824 = 5.1405 %` main page;
  `5.0179 %–5.1502 %` across the four brackets) plus a 50-card cap on
  `creatures` and `lands`; `newcards` reaches down to `29 / 1,221 =
  2.3751 %` (`2.0833 %–3.4783 %` across brackets).

