# WS232 Finding: look-then-bottom pilot-domain gap (fail-closed)

## Observation (DIRECTLY_VERIFIED)

CARD_12 (Dig Through Time) attempts repeatedly reach: engine offers Dig,
pilot selects, engine consumes, take-2 selection answered through the
`choose_object` path, then the run ends with:

`FullGameProtocolError: pilot bottom-card selection is not XMage-legal`

at the rest-on-bottom step (turn ~16, ~19 decisions after selection;
e.g. `runs/card/CARD_12_2P_seed777021.json`: decisions 362, bottom
illegality, game not terminal, budget not exhausted).

## Mechanism (CODE_DERIVED, read from source)

`ExternalPilotDecisionPolicy._decide_targets` routes every
`context.bottom_of_library_selection == True` decision through the actor's
HAND (`_hand_action` views) and requires the answer to be a subset of the
offered option IDs. That domain is correct for London mulligan bottoms
(options ARE hand cards; 800+ WS232 games prove it) but wrong for
look-then-bottom effects (Dig: options are the looked cards, hand is a
different set). Both the generic pilot and the WS232 spotlight pilot
answer from hand views, so the mismatch fails deterministically whenever
the sets differ.

## Classification

- NOT a Rules-semantics defect: engine legality, costs, targets, and the
  take-2 selection are intact; nothing is fabricated or skipped.
- Pilot-coverage limitation that FAILS CLOSED (raises instead of
  defaulting/skipping). Fail-closed is the policy-correct behavior.
- Out of scope to fix inside WS232: changing `src/**` pilot semantics
  merely to obtain Dig evidence is explicitly forbidden by the WS232
  production-mutation boundary.

## S8 disposition

- CARD_12 cells (2P/3P/5P): UNKNOWN with this exact cause (offer + select
  + take-2 proven; rest-on-bottom-5 unanswerable in-lane). They are
  honestly terminal; the attempts document the boundary precisely.
- Independent rows are unaffected (no other retained card uses the
  look-bottom path; Lions-based micro/replay runs never enter it).
- Successor note: a dedicated pilot-domain remediation (bottom decisions
  answered from the offered option domain, not the hand domain) belongs
  to a future workstream, chartered in FINAL_HANDOFF. No silent fix here.
