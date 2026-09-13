# WS92 Final Report — XMage D1–D5 Boundary Reacquisition

Status: COMPLETE (implementation + census). No behavior credit claimed.
Source lock: `6baa24d465d43eb10456fc846efb44f7c42dfc66`. Engine pin unchanged:
`cfc36f445f917f101fa2ed588770e043f53bc44c`.

## Objective

Systemically reacquire the five WS60 D1–D5 external-control capabilities on
current `cfc36f` without cherry-picking stale production code, then run an
actual-card-driven census of the corrected WS90 First-Wave 20 decision kinds
to fix the exact remaining authoritative boundary blockers. No behavior
scoring run.

## D1–D5 reacquisition (all fresh runtime evidence on current main)

- D4 key-mode Choice projection + twin-stable redaction —
  `XmageFullGameDecisionController` (`redactObjectIds` on every option
  label/metadata), `XmageFullGamePlayer.choose(Choice)` (key-mode branch,
  `choiceText`/`choicePrompt`) — `Ws92D4ChoiceProjectionTest` (5 tests).
- D5 content-stable attacker/blocker ordering — `stablePermanentOrder`
  (name, zone-change counter, P/T, tapped, damage; never native UUID) —
  implemented; twin-equality replay remains UNKNOWN (single-game lane).
- D1 grant-scoped hidden-library projection + D2 entitled look window —
  `XmageFullGameStateRedactor` grant registry (`begin/endZoneFullLook`),
  `granted_library` per-player array, try/finally window in
  `chooseTargetInternal` + `lookOwnerFor` — `Ws92D1D2D3ProjectionTest`.
- D3 public projections — P/T/damage/counters + face-up-gated ability text
  on permanents, `commander_status` (registry ∪ command-zone union with
  damage totals and casts-from-command) — same test (real started game:
  8 commander entries; grant scoping per viewer/owner; face-down gating).

No WS60 production file restored; no engine edits; WS80 fail-closed
boundary preserved (full suite green, incl. `XmageBridgePlayerFailClosedTest`,
`XmageFullGameBridgeContractTest`, `XmageFullGameInventoryTest`).
Global capability flags untouched (`legal_actions`/`action_submission` false).

## Decision-kind census (non-scoring, actual cards, RogShai ×4, seed 7017)

`Ws92DecisionKindCensusTest` drives a real started game with a
pass/keep-only driver (keep, pass, attacker hold, zero blockers,
setup-honoring starting-player vote; richer decisions recorded unanswered).
Result: 37 answered, stopped fail-closed on turn-1 cleanup discard
(`choose_object`, 8 hand options). Sealed artifact: `DECISION_KIND_CENSUS.json`.

- OBSERVED (reachability only, never PASS): `pass`, `hidden-zone selection`.
- NOT_OBSERVED (18): `cast`, `targets`, `mana payment`, `activate`,
  `mana source`, `X`, `replacement ordering`, `trigger ordering`, `modes`,
  `copy choices`, `search`, `attackers`, `defender per attacker`, `blockers`,
  `combat damage assignment`, `alternate cost`, `Commander movement`,
  `concession` — every one blocked on the B4-D action-submission pilot.

## Verdict

`WS92_D1_D5_REACQUISITION = COMPLETE` (fresh implementation + runtime
evidence, zero cherry-pick). `XMAGE_FIRST_WAVE_EXECUTION_READINESS` remains
`BLOCKED_BY_BOUNDARY`: the exact remaining blocker is the B4-D
action-submission pilot, unchanged from WS90 and now confirmed with fresh
runtime evidence on the D1–D5 bridge. `BEHAVIOR_CREDIT_CHANGE = 0`,
`XMAGE_RQC3_FIRST_WAVE = NOT_RUN`. Architecture Freeze NOT_CLAIMED,
Production Provider NOT_SELECTED.
