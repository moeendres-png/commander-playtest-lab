# TARGET_AMOUNT_LIVE (P-T1: PARTIAL — companion qualified, live-callback UNKNOWN)

## Qualified (DIRECTLY_VERIFIED)

- Lab companion path: target selection from the eligible set AND scalar
  descriptor [1, remaining] with the amount applied
  (`test_target_amount_companion_path`: [1,40] benefit -> 40).
- Bridge emitter unchanged and lossless (numeric_min=1,
  numeric_max=max(1, remaining); unit-proven by
  `XmageFullGamePlayerBoundaryTest` 4/4).
- Live companion violations at transport
  (`targetAmountCompanionViolationsRejectedLive`): missing companion
  fails closed at the player gate (never defaults to one); 99/0/-1
  rejected `out of range`; lawful 2 accepted.
- Scalar strictness transfers (shared `_decide_numeric` + shared
  transport/projection scalar lane with announce_x/amount).

## UNKNOWN with exact blocker (no fabrication)

Live-callback fire (`chooseTargetAmount` on the minimal fixture) is
unreachable: range-gated `possibleTargets` requires a STARTED game
(engine error pinned by `targetAmountLiveCallbackBlockedOnUnstartedGame`:
"game is not started, but you call hasPlayerInRange"). Card-driven fire
needs U5 scenario engineering (an amount-effect card cast in a live
game). No card-driven target_amount observation is claimed.

## Next

U5 scenario work (S8 scope) can close this row by firing a real amount
effect; the companion path needs no further code changes.
