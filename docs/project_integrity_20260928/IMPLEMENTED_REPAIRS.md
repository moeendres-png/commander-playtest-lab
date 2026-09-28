# Implemented repairs

Five sealed legacy deltas were still absent: production helper bytes on audit-main
matched each donor parent. Transplanted only the relevant helper, tests and usage
contract; no stale campaign state or provider evidence was imported.

| Helper | Repaired behavior |
| --- | --- |
| evidence.py | Stable artifact identity, missing-root rejection, duplicate handling, atomic index output and self-exclusion. |
| context_capsule.py | Bounded Git collection and sanitized failure diagnostics. |
| cluster_failures.py | Strict identifiers/JSON, deterministic groups, atomic output and input-alias protection. |
| session_stats.py | Reject malformed/nonfinite/negative/boolean numeric data; preserve output on failure. |
| test_impact.py | Verified refs, NUL-safe paths, explicit staged/dirty/untracked inventory, fail-closed Git errors. |

Exact donor commits, trees and content hashes are in LEGACY_PORT_RECEIPTS.json.
119 focused donor tests pass. Against isolated exact audit-main helper code, 102
fail and 17 pass (BASELINE_REGRESSION_RECEIPT.json). These are current reproduced
defects rather than inherited donor PASS claims.

Additional repairs: exact remote identity in drift_check.py, operational policy
prose, external-content boundary, fresh triage index and semantic policy guards.
No launcher, provider, Rules, qualification implementation or runtime evidence
was modified. Combined donor snapshots are compared by blob in
COMBINED_DONOR_COMPARISON.json; differences are retained as provenance, not blindly
merged. Replay-specific legacy delta is deferred to the completion owner.

Review follow-up: standalone drift checking now reuses source-lock's effective
URL rewrite guard, not just literal remote parsing. All three scope fixtures
(local/global/environment) failed before this follow-up. Downstream implementer
and full-execution authority instructions now defer to root Git boundaries; a
regression guard prevents the identified positive rebase/deletion grants returning.
