# WS221 RED Gate Reproduction (S4, pre-repair, DIRECTLY_VERIFIED)

Command: pytest tests/qualification/test_ws17_qualification.py::test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts -q
Result on audit-base HEAD 1a6ffcda: 1 failed (0.27s).

Failure: WS17_SHA256SUMS records 5dd9fc5a… for
qualification/ws207-xmage-qualified-scenario-setup/tests/test_ws207_seed_binding.py;
current bytes hash to 12e07d08…. First failing boundary is the byte comparison
in _verify_sha256_manifest (test line 176). No other assertion was reached, but
a full-manifest audit additionally found 766 post-manifest seal files
(ws213/ws215 namespaces) uncovered by both manifests.
