# Local card-data subset

`oracle_subset.json` contains only the 161 unique card names used by the current Korvold and RogShai
snapshots. It is a local project dataset, not a complete MTG Oracle database.

Entries marked `project_inferred` are sufficient to enforce the already validated current deck color
boundaries but must be replaced or enriched when an authoritative version-pinned Oracle snapshot is
added. The importer and validator APIs do not depend on the source vendor.
