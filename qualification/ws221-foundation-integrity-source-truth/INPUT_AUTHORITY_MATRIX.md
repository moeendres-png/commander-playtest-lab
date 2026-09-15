# WS221 Input Authority Matrix

Consumed WS220 artifacts (direct workstream input, provenance only — fresh
verification below is the authority):

| Input | Used for | Fresh verification |
|---|---|---|
| FINDINGS.json F-EVID-03 / F-CI-02 / F-SRC-01 | owned findings | re-inspected schemas, harness, manifests, policy, code |
| SUCCESSOR_PROPOSALS.json S1 / S4 / S11 | owned objectives | implemented; S1 repair structure redesigned, not assumed |
| SOURCE_TRUTH_MAP.json | stale-surface pointers | every living hit reinspected before edit |
| EVIDENCE_MODEL_AUDIT.md | joint-leak ranking | harness coercion reproduced in test |
| TEST_AND_CI_AUDIT.md | test strategy | impact-selected validation, no JVM rerun |
| VALIDATION.md | RED reproduction reference | RED reproduced pre-repair on HEAD |
| probes/stale_source_scan.py (P-SRC-01) | stale-source probe | rerun pre- and post-fix; result sealed |

Other WS220 findings are NOT absorbed. S5 (2–5P CI expansion) and WS218
replay surfaces are untouched (ownership boundary).
