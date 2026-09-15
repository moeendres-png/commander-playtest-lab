# WS221 Manifest Root Cause (S4, CODE_DERIVED from git history)

- Stale manifests: WS17_SHA256SUMS and qualification/SHA256SUMS last refreshed
  at 17ddab61 (pre-WS213).
- Commit 344deca4 (WS213, legitimate successor revision) revised the guard test
  qualification/ws207-xmage-qualified-scenario-setup/tests/test_ws207_seed_binding.py
  (RandomUtil-only assertion superseded by native Rules-seed binding assertion;
  documented in-commit; WS207 sealed evidence untouched) without refreshing the
  manifests in the same commit.
- Commits through WS215 added 766 seal files (ws213/ws215 namespaces) likewise
  without manifest refresh.
- The test was not weakened and no file was excluded: the RED is a true
  tamper-evidence signal for a provenance lapse, not a false positive.
