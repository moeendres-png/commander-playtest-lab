# Corpus mass harvest #1388 — the bracket-less EDHREC decks as the `edhrec/unclassified` cohort

Issue #1388 (mass harvest by Owner decision, 2026-11-15). Measured and built
2026-11-15 on basis main `86868bc17` (merge of PR #1390; the parallel
classified-refresh PR had not landed, so the base corpus here is the 3,004
decks of the first harvest). Stores for the acceptance counts were built
fresh from this worktree via the production route (`import-all --from-repo`,
Scryfall oracle bulk as the card catalog). Semantics below are `CODE_DERIVED`
from the lines cited; every count is `DIRECTLY_VERIFIED` on the fresh builds
or on the committed files.

## 1. Step A — the semantics, before any harvest

**Target set.** The EDHREC deck index
(`json.edhrec.com/pages/decks/chulane-teller-of-tales.json`, fetched fresh on
2026-11-15) held **9,819 stubs** (step 0, hours earlier: 9,816 — the rolling
two-year window moves). Target = stubs with `bracket = null` whose `urlhash`
is not already a corpus file: **7,528 decks** (step 0: 7,523).

**Loader.** The corpus loader does **not** discover folders:
`repo_import.CORPUS_FOLDERS` (`src/commander_lab/studio/repo_import.py`, line
42) is a fixed tuple, consumed by `import_corpus` (line 106), which imports
each listed folder through `decklist_import.import_decklists`. A new cohort
therefore needed the tuple entry `("edhrec/unclassified", "edhrec")` — placed
after the five classified variants, so a classified copy of the same physical
deck stays the canonical one under the importer's first-copy-wins fingerprint
rule.

**Cohort derivation.** A deck's `corpus_cohort` rows are built in
`decklist_import._edhrec_deck` (line 129) from the file's own fields:
`source:edhrec`, `bracket:<n>`, `variant:<variante>`, `commander:chulane`.
The old code required a bracket integer (`_bracket` raises on a missing or
null field). The minimal change: an **explicit null** bracket now yields no
`bracket:<n>` cohort and no bracket tag (never a substitute bracket number),
while a file without the bracket field at all stays rejected as broken — the
contract the existing test `test_import_rejects_broken_deck_files_with_the_file_name`
pins. Two tests carry the change (bracket-less import; `import_corpus`
reading the new folder). Archidekt files still require their bracket.

**Universe.** The tier universe is `universe_choice.local_spec`
(`universe_choice.py`, line 148): `filtered_spec(store, [], commander_names=[commander])`
— a commander scope with **no cohort filter**. A deck bound to Chulane (via
its commander section) enters it, bracket or not. The bracket-bound signals
of the strength index count `corpus_cohort` cohorts instead
(`corpus_signals.py`: `TUNED_COHORTS = ("bracket:4", "bracket:5")`, line 35;
`LOW_COHORTS = ("bracket:2",)`, line 36; `count_corpus`, line 126) — cohorts
the new decks never join. Expectation, verified in section 3: the total
universe grows, every bracket denominator stays identical.

## 2. Step B — the harvest

Route per deck: `GET edhrec.com/api/deckpreview/<urlhash>` (browser
user-agent), paced at **1.5 s between request starts** (the project's
documented EDHREC pacing), soft-429 answers (HTML under HTTP 200) and
5xx/429 retried with exponential cooldown. Raw answers stay outside the
repository (`~/workspace/tmp/1388/mass/raw/`, 7,528 files); progress was
checkpointed per deck in `state.json`.

The run history is part of the evidence: the first run was cut by a runtime
restart (SIGTERM) after **4,118 decks**; the checkpoint resume continued with
the remaining 3,410 and lost nothing — the state file, the raw answers and
the normalized files agree exactly.

| outcome | count |
|---|---|
| target decks | 7,528 |
| fetched and normalized | **7,528** |
| fetch failures (404 / HTTP / network / soft-429 after retries) | 0 |
| normalization failures | 0 |
| parse status `ok` (100 cards) | 7,483 |
| parse status `error`, note `summe_101_statt_100` | 45 |

Normalization mirrors the first harvest's proven reconstruction (verified
field-exact against a corpus file in step 0): commanders first
(`commander_v2`), then the container cardlists in order, quantities from
`deck.cards`; every deck's reconstructed card multiset is checked against
the preview's own counts and a mismatch would have been recorded, never
guessed — none occurred. `variante`/`bracket`/`savedate`/`price`/`salt`/
`tags` come from the index stub (the join the first harvest used);
`source_url` is the preview's source URL plus the harvest's UTM suffix.
No author fields anywhere. The 45 decks at 101 cards are the companion
pattern the first harvest already carries (15 decks, same note). No deck
needed a merged duplicate cardview, a source-URL fallback, or showed a
savedate mismatch between index and preview.

## 3. Step C — integration and acceptance (fresh stores, before / after)

| measure | before | after | delta |
|---|---|---|---|
| `corpus_deck` | 3,004 | 10,532 | +7,528 |
| canonical (`duplicate_of IS NULL`) | 2,845 | 10,363 | +7,518 |
| exact duplicates | 159 | 169 | +10 |
| `corpus_deck_card` | 266,539 | 911,398 | +644,859 |
| card rows with `oracle_id` | 266,366 (99.94 %) | 911,225 (99.98 %) | — |
| `corpus_cohort` rows | 11,297 | 33,881 | +22,584 (= 7,528 × 3) |
| tier universe (`local_spec`) | 2,823 | **10,341** | +7,518 |
| `variant:unclassified` universe | — | 7,526 | — |

