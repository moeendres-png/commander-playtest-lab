# Deferred Successor Notes — Sealed-Manifest Blocked (WSR25, 2026-09-27)

Two additive pin-lineage notes were drafted, verified correct, then REVERTED before
publication because `tests/qualification/test_ws17_qualification.py::
test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts` requires
`qualification/SHA256SUMS` hashes to match every file under `qualification/`.
Updating that sealed manifest is outside WSR25 authority (sealed-evidence rewrite).

Proposed notes (Coordinator / manifest owner applies together with manifest update):

1. `qualification/ws88-xmage-integrated-successor-promotion/FINAL_REPORT.md` append:
   "## WSR25 Successor Note (2026-09-27, additive only) — Historical-at-time truth
   above (`NEW_XMAGE_RUNTIME_CANDIDATE = cfc36f44`) is preserved. Current authority
   (`config/rules_engines.json`) is XMage `b1959698…` via lineage `cfc36f44` →
   `db134b97` (WS213) → `b1959698` (PR #242). Retained as promotion evidence."
2. `qualification/ws90-rqc3-corrected-first-wave-reissue/FINAL_REPORT.md` append:
   analogous note for historical `cfc36f44` references; zero behavior credit unchanged.

Landed instead: `docs/RETENTION_AND_LIFECYCLE_POLICY.md` WSR25 addendum (docs/ is not
hash-gated; infrastructure gate confirms only the ws88 path failed).
