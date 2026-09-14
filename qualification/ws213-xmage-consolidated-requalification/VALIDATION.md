# WS213 VALIDATION

- Bridge (`mvn -B -ntp verify`, engine-bridge): **105/105 PASS**
  (88 WS204-preserved + 17 WS213-additive), 0 failures/errors/skips.
- Python WS213 scope (88/88 PASS):
  `test_ws_a1r_pin_authority`, `test_ws_a1d_docker_pin_authority`,
  `test_xmage_full_game`, `test_xmage_compatibility_provider`,
  `test_ws_arclose_d1_authority_drift`, WS207 `test_ws207_seed_binding`
  (revised guard), WS213 `test_ws213_driver` (7).
- Ruff: PASS (`engine-bridge`, drivers, touched tests).
- Broader `tests/unit` + `tests/foundry`: 880 passed, 1 skipped; 6 failed
  + 40 collection errors, ALL pre-existing environmental, none WS213-caused:
  missing `openpyxl`/`fastapi` modules (opponent-repo/primer/whole-deck
  chains), `commander_lab` not pip-installed (hash-seed subprocess test),
  `opencode` binary 1.18.31 vs qualified 1.18.30 (WS75 gate). No failure
  references pins, manifest, bridge, or drivers.
- Matrix: 12 constructions × behavior+twin(500), 7 setup+twin(500),
  12 opening twins, 3 seed controls, E02 ladder (6×500+3×3000+2×6000+2 twins).
  Twin equality 19/19 decision-level; hidden-info 8709 rows/0 violations;
  binding explicit+supported in every run.
- `FULL107 = NOT_RUN` (remaining burden: full 107-scenario behavior matrix
  gated on per-slot qualified setups + credited pilots; successor burden
  after variable-player session + replay contract).
- `RAW_GIT_PUSH_USED = NO` (canonical safe_push only; dry-run first).

Machine companion: `VALIDATION.json`.
