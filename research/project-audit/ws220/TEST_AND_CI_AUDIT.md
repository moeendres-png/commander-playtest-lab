# WS220 Test & CI Audit

Question: are we testing the right things, reliably?

## Verdict: RIGHT SHAPE, THIN WHERE IT MATTERS, LANE-DEPENDENT

Test strategy (F-TEST-01, P2): guard-heavy by design (19/32 sampled GUARD),
which is correct for a fail-closed program. True rules behavior lives in the
JVM lanes + fresh-JVM matrices, not in pytest unit — consistent with
CODE_DERIVED != RUNTIME_VERIFIED. Gaps: live-engine rejection negatives for
3/17 classes (+concede); no per-forbidden-shortcut regression map (generic
legal-only gates only); card-overfit pilot fixtures; `test_impact.py`
advisory-only with zero CI consumers while `ci.yml` runs full `pytest -q`.

CI/environment (F-CI-01 P2, F-CI-02/F-CI-03 P1):
- Env is version-recorded, not locked: ranges + 6-pin lock + floating JDK
  tag + JDK17/21 skew + 12/16 lanes without PYTHONHASHSEED + cache keys
  ignoring runtime.lock. The 5-6+40 environmentals are traced to
  missing-extra/uninstalled/CLI-drift classes — harmless to scoped claims,
  proof the full suite is lane-dependent.
- RED integrity gate on WS215 line (F-CI-02): refresh manifests at merge.
- 4P-only conformance post-WS215 (F-CI-03): parametrize 2–5P + triggers.

Bottom line: day-to-day correctness feedback is honest but incomplete. The
highest-value test work is per-class live negatives (S6) + cardinality CI
(S5) + env lock (S15) — in that order. Do NOT chase full-suite green across
lanes before locking the env; lane-dependence makes that green meaningless.
