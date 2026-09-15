# WS221 Integrity Validation (S4, post-repair)

- pytest tests/qualification/test_ws17_qualification.py (full file, 12 tests):
  all PASS, including test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts.
- Exact current file bytes match recorded hashes (both manifests verify).
- No required changed artifact is uncovered (manifest entry sets equal the
  test's expected coverage sets exactly).
- tests/qualification/test_ws221_evidence_vocab.py::test_manifest_covers_post_ws17_seal_files
  PASS; ::test_manifest_mismatch_is_rejected PASS.
