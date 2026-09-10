# RQ-C2 Authority Baseline

All 37 RQ-C1 authority packets are verified against ONE coherent
official baseline unless an official update occurs mid-workstream (none
had occurred as of the final commit; this file would record both
versions plus impact if one did).

## 1. Comprehensive Rules baseline

- Document: Magic: The Gathering Comprehensive Rules.
- Effective date: **August 7, 2026** (stated in the document header).
- Retrieval source (first-party):
  `https://media.wizards.com/2026/downloads/MagicCompRules%2020260819.txt`
  (the `20260807` PDF edition and this TXT edition carry the same
  August 7, 2026 effective date; the TXT edition was used for
  section-existence verification).
- Retrieval date: 2026-09-10 (UTC).
- Retrieval method: direct HTTPS download from `media.wizards.com`;
  section headers and cited subrules verified by line-anchored lookup
  (`^<number>`) in the retrieved text.
- Working-copy integrity: sha256
  `4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f`
  (977,822 bytes / 9,397 lines).
- Currentness established: YES for 2026-09-10. Web search on 2026-09-10
  surfaced the 2026-08-07 edition as the newest published CR
  (next-older: 2026-06-19 edition). No newer edition appeared.
- Citation discipline (copyright): this pack records rule NUMBERS, short
  necessary excerpts, and precise paraphrases only. It does not clone
  official documents.

## 2. Official Oracle / rulings baseline

- Source: first-party Gatherer (`https://gatherer.wizards.com`), which
  states it "provides the official and most up-to-date card text and
  rulings directly from Wizards of the Coast."
- Retrieval date: 2026-09-10 (UTC). Retrieval method: direct page fetch
  (HTTP client + project web-fetch), rules text and Rulings sections
  extracted from server-rendered page content.
- Pages directly opened and verified (card — printing viewed):
  - Murder — ANB #53 (rules text verified; **0 rulings published**).
  - Cultivate — M21 #177 (rules text verified; 1 ruling, 2010-08-15,
    single-land placement).
  - Ornithopter — M11 #211 (type/rules/P-T verified; **0 rulings
    published** on the viewed page).
  - Turn to Frog — CLU #103 (6 rulings, 2014-07-18).
  - Council's Judgment — OTC #79 (6 rulings, 2020-08-07).
  - Delina, Wild Mage — AFR #138 (3 rulings, 2021-07-23).
  - Braids, Arisen Nightmare — EOC #82 (1 ruling, 2022-09-09).
  - Kokusho, the Evening Star — IMA #95 (**0 rulings published**).
  - Mana Crypt — 2XM #270 (1 ruling, 2020-08-07).
  - Humility — TPR #16 (3 rulings, 2006/2007/2009).
  - Doubling Season — FDN #216 (5 distinct rulings, 2024-11-08).
- Currentness established: YES for the above pages on 2026-09-10
  (Gatherer serves current Oracle by design; each page footer carries
  the 1993–2026 Wizards copyright notice).
- `OFFICIAL_SOURCE_ACCESS_BLOCKED`: NONE. Every card for which direct
  Gatherer verification was attempted was reachable. (Legacy
  `Details.aspx?multiverseid=` deep links return empty bodies via plain
  HTTP fetch; the current `{SET}/{lang}/{num}/{slug}` page shape works.
  Council's Judgment required resolving the canonical slug
  `councils-judgment` via Gatherer search. No card needed the blocked
  path, so no packet carries this status.)

## 3. Secondary crosscheck (NOT authority)

- Scryfall API (`https://api.scryfall.com/cards/named?exact=`), one
  request per exact corpus card name, 2026-09-10: **49/49 resolved**.
- Role: `SECONDARY_METADATA_CROSSCHECK` — Oracle-text comparison target
  and `oracle_id` gap-fill for the two RQ-C1 entries that carried none
  (Murder, Cultivate). Wherever Scryfall and Gatherer were both read
  for the same card, they agreed.
- Snapshot integrity (working file, not a corpus artifact): sha256
  `17ae9c5cba44b9c2533eb5e604d6a05567654d45384237d1d73a44cfadf2f8e9`.

## 4. Baseline stability during the workstream

No official CR or Oracle update was observed between work start and
pack completion. All packet citations refer to the August 7, 2026 CR
baseline above. If Sol adjudicates against a newer CR, the rule-number
mapping in `RQ_C2_RULE_REFERENCE_INDEX.json` is the re-check surface
(each entry carries its baseline edition).
