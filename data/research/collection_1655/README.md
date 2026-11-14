# Collection 1,655 — the Owner's inventory workbook as sheet CSVs

The complete, corrected inventory workbook of the CPL collection
(1,655 card identities, 1,870 physical lots, 2,233 counted copies;
status 2026-11-12, "15 Fotos A Box korrigiert"), exported as one
CSV per workbook sheet. This is the dataset the Studio store's `card`
and `inventory` tables are built from.

**Owner decision (M, 2026-11-13):** the collection file and the
ownership data (lots, counts, locations) may be kept in this
repository — the repository is being switched to private, and all
agents working on the project are to see and use the full data. This
folder is the in-repo form of that decision. (Third-party names are
unaffected by the decision: player names in tournament data stay
replaced with neutral "Liste N" labels, see issues #1108 and #1263.)

## Files

All 12 sheets of the workbook, verbatim (header + data rows):
`00_README_STATUS` (26 rows), `01_CARD_IDENTITY` (1,655),
`02_PHYSICAL_LOTS` (1,870), `03_LOCATIONS` (4), `04_INVENTORY_EVENTS`
(485), `05_INVENTORY_CURRENT` (1,655), `06_SOURCES` (1,366),
`07_DATA_QUALITY` (33), `08_NONPLAYABLE_OBJECTS` (3),
`09_PRINTING_DETAILS` (283), `10_PHOTO_AUDIT_20261111` (387),
`11_QA_RECONCILIATION` (22).

## Load

The Studio importer reads the workbook (XLSX), not CSVs, so rebuild
the workbook first (new script, assembles exactly these CSVs):

```bash
python scripts/build_inventory_workbook.py --out /tmp/collection_1655.xlsx
python -m commander_lab.studio import-inventory /tmp/collection_1655.xlsx
```

Acceptance: `card` = 1,655 rows, `inventory` = 1,655 rows with
observed copies summing to 2,233 and lots summing to 1,870.

## Notes

- The workbook is the authoritative source for the collection; the
  store is derived from it, never the other way round.
- One known open data point: Avacyn's Pilgrim carries color identity
  `G` in this workbook vs. `WG` at Scryfall — an Owner decision that
  is still open; the workbook value stands until then.
- The Deckbuild Studio project's separate, smaller collection is a
  different dataset and is not part of this folder.
