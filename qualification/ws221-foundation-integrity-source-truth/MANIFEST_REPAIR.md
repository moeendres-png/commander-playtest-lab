# WS221 Manifest Repair (S4)

Refresh-only repair, same-commit convention as prior reseals (e.g. e6eb7306):

- Updated the single stale digest line in each manifest to the current bytes of
  qualification/ws207-xmage-qualified-scenario-setup/tests/test_ws207_seed_binding.py.
- Appended the 766 uncovered post-manifest seal files (ws213/ws215 namespaces
  plus WS221 additions) with their current SHA256 digests.
- Refreshed the WS17 manifest's self-referential qualification/SHA256SUMS line
  after the inner manifest changed.
- No historical source artifact was altered to make hashes match; no file was
  removed from coverage; hash comparison is untouched.

Standing invariant (mechanical rule, enforced by
test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts itself): a
committed edit to a seal-covered artifact must refresh its applicable hash
manifest in the same commit. The RED→GREEN history of this workstream is the
standing proof that the gate bites.
