# MULTI_AMOUNT_LIVE (P-M1 live half: DIRECTLY_VERIFIED)

## 1. Joint live traversal (XmageNumericDomainWs229Test)

`jointVectorWithLargeLegAndBindingTotalLive`: REAL
`getMultiAmountWithIndividualConstraints` with legs [{0,100},{0,3}] and
binding total band [50,60] through the real player + controller +
native `isGoodValues` gate.

- ONE joint frame parked (stable bytes in LIVE_FRAME_CAPTURES.json:
  `numeric_legs` + `numeric_total_min/max` + outcome, zero options).
- Submitted vector [55,3]: leg0 spans >16 (55 unofferable under every old
  per-leg collapse), total 58 inside the binding band.
- Callback returned [55,3]; the served-frames counter proves a single
  frame served the whole distribution (framesAnswered == 1 — the
  sequentializer is gone, not shadowing).
- Feasibility-preserving repair strategy proven separately
  (`multiAmountJointMinimumsRepairedToFeasibleBand`).

## 2. Forged live rejections (same suite + CombatDamageTest)

Over-maximum leg spoil rejected then feasible accepted (controller);
infeasible domain fails closed before parking; scalar-shaped multi
projection row still enforced.

## 3. Lab half (test_ws229_numeric_domain.py)

Deterministic joint [60,0] for the captured domain; reproducibility;
vector-key (not scalar) response shape; length/leg/total/malformed/
empty-domain violations fail closed; bool element rejected.
