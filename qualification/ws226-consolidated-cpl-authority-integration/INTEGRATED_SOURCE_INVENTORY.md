# WS226 INTEGRATED_SOURCE_INVENTORY — combined tree contents

Base files: 12024 (`48885e8e` tree `d02d6c0…`). Added blob-exact (verified
`git status` + per-file `git show` sha equality):

- `research/project-audit/ws220/*`: 24 files (provenance).
- WS221 living (11): `evidence_vocab_v1.py`, `evidence/evidence_legacy_map_v1.json`,
  2 schema updates, `harness.py`, 3 docs, `robustness.py`, 2 tests (1 new + 1 updated).
- `qualification/ws221-foundation-integrity-source-truth/*`: 23 files.
- `qualification/ws222-g01-authority-reacquisition/*`: 71 files + `test_ws222_authority.py`.
- `qualification/manifests/AUTHORITY_LOCK_v2.json`: 1 (exact copy, current).
- `engine-bridge/.../XmageFullGameNameCanaryTest.java`: 1 + `qualification/ws224-*`: 34
  (33 + driver) + `test_ws224_name_canary.py`.
- `qualification/reporting/ws225/*`: 37 + `aggregate/WS225_ROLLUP_STATUS.json`
  + `test_ws225_standing.py`.
- `qualification/ws226-consolidated-cpl-authority-integration/*`: this namespace
  (SOURCE_LOCK×2, LINEAGE_GRAPH×2, PATH_OWNERSHIP, OVERLAP, INTEGRATION_PLAN,
  EVIDENCE_RETENTION_IMPACT, AUTHORITY_V2/HIDDEN_INFO/CI_ENV/REPLAY_INTEGRATION,
  + standing/manifest/validation/handoff outputs below).

Preserved base: `full_game.py` (WS223 smoke), `semantic_replay/`, locks,
workflows, docker, `ws218` + `ws223` namespaces, all prior tests.

Modified living (8, WS221-wins, base had no competing change):
`docs/OPERATIONAL_SIMULATION_POLICY.md`, 2 architecture docs, 2 evidence schemas,
`harness.py`, `robustness.py`, `test_operational_4p_policy.py`.

Unmodified living: `full_game.py`, manifests (until terminal repair),
`GATE_RESULTS.json`, `COMMON_FIXTURE_MANIFEST_v1.json` (v1 refs intentionally kept).

Machine companion: `INTEGRATED_SOURCE_INVENTORY.json` (counts + sha spot-checks).
