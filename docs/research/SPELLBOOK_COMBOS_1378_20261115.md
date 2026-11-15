# Spellbook combo base broadened via the variants API — issue #1378

Date: 2026-11-15. Code stand: `main` at `f842b296f`. Evidence class:
`DIRECTLY_VERIFIED` (every figure below is the output of the committed fetch
script or recomputed from the written file; the script's dry run and its
writing run were two independent full API pulls and produced identical
counts). Data change only: `data/meta/spellbook_combos.json` grows from 11
hand-curated entries to 16,571; no code path changes. The file stays metadata,
never rules knowledge — whether a line goes through in a game is decided by
the XMage engine alone.

Reproduction:

```bash
python scripts/spellbook_combos_fetch.py --data "<Studio-Datenordner>" \
    --retrieved-at 2026-11-15
```

The store must hold the repository data (`import-all --from-repo`), as for
`scripts/subarchetype_analysis.py`. The script is idempotent: entries it
generates carry the combo_id prefix `chulane-sb-` and are dropped and
regenerated on every run; hand-curated entries are preserved verbatim.

## 1. The file's semantics, verified before extending it

Schema (validated by `MetaComboLine` in `src/commander_lab/models/meta.py`):
each entry names `combo_id`, `commander`, `cards`, optional `any_of` groups,
`bands`, `tier`, `source`, `source_url`, `edhrec_decks`, `result`, `notes`;
the file adds a `provenance` block. Consumers: `sources.load_spellbook_combo_cards`
(evidence and coverage records; matches on the `commander` field),
`sources.load_spellbook_combo_partners` (universe view), and the meta lane's
model. The store-side combo machinery (`combos.py`, the `commander_combo`
table) reads a different list (EDHREC) and is untouched by this change.

The old file held **11 entries: 4 for Rograkh/Ishai and 7 for Chulane**
(2 of the Chulane entries name exactly 2 cards, both with an `any_of` group).
The working hypothesis for the Chulane selection — "every card of the combo
appears in the Chulane corpus/pool" — was tested against a store built from
this repository (canonical universe: 2,823 decks via `resolve_universe`;
9,266 corpus name keys over the counted sections):

* **Pool containment is refuted.** Only 3 of the 17 distinct names in the
  Chulane entries (Chulane itself, Shrieking Drake, Whitemane Lion) are rows
  of the store's 1,655-card table at all.
* **Strict corpus containment holds for 6 of 7.** The one deviation is
  `chulane-forager-turns`: Ethereal Forager appears in the stored corpus
  exactly once, in a *maybeboard* section (deck `archidekt:15666326`) —
  never in a counted section of a canonical deck. Under the loosest reading
  (any section, all 3,004 stored decks) all 7 entries are contained.
* All 7 entries carry color identity within WUG, and the file's one
  documented exclusion (a Dockside Extortionist line) breaks WUG *and* uses
  a banned card. The project's source register (`spellbook:variants-api` in
  `sources.py`) states the source's scope as "all known and rule-verified
  MTG combos matching Chulane color identity (Bant / WUG)", retrieved via
  "REST API GET (with commander filter)".

The extension therefore applies: identity within WUG (API query) + the
strict canonical-corpus rule locally. The preserved forager entry stays as
it is — curated evidence is not rewritten; its deviation is recorded here
and in the fetch script's summary output.

## 2. Query path (privacy rule section 12)

One public parameter only: `GET https://backend.commanderspellbook.com/variants/?q=identity<=WUG`,
paginated at the API's own page size (it caps `limit` at 100 and rewrites
larger values), following its `next` links: **316 pages, 31,544 variants**,
retrieved 2026-11-15. No deck list, pool, card list or any other project
data was sent to the service; every further filter ran locally. No 403/429
was hit; the script stops with the status as evidence if one ever occurs.

## 3. The local filter chain (counts of the writing run)