The new cohort's own card rows map to oracle ids at **100 %** (644,859 of
644,859; EDHREC names are catalog-clean — the remaining store-wide residue
sits in the old Archidekt names).

**Deduplication, reconciled exactly.** Of the 7,528 new decks, 5 are marked
`duplicate_of`: 3 point at classified EDHREC decks (2 × optimized, 1 × cedh),
2 at other unclassified decks (hence the cohort's own universe counts
7,528 − 2 = 7,526). The other +5 duplicates are Archidekt decks whose only
twin is an unclassified EDHREC copy: they were canonical before only because
that copy was missing, and are now marked as duplicates of it (EDHREC folders
import before Archidekt folders). Net counted growth of the tier universe:
7,523 canonical new decks − 5 re-marked Archidekt decks = **+7,518**.

Step 0 had estimated ~5 % duplicates (~7,100–7,500 unique of 7,523) from the
first harvest's EDHREC↔Archidekt overlap rate. Measured: **10 collisions,
0.13 %** — the unclassified population is largely disjoint from the
bracket-harvested corpus; the estimate's premise (same overlap structure as
the classified routes) did not hold. The measured figure replaces it.

**What does not change.** Every bracket cohort keeps its exact deck count
(bracket 1–5 cohort rows: 73 / 674 / 1,022 / 956 / 279) and every bracket
universe its exact size (**66 / 647 / 959 / 891 / 267** — the denominators of
the tier signals `corpus_tuned`, `corpus_bracket_slope` and the bracket-5
part of `tournament`). The classified variant universes are likewise
identical (233 / 557 / 45 / 695 / 755). What changes is only the whole-corpus
denominator: the tier universe (and with it the base of `corpus_log_lift`
and of the #1387 counted fill, on its next regeneration) now stands on
10,341 decks instead of 2,823.

## 4. Gates

Run on this worktree (basis `86868bc17` plus the loader commit), with the
worktree `src` on PYTHONPATH, the project toolchain environment and
`TMPDIR` on the workspace disk:

- `tests/unit/test_studio_decklist_universe.py` (incl. the two new tests),
  `tests/unit/test_audit_committed_research_data.py`,
  `tests/unit/test_studio_import_all_corpus_link.py`,
  `tests/unit/test_studio_multipart_corpus_import.py`,
  `tests/unit/test_studio_commander_binding.py`, `tests/unit/test_studio_memo.py`,
  `tests/unit/test_test_hygiene.py`, `tests/unit/test_any_usage_ratchet.py`:
  **91 passed** (no new `Any`; the loader change adds none).
- `ruff check` and `ruff format --check` on the four changed Python files:
  clean. `scripts/classify_docs.py --check`: OK (0 problems).
- Guard search (every test/script naming the changed paths): the files above
  are the complete hit list for `chulane_corpus` / `CORPUS_FOLDERS` /
  `import_corpus` / `decklist_import` under `tests/`.

## 5. Files

- Loader: `src/commander_lab/studio/repo_import.py`,
  `src/commander_lab/studio/decklist_import.py`,
  `scripts/import_chulane_corpus.py` (folder list + acceptance figures),
  tests in `tests/unit/test_studio_decklist_universe.py`.
- Data: `data/research/chulane_corpus/edhrec/unclassified/` (7,528 files),
  corpus `README.md` acceptance updated.
- Harvest tooling (checkpointed, resumable) and raw answers remain local
  under `~/workspace/tmp/1388/mass/`, like the first harvest's tooling.

## 6. Nachtrag — Merge-Stand (nach #1394 + Refresh)

The figures in §§2–3 above were measured on the harvest base `86868bc17`,
before the corpus refresh (PR #1395, +19 lists) and the fingerprint
normalization (#1394, PR #1397) reached this branch. After merging
`origin/main` (`0db690369`) into the branch, a fresh store built from the
merged tree measures instead:

- `corpus_deck` 10,551; canonical 10,150; duplicates 401;
  `corpus_deck_card` 913,063, of which 912,890 carry an `oracle_id`
  (99.98%; the new cohort alone: 644,859 of 644,859 = 100%);
  `corpus_cohort` 33,953.
- Tier universe (`local_deck_count`) 10,128; the `variant:unclassified`
  universe holds 7,526 decks. The bracket-derived figures are unchanged:
  tuned 1,066, low 608, B5 256; the bracket 1/3/4 universes are
  59 / 889 / 814.

In particular, the duplicate count involving this cohort is **17 new
markings, not the base-relative 10** of §3: 16 unclassified decks are
marked duplicate (13 of them point at Archidekt decks) and 1 classified
EDHREC deck loses its canonical status to an unclassified copy. The
import log also shows 10, but that is a different quantity: it counts
collisions of the source-name fingerprints at import time, while the
final `duplicate_of` marks are re-derived over oracle ids at link time
(#1394, lowest deck id canonical). Every fingerprint group still counts
exactly once in every universe, and no bracket cohort or bracket
universe changed size.
