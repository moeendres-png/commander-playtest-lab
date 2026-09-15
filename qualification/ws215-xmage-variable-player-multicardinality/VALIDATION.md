# WS215 VALIDATION

- Engine-bridge (`mvn -B -ntp test -o`, offline): **121/121 PASS**
  (105 WS213-preserved + 16 WS215: rewritten player-count gates,
  lane contract, 12-test variable-player lifecycle incl. 3P/5P
  concession, CR800.4 cleanup/active/priority, 4P/5P multi-defender).
  0 failures/errors/skips.
- Python impacted scope: `test_xmage_variable_player` 32/32,
  `test_xmage_full_game` + `test_xmage_full_game_decision_matrix` +
  `test_xmage_compatibility_provider` (62 combined PASS with the new
  file); `test_candidate_lossless_handoff` updated to the variable
  contract (not runnable here: pre-existing missing `hypothesis`
  module — same environmental class as WS213; change is syntax-verified
  and logic-reviewed).
- Ruff check: PASS on all touched Python files (check gate; `format`
  not enforced — 2 files pre-existing format-dirty, untouched to avoid
  diff noise).
- Broader `tests/unit`: 640 passed; 5 failed + 40 collection errors,
  ALL pre-existing environmental (missing `openpyxl`/`fastapi`-class
  modules, uninstalled-package subprocess tests) — none references
  WS215 files; same adjudication as WS213 (which recorded 6 + 40).
  `tests/foundry` not required by impact (no references to the
  WS215 mutation surface).
- Fresh-process matrix (`ws215_driver.py`, one JVM per run):
  24/24 runs clean (no failure, gates empty) — per count neutral pair
  (150 decisions) + develop pair (600 decisions) + distinct-seed
  controls; all 8 same-seed twin pairs MATCH; all 8 distinct-seed
  controls DIVERGE. Sealed in `runs/WS215_MATRIX.json`.
- Observation/supplemental runs: oracle 9985 frames / 0 violations
  (5 errors confined to one superseded pre-fix debug run); zone/tax/
  mulligan/damage/command-zone/start-draw observations as cited in the
  per-family files.
- `RAW_GIT_PUSH_USED = NO` (canonical safe_push only; dry-run first).
- `FULL107 = NOT_RUN`. `GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0`.

Machine companion: `VALIDATION.json`.
