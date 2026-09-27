# Impact Matrix (standing — append per change)

## Change 1 (Phase 1, worktree HEAD — restoration v2 + repository-readiness fix)

Touched: `XmageNativeStateRestoration.java` (hand zone end-to-end,
dimensions 1.1.0, `ensureRepositoryReady` in `materializeCards`),
`XmageNativeStateRestorationTest.java` (hand positive/transition/honeycard/
library-negative; hand-rejection negative retired by design).

- Semantically affected → requalified: `XmageNativeStateRestorationTest`
  (17/17 green, current bytes).
- Structurally affected → inspected + re-run: `XmageDigestCreditTest`,
  `XmageFullGame{Start2,Tax,Partner,Card02}ExecutionTest`,
  `XmageFullGameHiddenInformationTest` (all green; 1 pre-existing skip).
- Unaffected → retained: all other qualification evidence (no byte change on
  their paths; pin unchanged `1.4.61`/`db134b97`).
- Mapping impact: none yet — no FULL107 promotion in Phase 1 (promotions
  require Phase 2 exact runs). `TRIG-3/5` + 4 already-supported cells are
  execution candidates, not promotions.

## Changes 2–6 (Phases 2–6 — new test files only, no production bytes)

Added: `XmageFullGameElimExecutionTest`, `XmageFullGameTrigExecutionTest`,
`XmageFullGameDecisionExecutionTest`, `XmageFullGameMicroExecutionTest`,
`XmageFullGameCandidateDomainTest`, `XmageExternalRiskSignalTest`,
`semantic_replay/comparator.py`,
`tests/differential/test_first_divergence_comparator.py`.
Mapping: `FULL107_MAPPING.json` counts + 5 entries → DIRECT
(TRIG-3/5, MICRO_LAYERS, MICRO_TARGETS, PILOT_CHOOSE_MODE).

- Prior evidence: retained (additive tests; full bridge suite 217 run /
  0 fail / 0 error / 1 pre-existing skip on final bytes).
- Full-bridge requalification at Final Adjudication covers all producers.
- Python: differential + regressions + contract 40 passed / 1 pre-existing
  skip; `test_phase1212` collection blocked by missing `typer` in this
  environment (pre-existing, untouched surface).

## Change 7 (Phase 7 — audit only)

No bytes changed; all evidence retained by definition.
