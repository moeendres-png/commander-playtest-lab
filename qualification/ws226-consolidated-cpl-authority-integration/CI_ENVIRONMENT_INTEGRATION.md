# WS226 CI_ENVIRONMENT_INTEGRATION — WS223 protections survive

Preserved byte-exact from the WS223 base (`48885e8e`); no integration repair
needed (no sibling touches these paths — verified empty overlap).

- Cardinality CI: `CARDINALITY_2P/3P/4P_REPLAY_GATE/5P.json` + `CARDINALITY_6P_FAIL_CLOSED.json`
  + `CARDINALITY_CI_CONTRACT.md` + `CARDINALITY_LIVE_SMOKE.md` +
  `test_ws223_cardinality_regression.py` (648 lines; 2–5P bounded smoke +
  6P fail-closed) + `scripts/run_external_full_game_conformance.py` smoke lane
  (`run_smoke`/`_drive`/`_open_game` shared verbatim with `run`).
- Environment lock: `DEPENDENCY_LOCK_CONTRACT.md` + `DEPENDENCY_LOCK_DIGEST` +
  `requirements/lock.in` + `requirements/lock.txt` (2289 lines) +
  `LOCK_PROVENANCE.json` + `scripts/{verify_dependency_lock,write_environment_receipt,generate_lock_appendix}.py`
  + `ENVIRONMENT_RECEIPT_CONTRACT.md` + `ENVIRONMENT_IDENTITY_INVENTORY` +
  `JDK_CONTRACT.md` + `CONTAINER_IDENTITY.md` (digests) + `CACHE_IDENTITY_CONTRACT.md`
  + `PYTHONHASHSEED_POLICY.md` + `CLEAN_RESOLUTION_*.freeze.txt` + comparison.
- CI: 15 workflows (`.github/workflows/*`) + `CI_IMPACT_MAP` + `CI_TRIGGER_MATRIX`
  + `test_ws223_environment_identity.py` + `test_ws_a1d_docker_pin_authority.py`.

F-CI-02 was RED on WS223 (manifests missed WS221 repair + later namespaces).
WS226 owns GREEN on the FINAL COMBINED TREE (terminal manifest repair; same-commit
invariant). No Rules/pilot semantic change authorized or performed.
