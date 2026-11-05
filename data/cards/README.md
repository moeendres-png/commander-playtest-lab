# Local card-data subset

`oracle_subset.json` contains the 161 unique card names needed by the current RogShai snapshot and
preserved historical Korvold regression fixtures. It is a local project dataset, not a complete MTG Oracle database.

Entries marked `project_inferred` are sufficient to enforce the already validated current deck color
boundaries but must be replaced or enriched when an authoritative version-pinned Oracle snapshot is
added. The importer and validator APIs do not depend on the source vendor.

## `commander_flags.json` (Game Changers and Commander bans)

A small derived file: the Game Changers and the cards banned in Commander, taken from one stored
Scryfall Oracle bulk file (name, SHA-256 and date of the bulk file are in `source`). It is a label,
not a Commander Brackets rule: `scripts/deck_bracket_label.py DECK.json` prints a deck's Game Changer
count and its banned cards. Rebuild it with `scripts/build_commander_flags.py --bulk <file>` (the bulk
file is read from disk; the script makes no network call, and no deck or card list is sent to any
service). `--check` fails when the committed file no longer matches the bulk file.
