# Validation — FINAL-PROVIDER-CDQ-20260927 (continuation seal)

## Scope of validation

Reuse-first throughout: no already-valid suite rerun for reassurance. Lab
tree changes are evidence/tree additions under
`docs/final_provider_adjudication_20260927/` plus packet-test updates; no
`src/`, bridge, engine, config, or workflow code modified — touched-code
lint/type surfaces are N/A beyond executing the generator and tests green.
The one engine execution (Forge R20 denominator class) is new decision-
critical evidence, run read-only with zero mutation.

## Gate-D execution (actually executed)

- Command (worktree `/home/moeen/code/ws-forge-full107-cdq-20260926`,
  HEAD `18bba95a…`, clean before and after):
  `mvn -pl forge-protocol2-bridge -am -Dcheckstyle.skip=true
  -Dsurefire.failIfNoSpecifiedTests=false test
  -Dtest=WsR20Full107DenominatorTest`
- Result: **Tests run: 31, Failures: 0, Errors: 0, Skipped: 0** (~408 s),
  **BUILD SUCCESS all modules** (finished 2026-09-27T13:56:26+02:00).
- Scope note: denominator class only (the 31 decision-critical obligations);
  the 213 existing + full-bridge suites were already green at this tip
  (WSR20 seal) and were not rerun. No Forge file modified (worktree clean,
  HEAD unchanged — verified post-run).
- An initial attempt without `-Dsurefire.failIfNoSpecifiedTests=false`
  failed fast on empty-match modules (harness flag issue, not an engine
  failure); corrected flag, clean green run above. No code touched.

## Exact Lab commands (repo root, branch `wsr21/final-provider-cdq-20260927`)

1. `python3 docs/final_provider_adjudication_20260927/generate_packets.py`
   → exit 0; refresh 15/0/13/0/0/54/25 = 107; Forge mapping 84/17/3/3/0 = 107
   (verified from ingested bytes); comparison 14/62/25/0 = 101; 15 targeted
   gaps; 0 divergences / 0 pending; 38 readiness dimensions.
2. `pytest tests/unit/test_final_provider_cdq_packets.py
   tests/unit/test_full107_direct_correspondence.py -q` → **20 passed**
   (10 packet reconciliation + 10 pre-existing correspondence guard intact;
   no mapping/register/generator file touched).
3. `gh run view {36310680744,36310680885,36310680895,36310680966,36310680812}
   --json conclusion,status,name,headSha` → all `success`/`completed` on exact
   HEAD `58e8fca4` (launch gate PASS; reverified in continuation).
4. `git rev-parse HEAD` → local tip (see STATE.json); `git status` clean;
   remote WSR21 branch verified at `58e8fca4` (expected ancestor).
5. `git show` verifications: FULL107 `5a2e4f46…`, XMage runtime `59332671…`,
   Mage candidate `b1959698…` (reference), Forge candidate `ef958ee…` + tree
   `fc3387bf…` (reference), WSR20 tip `18bba95a…` (reference HEAD, clean).

## Deliberately not rerun

- Lab full Python suite, mypy, Java XMage bridge, Conformance, Smoke, H4,
  Production Qualification: already qualified on the reconciled authority /
  exact main; evidence-only tree additions cannot change engine behavior.
  Sealed run IDs cited, not reclaimed.
- Forge existing 213 + full-bridge suites: green at this tip per WSR20 seal;
  rerun would violate reuse-first.
- XMage engine tests: credited rows qualified (Gate B); missing rows lack a
  Lab seam or exact test → recorded GAP/NON_COMPARABLE, never simulated.

## Checks performed on the final tree

- JSON validity: all 5 packets + ingest files parse strictly.
- Count reconciliation: 107 refresh; Forge mapping 107 over exact denominator
  ids; 101 = 107 − 6 verified seams; 14/62/25/0 comparison; 15 gaps
  (ranks 0–14, rank 0 COMPLETE); 38 readiness dimensions; divergence_count ==
  len(divergences) == 0 with empty pending list.
- Cross-file consistency: normalization XMage statuses == refresh; GAP rows
  == XMage BLOCKED set (25); SAME rows == both-exact (13 DIRECT + TAX-4 TC);
  excluded seams == Forge UNKNOWN/BLOCKED with blocking assessments;
  DIRECT refresh rows all hold EXACT verdicts.
- Forbidden content scan: no provider-ranking tokens in any packet or MD
  (enforced by test across 12 files).
- Diff review: additions only (evidence dir + ingest + tests); no weakened
  tests/denominators/assertions; no engine/pin/config edits; no hidden
  fallback behavior; Forge reference untouched.

## Result

VALIDATION = PASS (bounded to the evidence-tree scope + the executed Gate-D
run above). Remaining UNKNOWN/BLOCKED cells are recorded with seams and
bounded follow-ups, never upgraded.
