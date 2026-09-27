# Validation — FINAL-PROVIDER-CDQ-20260927

## Scope of validation

Smallest sufficient validation per change (reuse-first; no already-valid
expensive suite rerun for reassurance). No `src/`, bridge, engine, or config
code was modified — all changes are evidence/tree additions under
`docs/final_provider_adjudication_20260927/` plus one unit test — so
lint/type surfaces for touched code are N/A (no Python source besides the
deterministic generator and the test itself, both executed green).

## Exact commands (all from repo root, branch `wsr21/final-provider-cdq-20260927`)

1. `python3 docs/final_provider_adjudication_20260927/generate_packets.py`
   → 5 packets written; refresh 15/0/13/0/0/54/25 = 107; comparison 0/101/0/0;
   15 targeted gaps; 0 divergences; 38 readiness dimensions. Exit 0.
2. `pytest tests/unit/test_final_provider_cdq_packets.py -q`
   → 8 passed (reconciliation, EXACT-verdict guard, 101-common, refresh
   parity, gap ordering, divergence honesty, readiness completeness,
   no-ranking-language).
3. `pytest tests/unit/test_full107_direct_correspondence.py -q`
   → 10 passed (impacted existing guard: DIRECT↔EXACT correspondence intact;
   no mapping/register/generator file touched).
4. `gh run view {36310680744,36310680885,36310680895,36310680966,36310680812}
   --json conclusion,status,name,headSha`
   → all `success` / `completed` on exact HEAD `58e8fca4` (launch gate PASS).
5. `git rev-parse HEAD` → `58e8fca4…`; `git rev-parse HEAD^{tree}` →
   `4cf4f3d2…`; `git status` clean at session open (SOURCE_LOCK.md).
6. `git show --no-patch` for `5a2e4f46…` (FULL107 freeze) and `59332671…`
   (reconciled runtime authority) → both resolve locally.

## Deliberately not rerun

- Full Python suite (1548 tests), mypy, Java bridge (298 tests), Conformance,
  Smoke, H4, Production Qualification: already qualified on the reconciled
  authority / exact main; rerunning would violate reuse-first with no
  semantic delta in scope (evidence-only tree additions cannot change engine
  behavior). Their sealed run IDs are cited, not reclaimed.
- Engine runtime (XMage/Forge): Gate D records zero new engine executions
  with reason (credited rows qualified; missing + Forge rows need WSR20
  ingest + builds outside declared reference scope).

## Checks performed on the final tree

- JSON validity: all 5 packets parse (generator + tests load them strictly).
- Count reconciliation: 107 refresh rows; 101 = 107 − 6 seams; 15 gaps
  (ranks 0–14); 38 readiness dimensions; divergence_count == len(divergences).
- Cross-file consistency: normalization XMage statuses == refresh statuses;
  excluded seams == contract §14 list; DIRECT rows all hold EXACT verdicts.
- Forbidden content scan: no provider-ranking tokens in any packet or the
  readiness summary (enforced by test).
- Diff review: additions only (new evidence directory + one test); no
  weakening of tests, denominators, assertions, or expected semantics; no
  engine/pin/config edits; no hidden fallback behavior.

## Result

VALIDATION = PASS (bounded to the evidence-tree scope above). Missing
evidence (Forge WSR20 side, exact-rerun gaps) is recorded UNKNOWN/absent,
never upgraded.
