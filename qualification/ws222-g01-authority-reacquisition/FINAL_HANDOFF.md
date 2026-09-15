# WS222 FINAL_HANDOFF — G01 Official Rules & Oracle Authority Re-acquisition

## Source Lock

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws222/g01-authority-reacquisition-20260915`
- Audit base (terminal published WS220): `1a6ffcdaa264bb64dbc32c9b32019092fc4a896b`
  (tree `6bc707b37f8fb39950f4ade2db11e7ccef03dab6`); HEAD verified identical at
  start; worktree clean; no WS218/WS221 surfaces touched.
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Work Completed

1. **Reproduced F-QUAL-02 independently** (v1 lock: CR sha null/bytes unavailable;
   Oracle UNKNOWN; 135/135 fixtures cite the lock; G01=G13=FAIL; secondary
   subset explicitly non-authoritative and missing 17/29).
2. **Reconstructed the contract** (`AUTHORITY_REQUIREMENT_MATRIX`, 12 rows):
   G01 minimum = byte-exact CR + official Oracle for the card-bearing domain
   (frozen 29) + Commander/B&R + deck legality + carried provenance. Bulk
   Oracle correctly deferred (no canonical requirement).
3. **Acquired the current official CR**: landing page re-resolved (drift found:
   prompt-expected `...20260807.txt` now 404; current official TXT is
   `MagicCompRules 20260819.txt`, same effective date 2026-08-07); 977822 bytes,
   SHA-256 `4381ad1b…27423f`, repeat-proven identical, receipt + verifier.
4. **Investigated official Oracle infrastructure** (Gatherer 2.0 official,
   structured per-card records, no bulk artifact/API, sitemap economics, robots
   posture) and executed **Model B bounded capture**: 30 official pages
   (29 front + 1 MDFC back) for all 29 denominator identities, all
   Commander-Legal, 111 rulings, field snapshot, bridge discovery-only.
   Proven honest reproducibility semantics (bytes pinned; fields deterministic;
   byte drift ≠ authority change).
5. **Correspondence tests** (8-sample secondary vs official): match without
   promotion (6 exact, 2 rendering-delta-only, zero conflicts).
6. **Deck legality**: zero banned hits (frozen 29, RogShai 87, Kaervek 77)
   against the official Commander list (2026-02-09, effective 2026-02-09).
7. **Sealed successor lock** (`AUTHORITY_LOCK_v2.json`, supersedes v1, v1
   untouched, offline verifier PASS) + impact adjudication (credit 0,
   requalification []) + **G01 adjudication: PASS (scoped, sealed)**.
8. **Validation**: new offline test 5/5 PASS; qualification dir 19 pass +
   1 pre-existing F-CI-02 FAIL (untouched); ruff check clean, format applied.

## New Findings

- Official TXT republished 2026-08-19 with unchanged effective date; old URL 404s
  (drift recorded; current source truth wins).
- Gatherer 2.0 redirects preserve 1.x multiverseid identity; `//` names need
  bridge+redirect (old search falls back to homepage).
- MDFC back faces live at same set+number under back-face slug with 64-hex
  composite resourceIds; split cards carry combined Oracle text on one page.
- Gatherer shells are byte-dynamic but field-deterministic (proven).
- Veyran-class new printings may lack Scryfall Gatherer pointers → deterministic
  older-printing fallback (recorded).
- Oracle extraction hazards documented + fixed (UI-table over-match, U+2212
  mojibake via blanket unicode_escape).
- Sol Ring Oracle/printed templating delta (`{CC}` vs `{C}{C}`) shows why Oracle
  (not printed/engine text) is authority.

## Changes

- NEW `qualification/ws222-g01-authority-reacquisition/` only (docs, receipts,
  artifacts incl. CR bytes + 30 Gatherer pages + snapshot + B&R pages, 5 tools,
  v2 lock, adjudications, validation, handoff).
- NEW `tests/qualification/test_ws222_authority.py` (offline, 5 tests).
- No engine/pilot/manifest/aggregate/contract/history changes. No pushes yet
  (safe_push steps run terminally below).

## Tests / Evidence

- DIRECTLY_VERIFIED: live official acquisitions + hashes + repeatability +
  correspondence sample + deck-legality counts + tool verify modes.
- Offline machine: WS222 test 5/5 PASS; `tests/qualification/` 19 pass +
  1 pre-existing FAIL (F-CI-02, evidence of non-interference).
- NOT_RUN by design: 135-fixture reruns, bulk capture, broad suite/Maven.
- Classifications kept: no secondary promotion, no browser-text bytes, no waiver.

## PASS / FAIL / UNKNOWN

