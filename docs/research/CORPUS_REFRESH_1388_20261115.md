# Corpus refresh #1388 — the classified lists added since the first capture

Issue #1388, steps 1+2 restricted to the undisputed subset: only NEW
bracket-classified lists from the two proven routes (EDHREC index +
deckpreview, Archidekt `edhBracket` search + detail), harvested
2026-11-15. The unclassified mass (7,528 EDHREC stubs without a bracket)
is not part of this refresh; it waits on the owner decisions recorded in
the step-0 analysis. All figures are counts over the files or over fresh
stores built in this worktree; evidence class `DIRECTLY_VERIFIED` unless
noted.

## 1. Fresh target diff (measured, not taken over)

Step 0 (same day, ~2 h earlier) expected 13 new EDHREC stubs and +3
Archidekt decks. The fresh diff against the corpus files gave:

**EDHREC** — index of 2026-11-15: 9,819 stubs (step 0: 9,816). Corpus
holds 2,285 urlhashes; 2,276 of them are still in the index, all with an
unchanged bracket (0 reclassifications). New classified stubs whose
urlhash is not in the corpus: **15** — bracket 2 (core) 1, bracket 3
(upgraded) 9, bracket 4 (optimized) 5, bracket 5 (cedh) 0. That is +2
over the step-0 expectation (one upgraded, one optimized more), ordinary
daily churn of the rolling index; the 7,528 new unclassified stubs stay
untouched, as scoped.

**Archidekt** — `edhBracket` filter counts today: 28 / 117 / 269 / 262 /
46 (brackets 1–5, total 722). Corpus files: 28 / 117 / 267 / 261 / 46
(total 719). ID diff (global, not per folder): **4 new IDs** — bracket 3:
28360286, 28364312; bracket 4: 28362247, 28364495. One corpus deck of
bracket 4 no longer appears in the search results (count arithmetic
261 − 1 + 2 = 262); per the corpus rule it is of course not deleted.
No deck changed its bracket folder.

## 2. Harvest and normalisation

19 detail calls (15 deckpreview, 4 Archidekt details), ~1.5 s pacing,
browser user agent for deckpreview. The normalisation reproduces the
first capture's format exactly — verified beforehand on the one deck
that exists both as a step-0 raw probe and as a corpus file: the
reconstruction (commander first, then the preview's cardlist order;
`price`/`salt`/`savedate`/`tags`/`bracket` joined from the index stub;
`source_url` = preview URL plus the EDHREC UTM suffix) is byte-identical
to the stored file. Archidekt files take `card.oracleCard.name`,
categories and the companion flag from the detail response; no author
fields anywhere, as in the existing corpus.

Result: 19 new files, every EDHREC file with `karten_summe` 100 and
`parse_status` "ok", every Archidekt file with `summe_hauptdeck` 100.

| cohort | before | new | after |
|---|---|---|---|
| edhrec/core (B2) | 557 | 1 | 558 |
| edhrec/upgraded (B3) | 755 | 9 | 764 |
| edhrec/optimized (B4) | 695 | 5 | 700 |
| edhrec/cedh (B5), edhrec/exhibition (B1) | 233 / 45 | 0 | 233 / 45 |
| archidekt bracket3 | 267 | 2 | 269 |
| archidekt bracket4 | 261 | 2 | 263 |
| archidekt brackets 1/2/5 | 28 / 117 / 46 | 0 | unchanged |

**Cross-source overlap:** the 4 new Archidekt decks are the same
physical decks as 4 of the 15 new EDHREC files (their `source_url`s
point at exactly these Archidekt IDs) — the known pattern of the corpus
(EDHREC ingests Archidekt), not double-harvesting: both source copies
belong in the corpus, deduplication is the store's fingerprint step.

## 3. Loader acceptance (fresh stores, production loader)

`scripts/import_chulane_corpus.py` on an empty store, before (corpus
without the 19 files) and after:

| count | before | after | delta |
|---|---|---|---|
| `corpus_deck` | 3,004 | 3,023 | **+19** |
| canonical (`duplicate_of IS NULL`) | 2,845 | 2,861 | +16 |
| duplicates marked | 159 | 162 | +3 |
| `corpus_deck_card` | 266,539 | 268,204 | +1,665 |
| `corpus_cohort` | 11,297 | 11,369 | +72 |

The before-run reproduces the corpus README's acceptance figures
exactly. The +3 duplicates are three of the four cross-source pairs:
their Archidekt copies are marked `duplicate_of` their EDHREC twins.
The fourth pair is not fingerprint-identical for a naming reason only
(next section) and counts as two canonical decks.

Oracle mapping (`scripts/map_corpus_oracle_ids.py` on a store carrying
the Scryfall catalog): 268,031 of 268,204 card rows carry an `oracle_id`
(99.94 %, the same rate as the first capture; the 173-row residue is the
unchanged token-name class). The 1,665 card rows of the 19 new decks are
mapped **1,665 of 1,665 (100 %)**.

## 4. Findings

- **Front-face naming (the one non-duplicate pair):** EDHREC's preview
  names adventure cards by their front face ("Beanstalk Giant",
  "Rosethorn Acolyte"); Archidekt stores the full name ("Beanstalk
  Giant // Fertile Footsteps"). The physical deck is identical, the
  exact fingerprint differs, so both copies stay canonical. The oracle
  mapping resolves both forms (both decks are in the 100 % above). No
  action taken — changing either source's naming would falsify its
  provenance; noted for any future fingerprint normalisation.
- **Index window:** 9 corpus decks have now rolled out of EDHREC's
  two-year index window (step 0: 5). They remain in the corpus, as the
  corpus is the superset by design.
- **One Archidekt bracket-4 deck vanished from the search** (deleted or
  made private at the source, presumably). Its corpus file stays.
- No bracket reclassification anywhere: EDHREC 0 of 2,276 returning
  stubs, Archidekt no folder moves.

## 5. Files

19 new corpus files under `data/research/chulane_corpus/` (listed in the
table above); corpus README and the loader's acceptance note updated to
the new counts. No code changes.
