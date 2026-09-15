# WS229 U4 Joint-Transport Spike (pre-H6, read-only analysis + verdict)

## Question

Can the DecisionController transport carry a joint multi_amount frame, or
must per-leg sequential frames remain (as a shim)?

## Findings (CODE_DERIVED from locked base source)

1. `DecisionResponse` carried exactly one `Integer numericChoice` — no
   vector field. Transport could not express a joint pilot decision.
2. `submit()` parsed only `numeric_choice`; the Lab `decide()` emitted only
   a scalar `numeric_choice`. A joint pilot-facing shape had no wire path.
3. Sequential per-leg frames cannot serve a joint pilot decision without
   fragile cross-frame caching: the engine blocks per leg, each leg frame
   carries only recomputed coupled bounds (no legs/totals), so the Lab
   cannot reconstruct the joint domain without inventing legality
   (forbidden). The shim alternative was rejected on authority grounds,
   not taste.
4. Native `MultiAmountType.isGoodValues(List, messages, totalMin, totalMax)`
   exists on the pinned engine and takes the ORIGINAL messages — a joint
   frame can be gated natively without any coupled-bounds recomputation.

## Verdict (implemented as H6)

Joint-frame transport: ONE `multi_amount` frame per native callback with
context `{numeric_legs: [{min,max,prompt}], numeric_total_min,
numeric_total_max, outcome}`, zero options, and a `numeric_choices`
integer-array response. Validation of the exact isGoodValues projection
(length, per-leg membership, total band) lives at three layers with the
identical predicate: Lab `_decide_multi_amount`, controller
`requireJointVector` (transport), projection `validateJointVector`
(generic-submission lane), player `requireJointChoices` — closed by the
NATIVE `isGoodValues` gate over the original messages. The sequentializer
is deleted (no shim retained): the task permits a shim but does not
require one, and a shim would reintroduce caching risk with zero
authority benefit.

## Compatibility

Additive optional wire field; old readers ignore unknown keys; old Lab
fails closed (not silent) on joint frames it cannot parse; new bridge +
old Lab cannot co-occur in one deployment (same repository). No protocol
version bump required (see NUMERIC_DOMAIN_CONTRACT.md).
