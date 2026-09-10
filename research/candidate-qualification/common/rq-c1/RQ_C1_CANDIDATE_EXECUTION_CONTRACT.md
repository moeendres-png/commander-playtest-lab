# RQ-C1 Candidate Execution Contract (template for future workstreams)

This contract is instantiated WITHOUT changing semantic expectations when
WS52/WS53 successors (Forge/XMage) — and, if RQ-A2 justifies it, Argentum —
execute the first-wave corpus. The candidate adapter may translate fixture
syntax; it may NOT modify any scenario's semantic expected outcome.

## Per-run requirements (every future candidate run)

1. Exact engine pin/tree/build recorded (engine identity, commit, build flags).
2. Exact provider contract recorded (adapter version + seam: native progression
   entry point used for the scenario's declared setup boundary).
3. Exact fixture boundary recorded (must equal the scenario's
   `native_setup_boundary`; any deviation is FIXTURE_LIMITATION, never silent).
4. Engine-generated legal options captured verbatim (candidate-native binding
   recorded alongside the neutral semantic identity; bindings never flow back
   into the neutral corpus).
5. Principal-scoped observation captured per checkpoint in
   `RQ_C1_HIDDEN_INFO_EXPECTATIONS.json` (one projection per principal;
   adversarial no-leakage check against the planted-leak controls).
6. Externally selected option recorded per script step (neutral semantic
   identity + exact native binding + principal).
7. Native execution acknowledgement recorded (engine applied the bound option;
   request/state identity per candidate capability, staleness fail-closed).
8. Rules events recorded in neutral vocabulary (scenario `expected_rules_events`
   compared in order; extra engine-internal events ignored, missing expected
   events fail).
9. Hidden-info checks evaluated per checkpoint (leak = FAIL with evidence).
10. RNG journal recorded where `rng_operations` non-empty: purpose, valid
    domain, candidate-set fingerprint, sampled result, Rules event, replay
    assertion (seed authority recorded; harness-side randomness = FAIL).
11. Post-state fingerprint recorded in neutral vocabulary (scenario
    `expected_terminal_assertions` compared field by field).
12. Evidence class recorded using EXACTLY the project classes
    (DIRECTLY_VERIFIED / CODE_DERIVED / TECHNICALLY_CONFORMANT /
    EXTERNALLY_RULE_VALIDATED / MODELED / SYNTHETIC / UNKNOWN).
13. Fail-closed unsupported handling: any scenario unreachable through the
    candidate's authoritative production seam MUST be classified as
    ENGINE_UNSUPPORTED, PROVIDER_UNSUPPORTED, HARNESS_LIMITATION,
    FIXTURE_LIMITATION, or UNKNOWN — never replaced by a simpler
    candidate-specific case and never normalized away.

## Fairness rules (cross-candidate)

Same Rules question + same actual cards + same authoritative initial semantic
state + same external discretionary choices where legal sets permit + same
Rules-RNG prescribed outcome/journal semantics + same expected Rules outcome.
Byte-identical engine states are NOT required. Legitimate legal-set divergence
(one engine wrong) is evidence, recorded, never normalized away.

## Negative-control execution

All `RQ_C1_NEGATIVE_CONTROLS.json` controls execute against the harness before
behavior credit: stale-frame, not-in-set, wrong-principal, wrong-kind,
zero-binding, multi-binding, reordered decisions; planted hand/library/
face-down leaks; changed/omitted RNG and decisions; wrong-outcome calibration.
Any control that does not fail closed blocks behavior credit for that run.

## Verdict discipline

`UNKNOWN != PASS`. Missing evidence stays UNKNOWN. GREEN harness without the
above artifacts is NOT_RUN for qualification purposes. Full107 credit is never
granted by this contract (see `RQ_C1_FULL107_RELATION.md`).
