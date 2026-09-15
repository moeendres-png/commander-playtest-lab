# WS221 Validation (impact-selected; no JVM/runtime rerun, no behavior change)

- tests/qualification/test_ws17_qualification.py (12 tests): PASS post-repair
  (RED reproduced pre-repair: 11 pass / 1 fail).
- tests/qualification/test_ws221_evidence_vocab.py (14 tests): PASS — vocab
  discipline, harness rejection ×5, admission blocking, legacy mapping,
  schema accept/reject, manifest coverage + mismatch negative.
- tests/unit/test_operational_4p_policy.py (7 tests): PASS (updated contract).
- P-SRC-01 probe rerun post-fix: living single-pod-size contradictions cleared
  (remaining hits adjudicated intentional/provenance/S5-owned).
- tests/qualification/test_ws17r_exact_main_runtime.py (3 tests): PASS.
- tests/unit/test_phase1215_robustness.py (7 tests): PASS (robustness.py message change).
- tests/unit/test_whole_deck_balanced_campaign.py: NOT_RUN — collection requires
  missing optional dependency openpyxl (pre-existing environment limitation,
  untouched by WS221).
  (remaining hits adjudicated intentional/provenance/S5-owned).
- ruff + schema validity covered by the ws17 suite (test_schemas_are_valid…).
- Not run (decision value negative, no behavior touched): full pytest suite,
  Maven/XMage builds, JVM matrices, FULL107 (retired), conformance workflow.
