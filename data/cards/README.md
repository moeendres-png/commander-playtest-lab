# Local card-data subset

`oracle_subset.json` contains the 161 unique card names needed by the current RogShai snapshot and
preserved historical Korvold regression fixtures. It is a local project dataset, not a complete MTG Oracle database.

Entries marked `project_inferred` are sufficient to enforce the already validated current deck color
boundaries but must be replaced or enriched when an authoritative version-pinned Oracle snapshot is
added. The importer and validator APIs do not depend on the source vendor.
