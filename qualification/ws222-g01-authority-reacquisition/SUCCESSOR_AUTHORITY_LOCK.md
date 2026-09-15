# WS222 SUCCESSOR_AUTHORITY_LOCK (AUTHORITY_LOCK_v2)

Versioned successor to `qualification/manifests/AUTHORITY_LOCK_v1.json`
(which is NOT mutated; it remains historical). Machine authority:
`AUTHORITY_LOCK_v2.json` (schema `authority-lock/2.0.0`, offline-verified
`PASS` via `tooling/verify_authority.py`).

- Supersedes: AUTHORITY_LOCK_v1. Capture date: 2026-09-15.
- CR: official TXT `MagicCompRules_20260819.txt`, 977822 bytes,
  SHA-256 `4381ad1b…27423f`, effective 2026-08-07, normalization NONE,
  repeat-proven, provenance in `artifacts/cr/CR_ACQUISITION_RECEIPT.json`.
- Oracle: Model B bounded official Gatherer capture, 30 pages (29 front +
  1 MDFC back) for the 29-card denominator; field snapshot
  `artifacts/oracle/ORACLE_FIELD_SNAPSHOT.json`; receipt
  `artifacts/oracle/ORACLE_ACQUISITION_RECEIPT.json`; all Commander-Legal;
  111 rulings; bridge discovery-only; secondary never promoted.
- Rulings: captured with Oracle, subordinate to CR/Oracle (see
  RULINGS_AUTHORITY_ANALYSIS.md).
- Commander/B&R: official list + 2026-02-09 announcement (effective
  2026-02-09); 42 named bans; zero hits in frozen 29 / RogShai 87 /
  Kaervek 77 (`artifacts/ban/` + receipts).
- Deck provenance: carried forward unchanged (no identities invented).
- Freshness: CR 2026-08-07, B&R 2026-02-09, capture 2026-09-15; stale blocks
  admission. Refresh procedure + known limitations documented in the lock JSON
  (`refresh_procedure`, `known_limitations`).
- Tooling: `tooling/{acquire_cr,acquire_oracle,build_oracle_snapshot,capture_ban,verify_authority}.py`
  (allowlisted hosts, no credentials, atomic writes, fail-closed sanity,
  idempotent verify, offline verification).

Fixture-manifest migration (`authority_refs: AUTHORITY_LOCK_v1 → v2`) is NOT
performed by WS222 (manifest surface owned by the S2 rollup/integration
track); the Coordinator gate doc records it as the exact next integration step.