| stage | removed |
|---|---:|
| fetched variants (identity ≤ WUG per the query) | 31,544 fetched |
| identity letters outside WUG (local recheck; colorless `C` counts as inside) | 0 |
| status not `OK` | 100 |
| not legal in Commander (`legalities.commander`) | 503 |
| spoiler | 0 |
| a card required as a *different* commander (`mustBeCommander`) | 249 |
| a card outside the canonical corpus (2,823 decks, counted sections) | 14,123 |
| card set already present as a hand-curated entry | 4 |
| same card set as another kept variant (merged) | 5 |
| produces no feature (no result text) | 0 |
| **kept** | **16,560** |

Counter note for future re-runs: a review fix moved the seen-set marking to
the keep point, so a card set counts as seen only once a variant with that
set is actually kept — "produces no feature" now counts every produces-less
variant reaching that stage and "same card set as another kept variant
(merged)" counts only merges into a kept entry; the writing run above is
unaffected, because its produces-less count was 0.

Of the kept variants, 48 name Chulane itself as a card. Card-count
distribution of the kept entries: 1 card: 4 (the remaining pieces are
template requirements, not named cards), 2: 1,238, 3: 9,185, 4: 5,656,
5: 477. They name 2,263 distinct cards; 21 carry no EDHREC deck count
(`edhrec_decks: null`, as the schema allows).

One cross-check worth noting: the API variant of the curated
`chulane-ranger-symbiote` loop names Priest of Titania as a fourth card —
exactly the card the curated entry's note documents as an implicit
requirement "NOT encoded as cards". The generated entry
(`chulane-sb-1376-1909-2900-3314`) encodes it.

## 4. Result

| | before | after |
|---|---:|---:|
| entries, whole file | 11 | 16,571 |
| entries, Chulane section | 7 | 16,567 |
| two-card entries, Chulane section (`cards` field) | 2 | 1,240 |
| file size | 7,604 bytes | 11,293,231 bytes |
| distinct Chulane combo card names (`load_spellbook_combo_cards`) | 17 | 2,265 |
| pool cards (of 1,655) carrying a Spellbook combo flag | 3 | 147 |

The 11 preserved entries are byte-identical and in their original order
(verified against the pre-change file). The provenance block keeps the
2026-10-25 record untouched and adds the API source plus an
`extension_1378` block with the endpoint, query, scope text and the full
count table. Generated entries follow the old entries' conventions:
`bands: ["high_power"]` (as all 7 old Chulane entries), `tier: "A"`,
`source: "commanderspellbook"`, the variant's page as `source_url`, the
API `popularity` as the all-decks `edhrec_decks` count, and `result` as the
variant's produced feature names joined in API order. The API's
`bracketTag` is deliberately **not** used as band evidence — the old file
already records that the source's bracket tag is not band evidence.

## 5. Consumer verification

* All 16,571 entries validate against `MetaComboLine` (0 errors).
* `load_spellbook_combo_cards()` returns 2,265 names in 0.21 s;
  `load_spellbook_combo_partners()` maps 2,265 cards in 0.37 s — the
  11 MB file parses fast enough for both call sites.
* Guard tests for the changed file (`test_studio_sources.py`,
  `test_meta_spellbook_pr5.py`), the partner-loader consumer
  (`test_studio_decklist_universe.py`), `test_test_hygiene.py` and
  `test_any_usage_ratchet.py`: 66 passed, 1 skipped (a pre-existing skip:
  no local Studio DB on this machine). The whole `test_meta_*` family
  separately: 18 passed.

## 6. Limits and downstream notes

* The corpus filter is only as strong as the corpus: with 9,266 name keys
  it removes 45 % of the WUG catalog, but any WUG combo whose pieces each
  appear *somewhere* in 2,823 decks passes — containment is not synergy,
  and per the register, redundant variants are not independent strength
  claims (shell deduplication is issue #1366's layer, not this file's).
* Static artifacts computed from the old file predate this extension —
  notably the `has_spellbook_combos` flags in
  `data/research/chulane_legal_pool_gap_matrix.json` (2026-11-12). They are
  snapshots of their date and were not regenerated here.
* The file is now a single-line JSON of 11.3 MB; tooling that diffs or
  pushes it per file must be able to handle that size.
