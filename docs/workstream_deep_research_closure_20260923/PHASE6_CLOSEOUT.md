# Phase 6 Closeout — P2 Predictive Regression Pack

Source lock (execution): worktree HEAD on `2231ff4b` (see STATE.md).
Namespace: `XmageExternalRiskSignalTest` — every case labeled
`EXTERNAL_RISK_SIGNAL` until a local failure reproduces (§14). Oracle
authority: Esior/Hex wording verified against Gatherer/Scryfall at campaign
time; casting order per CR 601.2. Engine behavior is never authority.

## Cases (all DIRECTLY_VERIFIED on current bytes, 4/4 green)

- **A (PRED-PARSER-03)** `externalRiskSubjectCountSurvivesIntoPayment`:
  real-commander Bolt pays {3}{R} (4 Mountains), non-commander Bolt pays {R}
  (5th Mountain). Subject (commanders you control), controller (opponent's
  spell), count (once) survive into runtime payment. Also proves a subtle
  Rules point: a setup-placed commander copy is NOT a commander
  (`isCommanderObject=false`, correctly untaxed); only the genuine
  command-zone-cast permanent is.
- **B+C (PRED-ZONE-04)** `externalRiskWrongObjectAndZoneDestination`:
  Unsummon on P2's Bears returns it to hand (alternative destination, not
  graveyard); P1's same-named decoy never moves.
- **D (PRED-REPL-05)** partial: commander-zone replacement choice timing
  proven (correct actor P1, correct zone-change point, explicit labeled
  selection in `resolveStackEmpty`). General replacement-effect timing still
  needs combat-temporal progression → follow-up, fail closed.
- **E (PRED-RESTORE-01)** `externalRiskRestoreDerivedStateAcrossTransition`:
  restore → full priority round + revalidation → only turn-position pins
  drift; life/zones/commanders/seed hold; layer P/T re-proven.
- **F (PRED-AUTH-07)** `externalRiskStaleAnswersRejectedWithoutMasking`:
  stale decision id rejected typed; live decision unmasked; plus Phase 3
  forgery/parked-payment/explicit-cancel evidence. No auto-pass pattern
  exists.

## New findings (follow-up dispatches)

1. **Exact-6-target offer gap**: Hex is never offered by engine `getPlayable`
   with or without Esior, at 9 or 12 mana (only the Swamp ability is
   playable). Multi-exact-target spells need an offer-path investigation
   (engine-side or bridge-enumeration follow-up). Not papered over.
2. **Cost-aware harness payment**: the homogeneous payment helper now parses
   engine `unpaid_mana` and taps exactly the required count (an over-tap
   harness defect was caught and fixed in-campaign).

## Impact

New test file only (plus shared helpers used by it); no production bytes
changed → all prior evidence retained.
