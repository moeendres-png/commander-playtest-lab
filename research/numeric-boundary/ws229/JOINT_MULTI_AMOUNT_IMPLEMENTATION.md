# WS229 Joint multi_amount Implementation (H6 + H4 vector parts)

## Pilot-facing semantics (one joint bounded integer-vector decision)

Per-leg min/max + total_min/total_max in a single descriptor; single
`choose_numbers` call; single `numeric_choices` vector response.
Per-leg frames never appear as separate pilot strategic choices (the
sequentializer is deleted, not demoted).

## Changed hunks

- `XmageFullGamePlayer.getMultiAmountWithIndividualConstraints`: builds ONE
  joint frame (legs verbatim from `MultiAmountMessage`s, totals verbatim,
  outcome string, zero options), validates the returned vector with
  `requireJointChoices` (length, strict ints, per-leg, total), then gates
  on the NATIVE `MultiAmountType.isGoodValues` over the original messages.
  Empty domains (min-sum > totalMax, max-sum < totalMin, reversed band,
  reversed leg) fail closed BEFORE parking any decision.
- `XmageFullGameDecisionController`: `DecisionResponse` gains
  `List<Integer> numericChoices`; `submit()` parses `numeric_choices`
  (strict integer array), rejects scalar+vector mixing, enforces the joint
  predicate via `requireJointVector` when the frame carries legs, rejects
  vectors on frames without legs (`not authorized by decision schema`),
  and newly rejects scalar numbers on frames without bounds (N-22
  transport lane). Transcript records `numeric_choices`.
- `XmageFullGameActionProjection`: `numeric_choices` allow-listed;
  `jointOnly` lane validates the joint predicate (`validateJointVector`)
  and passes the vector through; scalar/vector mixing and unauthorized
  vectors fail closed; `project()` emits one numeric action for joint
  frames; `choicesSchema` describes legs/totals verbatim.
- Lab `_decide_multi_amount` + recorder/consumer/tape vector fields (see
  REPLAY_IMPACT.md).
- Pilots: `BasePilot.choose_numbers` raises; mixin strategy =
  per-leg outcome extremes (benefit->max, detriment->min, neutral->mid)
  + deterministic greedy band repair (span-sum bounded, always
  terminates); stochastic = per-leg seeded draws + same repair.
  Unrepairable (empty) domains return unrepaired so the Lab fails closed.

## Equivalence proof (CODE_DERIVED + DIRECTLY_VERIFIED)

- The Lab, controller, and projection predicates are textually the same
  check (length, per-leg inclusive, total band) over the same transmitted
  bounds — projection, not legislation.
- The native `isGoodValues` gate over the ORIGINAL messages accepts every
  vector the projection accepts in all executed cases (joint live tests
  green; any future divergence fails closed at the native gate, never
  silently).
- Live joint frame bytes (MULTI_AMOUNT_LIVE capture): legs + totals in
  context, zero options; vector [55,3] with a span-100 leg and band
  50..60 submitted and consumed natively in ONE frame
  (framesAnswered == 1 asserted).
