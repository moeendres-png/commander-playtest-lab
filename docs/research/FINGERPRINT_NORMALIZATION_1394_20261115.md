# Fingerprint normalization #1394 — one physical deck, one fingerprint

Issue #1394 (Owner go 2026-11-15). Measured 2026-11-15 on two stores built fresh
from this repository (`import-all --from-repo`, Scryfall oracle bulk as the card
catalog), before and after the change, on identical input data. Basis: main
`84a35cef8` (includes the #1388 corpus refresh merge, PR #1395). Evidence classes
per AGENTS.md §4: the mechanics are `CODE_DERIVED` from the lines cited, every
count is `DIRECTLY_VERIFIED` on the fresh builds.

## 1. Step 0 — the mechanics, as the code defines them

**Formation.** `decklist_import._fingerprint` (now a delegation to
`catalog.corpus_content_fingerprint`) hashes the sorted (card name, section,
quantity) rows of a deck **over the source spellings of the card names**, at
import time, and stores the result in `corpus_deck.fingerprint`. EDHREC lists a
two-part card under its front face, Archidekt under the full `Front // Back`
name — so one physical deck imported from both sources carried two fingerprints.

**The duplicate mark.** `corpus_deck.duplicate_of` is informational only (the
importer's module docstring): it is derived from the fingerprint at import and
repaired by `_release_stale_marks` when a re-import changes a target. No count
reads it.

**Consumption.** `universe.resolve_universe` collapses the decks of a selected
universe by the **stored** fingerprint at query time (lowest deck id wins);
`universe_choice.local_spec` is the unfiltered commander universe the tier
signals count over (`corpus_signals.count_corpus`), and universe snapshot ids
hash the stored fingerprints. The #1387 fill counted over the same collapse.

**Other writers.** The register and hub importers (`importers.py`) take the
fingerprint from their input files (`fingerprint_scryfall_oracle`,
`content_fingerprint_sha256`). Those are separate legacy datasets, not part of
the repository build; this change leaves them alone (section 2, candidacy).

**Name resolution.** `catalog.name_resolver` maps a full name or a front face to
exactly one oracle id, or leaves the name out entirely — a front face shared by
several cards stays unresolved. `relink_corpus` and
`repo_import.map_corpus_oracle_ids` fill `corpus_deck_card.oracle_id` from it:
268,031 of 268,204 rows (99.94%) on the fresh build; the residue is 173 rows
under 74 names with no unambiguous catalog match (token names and the like).

## 2. The chosen variant — oracle keys, re-derived at link time

Variant (b): the fingerprint is re-derived over **oracle keys** once a deck's
names are linked, in the new `catalog.refresh_corpus_fingerprints`, which runs
inside `relink_corpus` and at the end of `map_corpus_oracle_ids`. A linked row
keys on `oid:<oracle_id>`; an unlinked row keeps its source name as
`name:<card name>`; rows are merged per (key, section) before hashing, exactly
like the importer's row merge.

Why not variant (a), normalizing the names at import time: the deck list import
must stay independent of import order (deck lists may precede the catalog — the
link step exists for that), and a name-only canonicalization is not fail-closed:
truncating to the front face would merge two decks whose differing cards merely
share a front-face spelling with another card's full name. Variant (b) reuses
the resolver that already refuses exactly those names.

Fail-closed, concretely: an undecided name can only keep two spellings of one
deck apart (its rows key on the raw name), it can never merge two decks.
Measured on the real corpus: **none** of the 222 collapsed groups involves an
unresolved row — every collapse is carried by fully linked rows.

Candidacy is provenance, not fingerprint history: a deck is re-derived when
every one of its card rows carries the deck list importer's `source_name`
normalization status (only that importer writes it). The step is a pure function
of the stored rows, so a later link (a catalog update resolving one more name)
simply re-derives again; register and hub decks keep their file fingerprints.
`duplicate_of` of the re-derived decks is re-derived with them, lowest deck id
canonical — the same tie-break `_release_stale_marks` and `resolve_universe`
already use.

One visible side effect on an intermediate counter: `import_decklists` reports
`duplicates_marked` for marks made during its write loop (8 on the full corpus
build, 162 before). A cross-folder duplicate whose first copy was already
re-derived is now marked by the link step at the end of the same import instead.
The store end state (section 3) is the authoritative count either way.

An existing store migrates by re-running any link step (the CLI `relink`
command, any deck list or catalog import): no corpus data file changes, and this
change touches no corpus data — only the two acceptance figures in the corpus
README and the loader docstring, which pinned the old canonical count.

## 3. Measured effect — canonical decks, before → after

| figure | before | after |
|---|---|---|
| `corpus_deck` rows | 3,023 | 3,023 |
| distinct fingerprints | 2,861 | **2,639** |
| decks marked `duplicate_of` | 162 | 384 |
| canonical decks (mark is NULL) | 2,861 | **2,639** |
| tier universe, `local_deck_count` | 2,839 | **2,617** |

222 groups collapse, every one a pair (one EDHREC copy, one Archidekt copy of
the same physical deck); all 222 pairs sat inside the tier universe. (The 2,823
universe figure quoted in the #1387 report was the pre-refresh store; on the
refresh stand the before value is 2,839.)

Cohort denominators of `corpus_signals.count_corpus` (the counted tier signals):

| cohort group | before | after |
|---|---|---|
| tuned (brackets 4+5) | 1,160 | 1,066 |
| low (bracket 2) | 648 | 608 |
| tournament (bracket 5) | 267 | 256 |

Distinct decks inside each single bracket cohort (a deck can sit in two bracket
cohorts through its two source copies, so these do not add up to the group
denominators): bracket 1: 68 → 61; bracket 2: 654 → 614; bracket 3: 978 → 898;
bracket 4: 901 → 819; bracket 5: 267 → 256.

## 4. Counted signals — what actually moves (pool of 927, production functions)

- **`corpus_tuned`**: 344 of 927 values change; the largest shift is 0.011 —
  Prairie Stream 299/1,160 → 263/1,066 (−0.011), Crop Rotation 353/1,160 →
  336/1,066 (+0.011), Silence (+0.010), Avacyn's Pilgrim (+0.009).
- **`corpus_log_lift`**: all 564 values that exist change; the largest shift is
  0.034 (Loyal Sentry, 6 → 4 hits of 2,839 → 2,617 decks). The movers are
  small-count cards throughout.
- **`corpus_bracket_slope`**: 290 values change in place, largest 0.034
  (Blue Sun's Zenith +0.034; Maze's End −0.034). **16 cards lose the value
  entirely** — after the dedupe they fall under the five-hit rule the slope
  requires, and an absent value is the honest state (missing, never 0):
  Briarhorn, Brigid's Command, Bristlebane Battler, Cat Collector, Darksteel
  Colossus, Disperse, Eclipsed Kithkin, Environmental Scientist, Hada
  Freeblade, Kinscaer Sentry, Steward of Valeron, Thoughtweft Lieutenant,
  Venom Connoisseur, Vine Trellis, Whirlwind Denial, Winds of Rath.

No counted signal moves by more than ~0.034 on its 0..1 scale: the correction
is broad but shallow — the expected shape of removing a 7.8% double count.

## 5. Effect on the #1387 fill (named only)

The committed fill (`data/research/corpus_fill_20261115`) was counted over the
pre-normalization universe (2,823 decks on the pre-refresh stand). Its
denominators and counted zeros stand as published until #1388 step 5
regenerates it over the enlarged, normalized corpus; this change does not
rewrite it.

## 6. Gates

Run on this worktree (basis above), worktree `src` on PYTHONPATH, project
toolchain environment:

- New module `tests/unit/test_studio_fingerprint_normalization.py`: **4 passed**
  with the change; the two collapse tests **fail on the pre-change code**
  (verified against the stashed basis), the two guard tests (no false merge,
  ambiguous name) pass on both, as designed.
- Guard cluster for the changed files (`test_studio_decklist_universe`,
  `test_studio_import_all_corpus_link`, `test_studio_import_from_repo`,
  `test_studio_counted_universe`, `test_studio_multipart_corpus_import`,
  `test_studio_data_report`, `test_studio_memo`, `test_studio_store`,
  `test_card_name_collisions`, `test_import_oracle_cards`,
  `test_public_catalog_refresh`, plus the new module): **219 passed**.
- `test_test_hygiene` + `test_any_usage_ratchet`: passed (no new `Any`).
  `test_audit_committed_research_data`: passed.
- `ruff check` + `ruff format --check` on all changed Python files: clean.
  `mypy` on the three changed source files: clean.
  `scripts/classify_docs.py --check`: OK (0 problems).
