# DR-CLOSURE-01 Final Handoff

## Source Lock

- Start: `HEAD 2231ff4bdd30753a127133e51a0d3657c668532d`,
  tree `f759ed34d35fdf76ebbb04814edf4a470f960e27` (== `origin/main`, clean).
- End: final branch HEAD/TREE stamped in `DEEP_RESEARCH_IMPLEMENTATION_LEDGER.json`
  (`source_lock` per finding) at re-lock commit; engine pins unchanged
  (`xmage 1.4.61` / `db134b9737e951367d65ef5806ad986319cc73ab`;
  Forge `a37a865a`; provider decision `NO_PROVIDER_READY`).
- External references: no foreign code copied anywhere (provenance ledger
  clean); Oracle wording (Esior/Hex) verified via Gatherer/Scryfall at
  campaign time; Manabrew method reimplemented independently.

## Work Completed (per phase)

0. Source lock + ownership (PR #239 merged → no foreign ownership) +
   duplicate census + ledger skeleton.
1. Blocked-fixture matrix (30 cells); reuse-first per dimension; hand-identity
   v2 with A–E proofs; incidental repository-readiness systemic fix.
   Stack/damage/temporal/control stay fail-closed with exact reasons.
2. TRIG-3 (3P) + TRIG-5 (5P) executed → DIRECT (real cast/resolve/triggers).
   ELIM life-0 proven unrestorable via setLife (engine resets to 40) →
   blocker characterization, stays blocked.
3. MICRO_LAYERS + MICRO_TARGETS + PILOT_CHOOSE_MODE executed → DIRECT.
   NEGATIVE_FIRST_OPTION direct negative evidence (no promotion — failure
   terminal superseded). Argentum 4 patterns verified present. UNKNOWN
   blocker correction (dimension-blocked vs unrunned).
4. Candidate-domain invariant across look/target/mode + Serum Visions
   actual-card regression + decoy adversarial. No second legality engine.
5. Provider-neutral `compare_tapes` (9 classes, context/source-lock/provider
   records); 13/13 tests incl. real WS218 4P 257-step pair. MATCH ≠ PASS.
6. `EXTERNAL_RISK_SIGNAL` pack 4/4 green (Esior subject+count, Unsummon
   wrong-object+destination, restore-derived, stale-rejection; D partial via
   commander-zone choice). Findings: exact-6-target (Hex) offer gap;
   harness over-tap fixed in-campaign.
7. Process-isolation audit → verified, zero changes.

## Disposition Ledger (terminal, all 13)

9× IMPLEMENTED_AND_RUNTIME_VERIFIED (STATE-01, CHOICE-02, DIFF-03,
PHASE-BUGS-05, PRED-RESTORE-01, PRED-PARSER-03, PRED-ZONE-04, PRED-HIDDEN-06,
PRED-AUTH-07); 2× ALREADY_IMPLEMENTED_VERIFIED (ARGENTUM-API-04,
PRED-CANCEL-02); 1× REJECTED_BY_RULES_AUTHORITY (FORGETS-ANTI-06);
1× BLOCKED_FAIL_CLOSED (PRED-REPL-05 general timing; partial evidence kept).
Machine-readable: `DEEP_RESEARCH_IMPLEMENTATION_LEDGER.json`.

## New Findings

- Life-0 elimination unrestorable via pre-start setLife (engine re-derives
  starting life) — needs genuine loss causation (executor scope).
- Setup-placed commander copies correctly lack commander status
  (`isCommanderObject=false`); only genuine command-zone-cast permanents
  count — engine correct, fixture design corrected in-campaign.
- Exact-6-target (Hex) offer gap in `getPlayable` (engine/bridge follow-up).
- Targets precede payment per CR 601.2 (harness order corrected).
- Mode actions share prompt text (label-exact matching required).
- Scry surfaces as bounded `target` decision (exactly 2 offered).
- Single-source payment must be cost-aware (over-tap harness defect fixed).

## Changes (exact)

Production: `XmageNativeStateRestoration.java` (hand zone, 1.1.0 dimensions,
`ensureRepositoryReady`). Tests: restoration suite (+hand/transition/
honeycard/library-negative), Elim/Trig/Decision/Micro/CandidateDomain/
ExternalRiskSignal suites, `semantic_replay/comparator.py`,
`tests/differential/test_first_divergence_comparator.py`. Docs: workstream
dir (lock/state/ledger/provenance/matrix/phase closeouts/handoff) +
`FULL107_MAPPING.json` (5 promotions).

## Tests / Evidence

- Final XMage bridge conformance at implementation head `28cecb44`: 223 tests run, 0 failures, 0 errors, 1 skip; Maven BUILD SUCCESS.
- Final repository CI at implementation head `28cecb44`: 1545 Python tests passed, 5 skipped; Ruff lint/format, mypy strict, compile, secret scan, wheel build and security job all succeeded.
- H4 Docker Materialization run 60: preflight PASS, h4-xmage PASS, h4-forge PASS.
- All eight PR workflows were green at implementation head `28cecb44325047bd2b7b4069cbcebba9064aacca`.
- All evidence DIRECTLY_VERIFIED on the validated implementation bytes unless labeled otherwise; UNKNOWN≠PASS, NOT_RUN≠PASS preserved.

## FULL107 Delta

`DIRECT 7→12` (+TRIG-3/5, +LAYERS, +TARGETS, +CHOOSE_MODE);
`NOT_RUN_BLOCKED 30→28`; `UNKNOWN 57→54`; `SUPPORTING 13`.
DIRECT by count: 2P:2, 3P:1, 4P:8, 5P:1.
Hidden 0/20 direct (slices covered); decision families: 10 supporting +
2 direct (CHOOSE_MODE new); replay tapes 0/5 direct (method ready);
isolation verified.

## PASS / FAIL / UNKNOWN

No false PASS created; unsupported dims fail closed with codes; 54 UNKNOWN +
28 blocked retained with exact reasons (no headline inflation).

## Remaining Blockers (technical only)

Stack reconstruction (11), commander damage (5, engine-side), temporal
progression (7, executor-side), control divergence (2, executor-side),
life-0 elimination (4, genuine-loss executor-side), library/facedown (HIDDEN
+ tapes), exact-6-target offer gap, general replacement timing.

## Outputs

PR #241 branch `dr-closure-01-deep-research-20260924` is pushed and review-remediated. Validated implementation head before final documentation reconciliation: `28cecb44325047bd2b7b4069cbcebba9064aacca`, tree `d675269ce58e8294bc72bc45c1c55b3006218977`. The final docs-only descendant and merge SHA are recorded by GitHub on PR #241.

## Dependencies Unblocked

TRIG/decision/micro execution patterns unblock remaining hand-restorable
UNKNOWNs (ANNOUNCE_X, MULTI_AMOUNT, COSTS-targets, MODES, TRIGGERS,
CONTINUOUS, SBA, NEGATIVE_* hand-only) for follow-up executor work.

## Follow-Up Dispatches (separate surfaces only)

1. Executor-driven stack reconstruction (Commander Lab; needs cast/resolve
   drivers for stack-bearing fixtures).
2. Engine-side commander-damage restore API (pinned `mage` repo).
3. Temporal progression driver (combat/postcombat/beginning arrivals).
4. Exact-N-target offer investigation (Hex gap; engine vs bridge).
5. Library/facedown restoration (HIDDEN per-fixture closure).
6. General replacement-effect timing fixtures.

## Exact Next Action

Merge PR #241 after the docs-only reconciliation checks remain green, then verify `main` HEAD/TREE and post-merge workflows. After merge, dispatch follow-ups 1–6 as independent non-overlapping workstreams according to dependency/ownership constraints. No authority gate is opened by this workstream: ARCHITECTURE_FREEZE NOT CLAIMED, PRODUCTION_PROVIDER NOT SELECTED.


## Post-Review Remediation

Five P1 review findings were fixed before merge and their review threads resolved:

- hand restoration now binds credit to exact injected native UUIDs, with a same-name Mountain adversarial regression;
- semantic replay tapes are validated against the supported Pydantic schema before comparison;
- the complete normalized game manifest is compared before trace comparison;
- numeric legal domains are compared explicitly;
- terminal outcomes are compared explicitly and normalized.

The FULL107 correspondence generator, mapping, identity register and digest-credit gates were aligned so the five new DIRECT promotions cannot drift silently.
