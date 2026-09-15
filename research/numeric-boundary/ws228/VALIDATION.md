# WS228 Validation

All runs on locked audit-base bytes (HEAD 48885e8e, clean tree except the
WS228 research directory itself). No production file modified (final
`git status` shows only `?? research/numeric-boundary/`).

## Bounded validation runs (exact commands, exact outcomes)

1. Research probe (SYNTHETIC defect reproduction):
   `python3 research/numeric-boundary/ws228/probes/numeric_boundary_probe.py`
   -> exit 0; verdicts small_domain_full/boundary_16_full/
   boundary_17_narrowed/large_domain_narrowed/
   large_domain_offered_is_min_mid_max all true;
   F_RULES_02_REPRODUCED = true (32 cases: 4 classes x 8 bound pairs).
   Sealed output: LIVE_PROBE_RESULTS.json (+ run_metadata envelope).

2. Existing Python unit boundary (DIRECTLY_VERIFIED):
   `python3 -m pytest tests/unit/test_xmage_full_game_decision_matrix.py -q`
   -> 20 passed.
   `python3 -m pytest tests/unit/test_xmage_full_game.py -q`
   -> 7 passed.

3. Existing JVM boundary, offline lane (DIRECTLY_VERIFIED):
   `mvn -o -q -pl . -am test -Dtest=XmageFullGamePlayerBoundaryTest`
   (workdir engine-bridge) -> Tests run: 4, Failures: 0, Errors: 0.
   `mvn -o -q -pl . test -Dtest=XmageFullGameActionProjectionTest`
   -> Tests run: 17, Failures: 0, Errors: 0
   (incl outOfRangeNumericIsRejected; boundary-test file read to cite the
   exact passing negative rows, not assumed).

4. Engine-native semantics derivation (CODE_DERIVED, read-only jars):
   `javap -c` on mage-player-human 1.4.61 HumanPlayer.announceX/getAmount
   (accept-loop proof) and mage 1.4.61 MultiAmountType.isGoodValues
   (joint-lattice proof); `javap -p` on Player interface (signature proof).
   No engine bytes modified (jars under ~/.m2, read-only use).

5. WS226 identity + delta verification (machine-checked):
   fetch origin branch -> HEAD fb156d2b == expected; TREE 52359f47 ==
   expected; full_game.py blob 7bd3bc28 on BOTH WS223 and WS226;
   narrowing hunk present on WS226 bytes; 14/14 material paths
   byte-identical (NO_IMPACT); 2 scope-adjacent diffs inspected hunk by
   hunk (message rewording + additive suites only).
   Sealed: WS226_DELTA_REVALIDATION.json. Verdict: DELTA_REVALIDATION_PASS.

## Deliberately NOT run (scope compliance)

- FULL107: NOT_RUN (broad campaigns forbidden in WS228).
- 135-fixture campaign: not run (S8 scope per action graph).
- Full-game live JVM numeric scenarios: not run (unobservable positives
  pre-S6 by construction; S6 scope per S6_TEST_PLAN.md).
- No test source modified outside the WS228 research namespace
  (nothing modified at all outside it).

## Hard-gate checklist (WS228 COMPLETE requires 1-14)

1. F-RULES-02 independently reproduced: YES (probe + boundary, §1).
2. First narrowing point identified exactly: YES (full_game.py:750-754).
3. Core-authoritative domain semantics documented: YES
   (DOMAIN_AUTHORITY_ANALYSIS.md + NUMERIC_DOMAIN_TRACE.json).
4. Every production numeric callsite inventoried: YES (1/2/4 —
   NUMERIC_CALLSITE_INVENTORY.json).
5. announce_x/amount/multi_amount separately adjudicated: YES (matrix +
   F-RULES-02b for multi_amount).
6. Canonical decision-family matrix: YES (17 classes,
   DECISION_CLASS_MATRIX.json).
7. Preferred repair design + rejected alternatives: YES (B preferred;
   A runner-up; C folded; D rejected — DESIGN_OPTIONS.md/CHOSEN_DESIGN.md).
8. No-second-Rules-engine argument explicit: YES
   (DOMAIN_AUTHORITY_ANALYSIS.md verdict + CHOSEN_DESIGN.md section).
9. Replay impact resolved at design level: YES (REPLAY_IMPACT.md; replay
   untouched).
10. Large-domain performance bounded: YES (PERFORMANCE_BOUNDARY.md; O(1)).
11. Positive + rejection-negative S6 matrices ready: YES
    (POSITIVE_MATRIX.json 6 cases; NEGATIVE_MATRIX.json 23 cases).
12. WS226 delta-revalidation predicates defined: YES (+ EXECUTED against
    terminal WS226 — WS226_DELTA_REVALIDATION.json PASS,
    RETENTION_PREDICATES.json for S6 entry).
13. Production source untouched: YES (git status + diff inspection).
14. Behavior credit unchanged: YES (0; no PASS/FIXED claims — see below).
