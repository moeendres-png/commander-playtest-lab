# WS222 G01_ADJUDICATION — `G01_STATUS = PASS (SCOPED, SEALED)`

Adjudicated against the 12 WS222 hard gates. Each gate cites sealed evidence;
missing evidence would stay UNKNOWN (none missing).

1. Exact current official CR bytes captured — PASS (`artifacts/cr/...txt`,
   receipt; §CR_OFFICIAL_SOURCE).
2. Raw SHA-256 recorded — PASS `4381ad1b…27423f` (normalization NONE).
3. Official source provenance reproducible — PASS (landing + resolved URLs,
   timestamps, headers, ETag/Last-Modified, allowlisted tooling, verify mode).
4. Effective date established — PASS ("...August 7, 2026", from bytes).
5. Oracle authority satisfies the canonical required scope — PASS (Model B:
   30 official pages cover all 29 card-bearing fixtures + deck-legality ban
   checks; scope proof in ORACLE_SCOPE_ANALYSIS.md; bulk correctly deferred).
6. Oracle/card identities unambiguous for the required domain — PASS
   (denominator → face → printing → function; split + MDFC models proven).
7. Secondary data not silently promoted — PASS (bridge discovery-only;
   correspondence tests separated; subset stays non-authoritative).
8. Rulings authority status explicit — PASS (captured, subordinate hierarchy).
9. Authority lock versioned and machine-validated — PASS (v2 supersedes v1,
   v1 untouched, offline verifier PASS).
10. Refresh/update semantics documented — PASS (lock `refresh_procedure`).
11. Existing behavior evidence impact adjudicated — PASS (IMPACT_ADJUDICATION:
    credit 0, requalification list empty, G13 separation stated).
12. No waiver by silence — PASS (no waiver used; Model D documented as
    Coordinator-only and NOT invoked; WAIVER_GRANTED = NO).

## Status

- `G01_STATUS = PASS` — scoped to the canonical required domain stated above;
  sealed by this package (evidence classes recorded per artifact).
- `G13_IMPACT` — G01 blocker cleared; G13 remains FAIL on independent
  behavior/provider grounds. No aggregate file is rewritten by WS222;
  rollup migration is a Coordinator/S2 integration step (see COORDINATOR_GATE).
- `REQUALIFICATION_REQUIRED = []` (empty list, not null: affirmatively none).

Machine companion: `G01_ADJUDICATION.json`.
