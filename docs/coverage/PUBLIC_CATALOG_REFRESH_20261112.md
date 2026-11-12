# Public engine and pilot catalogs — 2026-11-12

Refs #1227. Measurement packet: [PUBLIC_CATALOG_REFRESH_20261112.json](PUBLIC_CATALOG_REFRESH_20261112.json).

The missing catalog entries were a subset-export gap. All 230 locally reported missing
identities already have active registrations in the pinned engine, construct successfully,
and import through `XmageDeckImporter` into concrete 100-card Commander fixtures. No fork
card implementation, bridge runtime code, engine pin or qualification record changed.

The public engine catalog now covers every distinct database card name, independently of
any inventory or deck selection. The pilot catalog extends from an archived Scryfall bulk,
filtered to English paper cards with legal/banned/restricted Commander status and excluding
non-card layouts. Banned cards can have printed knowledge; the engine still decides legality.
Existing 7,231 pilot entries are retained byte-equivalent as objects, and all 7,231 previous
engine fact objects have equivalent normalized entries. The local inventory check changes
from 1,425 OK / 230 NO_CARD_FACTS to 1,655 OK, without publishing an inventory list.

`OK` is catalog readiness. Registration, construction and deck import do not prove every
ability or interaction. Gameplay completeness remains UNKNOWN and strength UNDECIDED.
These local observations are not PB-03 qualification credit.

## Provenance and reproduction

The source lock and output hashes are in the JSON packet. The engine source was freshly
built at the exact production pin with `mvn -B -ntp install -am -pl
Mage.Sets,Mage.Server.Plugins/Mage.Deck.Constructed,Mage.Server.Plugins/Mage.Game.CommanderFreeForAll,Mage.Server.Plugins/Mage.Game.CommanderDuel`.
The unchanged bridge was built and tested with `mvn -B -ntp verify`.

The public Scryfall snapshot is `default-cards-20261109100640`, supplied as 44 archived
JSONL parts. Their exact byte hashes are in `pilot_card_knowledge.json.bulk_refresh`.
The date is declared from the archive filename; there was no live Scryfall retrieval and
the original gzip was unavailable for independent comparison. Documentation:
https://scryfall.com/docs/api/bulk-data. No named-card API requests were made.

Use `scripts/export_xmage_card_facts.py --all-cards --db DB --h2-jar H2_JAR
--engine-commit COMMIT --engine-source-url https://github.com/moeendres-png/mage --out FACTS`.
Build DB from a fresh source-locked scanner run. The exporter measures the copied DB hash;
a caller-declared commit alone does not attest the DB's build identity.

Use `scripts/build_pilot_card_knowledge.py --all-cards --bulk-file PART ...
--snapshot-at 2026-11-09 --snapshot-description DESCRIPTION --output CATALOG`.
Seed CATALOG with the current catalog when newer entries must be retained. Offline mode
never falls back to a network lookup. Public API use requires explicit opt-in and public inputs.

The standalone diagnostic sources are `scripts/diagnostics/RegisteredCardProbe.java` and
`PrivateImportProbe.java`. Compile with the exact engine/bridge runtime classpath. Run the
registration probe in a new working directory without `db/`; it creates the scanner DB,
checks all public names and ECL/FRA/SPM printings, and rejects an unknown name and an
invalid constructor. Nonzero exit covers scanner, printing and construction failures.
The import probe accepts a local JSON array of engine names and a local output path;
it prints counts only. Keep its input and detailed output outside Git. It also rejects
an invented name and a mismatched combined identity. Neither probe runs game behavior.
