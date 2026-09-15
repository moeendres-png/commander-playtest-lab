# WS226 AUTHORITY_V2_INTEGRATION — G01 scoped PASS on the combined tree

## Living location (convention: `qualification/manifests/`)

- Historical: `qualification/manifests/AUTHORITY_LOCK_v1.json` (frozen;
  CR `AUTHORITY_IDENTIFIED_BYTES_UNAVAILABLE`, Oracle `UNKNOWN`; never mutated).
- Current: `qualification/manifests/AUTHORITY_LOCK_v2.json` (NEW, EXACT byte
  copy of `qualification/ws222-g01-authority-reacquisition/AUTHORITY_LOCK_v2.json`;
  schema `authority-lock/2.0.0`, `lock_id AUTHORITY_LOCK_v2`,
  `supersedes AUTHORITY_LOCK_v1`). Verification is namespace-relative so the
  copy verifies identically:
  `python3 qualification/ws222-g01-authority-reacquisition/tooling/verify_authority.py
  --ns qualification/ws222-g01-authority-reacquisition
  --lock qualification/manifests/AUTHORITY_LOCK_v2.json` → `PASS`.

## Scoped authority (Coordinator adjudication: G01 PASS ONLY for this scope)

- CR: official TXT `MagicCompRules_20260819.txt` 977822 B,
  sha256 `4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f`,
  effective 2026-08-07, normalization NONE, repeat-proven.
- Oracle: Model B deterministic bounded official Gatherer capture — 30 pages
  (29 front + 1 MDFC back) for the frozen 29-card denominator
  (`ORACLE_FIELD_SNAPSHOT.json` 30 records, sha `0a9ed9cc…`; 111 rulings
  subordinate; bridge discovery-only; secondary never promoted).
- Commander/B&R: official list 221325 B + 2026-02-09 announcement 200718 B,
  42 named bans, 0 hits in frozen29 / RogShai87 / Kaervek77.
- Deck legality: carried forward unchanged (no identities invented).
- Freshness: CR 2026-08-07, B&R 2026-02-09, capture 2026-09-15; stale blocks
  admission (refresh procedure in lock JSON).

Do NOT generalize the bounded Oracle to all Magic cards or arbitrary future
decks. Whole-corpus pin requires extension procedure or Coordinator decision
(Models B/C/D per COORDINATOR_GATE; WS226 claims none).

## What was (not) migrated

- `COMMON_FIXTURE_MANIFEST_v1.json`: NOT rewritten (135 `authority_refs`
  stay `AUTHORITY_LOCK_v1`; WS222 deferred fixture migration to the S2
  rollup track; standing G01 is direct-gate, not fixture-joined, so no
  fixture rewrite is required for the scoped PASS).
- `GATE_RESULTS.json`: historical `G01 FAIL` row PRESERVED as provenance
  (never mutated). Living G01 PASS is recomputed in WS226 standing views
  from the exact v2 trace (lock + receipts + offline verify PASS + Deck
  legality). No silent promotion: WS225 `G01_STATUS.json` (FAIL at WS225
  lock) frozen; WS226 `G01_STATUS_WS226.json` (PASS scoped) is the current view.
- `REQUALIFICATION_REQUIRED`: stays empty (WS222 impact adjudication lists
  zero required reruns; integration changes no material semantics).
- Fixture behavior evidence: unchanged (BEHAVIOR_CREDIT 0).

## Evidence

- `tooling/verify_authority.py` offline → PASS (CR sha + 30 oracle pins).
- `tests/qualification/test_ws222_authority.py` 5/5 PASS (offline).
- WS222 VALIDATION.md live-acquisition receipts (DIRECTLY_VERIFIED at WS222
  lock; bytes pinned, fields deterministic).
