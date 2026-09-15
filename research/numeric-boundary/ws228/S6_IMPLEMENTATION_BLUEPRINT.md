# S6 Implementation Blueprint (implementation-ready; no code in WS228)

## Baseline

S6_BASE_SHA = fb156d2b4cf8c5c21d0c84e844a53160032c0992
S6_BASE_TREE = 52359f47eea7ddc1e4ec8187e89b67fa67d63616
(All WS228 findings retained on this base by byte-identical predicates —
WS226_DELTA_REVALIDATION.json / RETENTION_PREDICATES.json.)

## 1. Chosen architecture

Family B — range-native pilot decision (CHOSEN_DESIGN.md). Scalar
descriptor {kind,min,max,outcome,prompt} + BasePilot.choose_number
(default raise); joint vector descriptor {legs,totals} +
choose_numbers; Lab-side exact-membership validation; no fallbacks.

## 2. Exact hunks to change

H1 — full_game.py decide() ~383-384: route announce_x/amount/
multi_amount to the new descriptor path (multi_amount → joint path).
H2 — full_game.py decide() ~405-406: target_amount companion → scalar
descriptor path.
H3 — full_game.py _decide_numeric ~736-774: replace view-enumeration
with descriptor build (keep missing/reversed-bounds guards) +
choose_number(s) call + membership validation + int return.
H4 — agents/pilots.py: add choose_number/choose_numbers (Base raise;
concrete strategies deterministic + stochastic).
H5 — replay (only if vector field needed): tape.py numeric_choices +
recorder descriptor-digest binding + consumer legs/totals equality,
under WS218 versioning.
H6 — bridge multi_amount (XmageFullGamePlayer 936-977): only per U4
spike outcome (joint transport vs shim).
H7 — F-RULES-03 five dispositions (same files; WS220 S6 surface):
single-offer forced-move log; mulligan-cap forced-keep log; priority
mana-withhold disposition; pool-shortcut disposition; London-bottom
structured-context routing.

## 3. Callsite inventory (NUMERIC_CALLSITE_INVENTORY.json)

1 chooser def, 2 invocation sites, 4 classes
(announce_x/amount/multi_amount/target_amount-companion).

## 4-6. Per-class dispositions

- announce_x: scalar descriptor; live X-spell observation span<=16 + >16.
- amount: scalar descriptor; same observation shape.
- multi_amount: JOINT vector restoration (F-RULES-02b closed as part of
  S6 only because the joint shape is the native-correct shape — tracked
  as a separate row, not silent scope growth); sequentializer becomes
  transport shim at most.

## 7-8. Matrices

POSITIVE_MATRIX.json (P-A1/P-A2/P-M1/P-T1/P-B1/P-N1) and
NEGATIVE_MATRIX.json (N-01..N-23) are the executable gates: S6 hard gates
are announce_x/amount/multi_amount live-observed incl span>16 + 14
remaining classes live rejection negatives.

## 9. Remaining decision-family evidence

DECISION_CLASS_MATRIX.json: 13 non-numeric classes need live rejection
negatives; numeric 4 need repair + observation. No row may be marked
without the exact error family observed live.

## 10. Replay impact

REPLAY_IMPACT.md: no schema change for scalars; typed vector field for
multi_amount; descriptor-digest binding; numeric-step digest shape change
is expected + versioned; WS218 dual-replay positives re-run for
numeric-bearing scenarios.

## 11. Process isolation

JVM live scenarios scenario-per-process; unit suites per-file processes
for the new numeric suites; offline mvn lane as WS228 used.

## 12. Requalification burden

Medium (per WS220 S6: live observation runs for numeric classes). No
FULL107, no 135-fixture campaign, no behavior credit beyond observed
rows (credit stays 0 until observed; observed rows credit per standing
governance, not by S6 fiat).

## 13. Retained-evidence predicates

RETENTION_PREDICATES.json: machine checks S6 re-runs at entry; all green
-> implement immediately.

## 14. Remaining UNKNOWNs (CURRENT_EVIDENCE_GAPS.json)

U1 maxima distribution (collected during S6 runs), U2 actual-card firing
(the S6 positives themselves), U3 base-drift (entry predicates), U4 joint
transport (pre-implementation spike), U5 cheapest-reach scenarios (test
instantiation).
