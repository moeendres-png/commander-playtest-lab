# WS223 Validation Record

Branch `ws223/ci-cardinality-environment-lock-20260915` @ `3e6d170f`
(plus staged follow-ups below). All commands run from the worktree root
unless noted. Classifications per project evidence semantics.

## Unit / guard validation (DIRECTLY_VERIFIED)

| Suite | Result |
|---|---|
| `tests/unit/test_ws223_cardinality_regression.py` (32 tests) | 32 PASS |
| `tests/unit/test_ws223_environment_identity.py` (11 tests) | 11 PASS |
| `test_xmage_variable_player.py` + `test_xmage_full_game.py` + `test_semantic_replay_tape.py` + `test_xmage_full_game_decision_matrix.py` (impacted guards) | all PASS (112 combined with WS223 batteries) |
| `tests/unit` full directory, clean tree, locked venv (CPython 3.14) | **871 PASS, 0 FAIL** |
| `tests/qualification` | 14 PASS, 1 FAIL = base-red F-CI-02 integrity gate (proven red at HEAD; WS223 adds no new failure mode — see below) |
| `test_ws_a1d_docker_pin_authority.py` (impacted by digest pin) | PASS after domain-split narrowing (engine-pin prohibition preserved) |
| `test_ws17r_exact_main_runtime.py` (impacted by locked install) | PASS after install-pattern update (ordering property preserved) |

## Lint / types (DIRECTLY_VERIFIED)

| Check | Result |
|---|---|
| `ruff check` on all 8 new/edited Python files | PASS |
| `ruff format --check` on same | PASS (6 reformatted by tool, re-tested green) |
| `mypy src/commander_lab` (locked mypy 1.20.2) | 9 errors, ALL in untouched `semantic_replay/*` (pre-existing WS218-stack condition; advisory in CI — no `pipefail` on that step); **0 in `full_game.py`** |
| `ruff check .` repo-wide | 10 errors, ALL in untouched `qualification/ws218-*/ws218_driver.py` (pre-existing) |
| All 16 workflow YAMLs | `yaml.safe_load` PASS |

## Live production validation (DIRECTLY_VERIFIED, local-equivalent)

Locked venv A + JDK17-built bridge + engine 1.4.61 @ `db134b97`:

- 2P bounded smoke (25): PASS — 5 classes incl. mulligan+priority.
- 3P bounded smoke (25): PASS — 4 classes incl. mulligan+priority.
- 5P bounded smoke (45): PASS — 4 classes incl. mulligan+priority.
- 5P @ 25: correctly FAILS required-class gate (missing priority) —
  live negative sensitivity; calibrates the 45 target.
- 4P full gate (default path): PASS — game over, 3105 decisions, winner
  seat 2, semantic replay match, hidden boundary PASS.
- 6P probe: FAIL_CLOSED, `engine_launched=false`, no JVM.
- Lane JSONs sealed as `CARDINALITY_*.json` companions; run products
  removed from `artifacts/` (tracked state restored).

## Lock validation (DIRECTLY_VERIFIED)

- `verify_dependency_lock.py` offline: PASS (115 compiler + 2 appendix pins,
  26 inputs, digest `200159e3…`).
- `--with-network`: PASS (requires-python ≥3.12 floor for all 117;
  3.12 linux/win32 closure complete; appendix matches index).
- Regeneration: re-running the recorded `pip-compile` command yields
  **identical 115 compiler pins**.
- Clean resolution A (default cache) vs B (`--no-cache-dir`): **identical
  114-package identity sets**, digest
  `b6ec216c…` == `b6ec216c…`; zero unpinned; applicable lock coverage exact.
- Offline: `--no-index` fails explicitly (`No matching distribution`);
  markers skip win32 entries without substitution.
- Editable project install after locked install works fully offline
  (`--no-deps --no-build-isolation`, pinned setuptools).

## Base-red conditions (CODE_DERIVED, explicitly not WS223 regressions)

1. `test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts` (F-CI-02
   RED gate): root manifest lists 0 ws213/ws218 files while those tracked
   files exist → `root_entries == expected` is False at HEAD independent of
   WS223 (manifests byte-identical to HEAD). WS223's workflow edit changes
   which assertion fires first, not the verdict. Refresh belongs to the
   F-CI-02 successor/integration (plus WS221 manifest-integrity ownership);
   WS223 leaves manifests untouched and records the required additions.
2. `ruff check .` / `mypy` findings in `ws218` files: pre-existing on the
   WS218 stack line; untouched by WS223.

## Not run (explicit)

- FULL107 = NOT_RUN (no impact finding requires it).
- Remote CI lanes (post-merge; local-equivalent evidence above stands in).
- Longitudinal availability recheck = FUTURE_ADVISORY (coordinator ruling).
- First-CI-run 3.12 locked-install proof: pending remote execution (metadata
  + closure gates are the local proof; install command verified on 3.14).
