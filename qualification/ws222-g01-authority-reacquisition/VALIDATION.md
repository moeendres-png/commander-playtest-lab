# WS222 VALIDATION

## Tooling runs (DIRECTLY_VERIFIED, live official network)

- `tooling/acquire_cr.py --out-dir artifacts/cr` → receipt + `VERIFY_PASS
  4381ad1b…27423f` (landing 150428 bytes + artifact 977822 bytes).
- Repeat TXT fetch (independent probe + tooling cycle): identical bytes twice
  (MATCH true). `--verify-only` → match true.
- `tooling/acquire_oracle.py` (29 names, delay 1.0) → 29 captures +
  `VERIFY_PASS`; `--ensure-back-faces` → +1 MDFC back page (`VERIFY_PASS`,
  30 records). One bridge fallback (Veyran → older printing pointer,
  deterministic) recorded in receipt.
- `tooling/build_oracle_snapshot.py` → `ORACLE_FIELD_SNAPSHOT.json`
  (30 records, sha `7686ca39…`, rebuilt after unescape fix).
- `tooling/capture_ban.py` → B&R list (221325 bytes) + 2026-02-09 Commander
  announcement (200718 bytes), 42 named bans, dates extracted.
- `tooling/verify_authority.py` (offline) → `PASS` (CR sha + 30 oracle pins).
- Repeatability probe (Ishai re-fetch): bytes differ (dynamic shell, proven),
  all 10 field groups SAME.
- Correspondence sample (8 identities, live Scryfall vs snapshot): 6 exact,
  2 rendering-delta-only (Wear join structure, Vandalblast `{4}{R}`/`{4R}`);
  no Oracle conflict; secondary NOT promoted.

## Tests

- New `tests/qualification/test_ws222_authority.py`: 5/5 PASS (offline).
- Full `tests/qualification/`: 19 pass + 1 pre-existing FAIL
  (`test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts` on
  `test_ws207_seed_binding.py` — F-CI-02 RED, identical before WS222's first
  edit; out of WS222 scope, untouched).
- `ruff check` on WS222 tooling + test: clean. `ruff format`: applied.

## Not run (by design, recorded)

- No 135-fixture behavior rerun (authority refresh grants no credit; impact
  adjudication lists zero required reruns).
- No full bulk Oracle capture (~30k pages; no canonical requirement).
- No broad repo test suite / Maven (no engine/pilot code touched).

Machine companion: `VALIDATION.json`.
