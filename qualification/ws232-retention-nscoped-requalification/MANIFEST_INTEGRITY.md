# WS232 MANIFEST_INTEGRITY (GREEN)

## Invariant

Same-commit qualification-manifest invariant (WS221 S4): a committed edit
to a seal-covered artifact refreshes its hash manifest in the same commit.

## Assessment

WS232 adds `qualification/ws232-retention-nscoped-requalification/**`
(1506 files: evidence, matrices, runs, tapes, tooling) plus one test file
outside the seal (`tests/qualification/test_ws232_retention_predicates.py`,
not manifest-covered by construction).

- `qualification/SHA256SUMS`: 1506 entries appended (mechanical refresh).
- `WS17_SHA256SUMS`: 1506 entries appended + inner-manifest digest line
  refreshed (mechanical, same commit).
- `__pycache__` strays purged from both manifests and disk.
- No historical sealed file altered (WS215/WS218/WS229 namespaces,
  contracts, standing inputs untouched — verified via `git status` scope
  review at commit time).

## Proof (DIRECTLY_VERIFIED, terminal tree)

- `tests/qualification/test_ws17_qualification.py`: 12/12 PASS
  (`test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts`
  verifies every digest and exact coverage).
- Standing/authority/vocab suites PASS (see VALIDATION.md).

MANIFEST_INTEGRITY = GREEN.
