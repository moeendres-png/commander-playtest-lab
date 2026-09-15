# WS226 F_CI_02_VALIDATION — manifest integrity GREEN proof (terminal)

- `pytest tests/qualification/test_ws17_qualification.py::test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts` → PASS (terminal, 1/1).
- Full `tests/qualification/test_ws17_qualification.py` → 12/12 PASS.
- `tests/qualification/test_ws221_evidence_vocab.py::test_manifest_covers_post_ws17_seal_files` → PASS
  (post-repair; pre-repair FAIL reproduced as expected RED).
- `tests/qualification/test_ws221_evidence_vocab.py::test_manifest_mismatch_is_rejected` → PASS.
- Byte hashes: every `WS17_SHA256SUMS` (10639 entries) / `qualification/SHA256SUMS` (10634 entries)
  line matches current file bytes (verified by the test itself).
- Coverage: `root_entries == {pyproject, prod-qual workflow, test_ws17_qualification} ∪ qualification/**`
  and `q_entries == qualification/** − {SHA256SUMS}` exactly.
- Negative control (DIRECTLY_VERIFIED): single-byte tamper of
  `qualification/ws226-consolidated-cpl-authority-integration/SOURCE_LOCK.json` → F-CI-02 FAIL
  (sha mismatch, gate bites); restore → PASS.
- Same-commit invariant maintained (repair commit includes both manifests +
  the final tree they cover). F-CI-02 GREEN terminal.
