# WS228 Live Probe Plan

## Principle

Reproduce F-RULES-02 without production edits. Prefer existing
production/full-game boundaries; research-only probes live under
research/numeric-boundary/ws228/probes/** and are explicitly SYNTHETIC
(Lab-transformation semantics only — never actual-card behavior proof).

## Executed in WS228 (evidence in LIVE_PROBE_RESULTS.json)

P1 — Shared-chooser boundary probe (DONE, PASS):
unit: research/numeric-boundary/ws228/probes/numeric_boundary_probe.py.
Drives locked ExternalPilotDecisionPolicy.decide with a recording pilot.
Cases: 4 numeric classes x 8 bound pairs ([0,0],[0,5],[1,5],[0,16],[0,17],
[0,100],[1,40],[0,1000000]). Asserts full exposure at span<=16,
{min,mid,max}-only at span>16, exact boundary at 16/17, per-class routing
through the shared chooser. Result: F_RULES_02_REPRODUCED = true.

P2 — Existing Python boundary (DONE, PASS, read-only runs):
tests/unit/test_xmage_full_game_decision_matrix.py (20 passed),
tests/unit/test_xmage_full_game.py (7 passed). Confirms small-domain
behavior intact and that the suite is blind to span>16 (max tested span 5).

P3 — Existing JVM boundary (DONE, PASS, read-only runs):
XmageFullGamePlayerBoundaryTest (4/4 incl
targetAmountMissingNumericChoiceFailsClosedInsteadOfDefaultingToOne),
XmageFullGameActionProjectionTest (17/17 incl outOfRangeNumericIsRejected).
Confirms bridge-side fail-closed submission semantics on locked code.

P4 — Engine-bytecode semantics (DONE, DIRECT derivation):
javap -c on pinned 1.4.61 mage-player-human HumanPlayer.announceX/getAmount
(accept-loop proof) and mage MultiAmountType.isGoodValues (joint-lattice
proof). No engine source modified; jars read-only from local .m2.

## NOT executed in WS228 (explicitly S6 scope)

P5 — Full-game live numeric observation (actual cards, JVM):
announce_x (representative X-spell), amount, multi_amount (joint),
target_amount companion, each at span<=16 AND span>16. Requires S6
implementation first (current code cannot expose interior values, so a live
span>16 positive is unobservable by construction — attempting it now would
only re-prove the narrowing through a slower path).

P6 — Full 135-fixture campaign: explicitly forbidden by WS228 validation
scope. S6 requalification burden is scoped in S6_TEST_PLAN.md instead.

## Evidence-class discipline

- DIRECTLY_VERIFIED: P2/P3 test outcomes (exact commands in VALIDATION.md).
- CODE_DERIVED: P4 bytecode readings; trace field mappings.
- SYNTHETIC: P1 probe (transformation semantics, not card behavior).
- UNKNOWN: P5/P6 (S6 work).