- `F-QUAL-02 REPRODUCED = PASS` (then repaired).
- `CR_AUTHORITY = PASS` (byte-exact, repeatable).
- `ORACLE_AUTHORITY = PASS` (bounded required scope, Model B).
- `G01_STATUS = PASS` (scoped, sealed; 12/12 hard gates).
- `G13 = FAIL` (independent behavior/provider grounds; G01 no longer blocker).
- `REQUALIFICATION_REQUIRED = []`. `BEHAVIOR_CREDIT_CHANGE = 0`.
- Pre-existing `F-CI-02 RED` = still FAIL (not WS222's surface).

## Remaining Blockers

None in-scope. Coordinator-owned follow-ups (non-blocking, see
COORDINATOR_GATE.md): bounded-scope acceptance for broader corpora (extend B /
Model C / Model D), rollup migration (GATE_RESULTS + authority_refs v1→v2 via
S2 track + hash-manifest refresh incl. pre-existing F-CI-02), POST_LOCK_DRIFT
if WS221 enums moved.

## Outputs

`qualification/ws222-g01-authority-reacquisition/`: SOURCE_LOCK(.md/.json),
INPUT_AUTHORITY_MATRIX(.md/.json), CURRENT_G01_REPRODUCTION(.md/.json),
AUTHORITY_REQUIREMENT_MATRIX(.md/.json), CR_OFFICIAL_SOURCE.md,
CR_REPEATABILITY.md, ORACLE_OFFICIAL_SOURCE_ANALYSIS.md,
ORACLE_IDENTITY_MODEL.md, ORACLE_SCOPE_ANALYSIS(.md/.json),
ORACLE_CORRESPONDENCE_TESTS(.md/.json), RULINGS_AUTHORITY_ANALYSIS.md,
AUTHORITY_LOCK_v2.json, SUCCESSOR_AUTHORITY_LOCK.md,
IMPACT_ADJUDICATION(.md/.json), G01_ADJUDICATION(.md/.json),
COORDINATOR_GATE.md, VALIDATION(.md/.json), FINAL_HANDOFF.md (this file),
`tooling/` (5 scripts + frozen29 names), `artifacts/{cr,oracle,ban}/`
(+ receipts, snapshot, pages). Plus `tests/qualification/test_ws222_authority.py`.

## Dependencies Unblocked

- G01 admission blocker cleared (scoped PASS sealed) → S2 rollup can migrate
  G01/authority_refs; candidate comparison has a grounded domain anchor.
- Behavior tracks (incl. WS218 replay inputs) can execute under the v2 pin.
- Future Oracle/CR/B&R refreshes have procedures + tooling (no re-research).

## Exact Next Action

In this same writer session, terminally: `git add` the two new paths →
commit (focused message) → `safe_push --dry-run` → actual `safe_push` →
`git fetch origin` → verify remote HEAD == local HEAD, remote TREE ==
local TREE, clean worktree → emit terminal fields and terminate. No raw push,
no PR, no merge, no main mutation. Rollup migration itself is Coordinator/S2
work, not this session's.

## Terminal fields

WS222_G01_AUTHORITY_REACQUISITION: COMPLETE (semantic; COMPLETE_WITH_EXTERNAL_AUTHORITY_GATE not needed — no gate blocks G01; gate doc is informational)
CR_AUTHORITY: BYTE_EXACT_CAPTURED
CR_SOURCE: https://media.wizards.com/2026/downloads/MagicCompRules%2020260819.txt via https://magic.wizards.com/en/rules
CR_EFFECTIVE_DATE: 2026-08-07
CR_SHA256: 4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f
CR_BYTE_EXACT: YES
CR_REPEATABLE: YES
ORACLE_AUTHORITY: BOUNDED_OFFICIAL_CAPTURE (Model B, required scope)
ORACLE_SOURCE_MODEL: B (Gatherer 2.0 per-card official; Scryfall discovery-pointer-only)
ORACLE_SCOPE: frozen 29 denominator, 30 pages (29 front + 1 MDFC back), all Commander-Legal, 111 rulings
ORACLE_REPRODUCIBILITY: BYTES_PINNED_FIELDS_DETERMINISTIC (byte drift alone is not authority change)
SECONDARY_SOURCE_ROLE: discovery / cross-check / correspondence ONLY; never authority
RULINGS_AUTHORITY: CAPTURED_WITH_ORACLE_SUBORDINATE (CR > Oracle > rulings > bulletins-provenance)
SUCCESSOR_AUTHORITY_LOCK: AUTHORITY_LOCK_v2 (supersedes v1; v1 untouched; offline-verified PASS)
G01_STATUS: PASS (scoped, sealed)
G13_IMPACT: G01 blocker cleared; G13 still FAIL on independent behavior/provider grounds
REQUALIFICATION_REQUIRED: []
AUTHORITY_GATE_REQUIRED: NO
WAIVER_GRANTED: NO
PRODUCTION_CODE_MODIFIED: NO
ENGINE_PIN_MODIFIED: NO
BEHAVIOR_CREDIT_CHANGE: 0
RAW_GIT_PUSH_USED: NO
ARCHITECTURE_FREEZE: NOT_CLAIMED
PRODUCTION_PROVIDER: NOT_SELECTED
