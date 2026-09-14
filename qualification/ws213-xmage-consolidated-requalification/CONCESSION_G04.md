# WS213 CONCESSION_G04 — `G04_CONCESSION = PASS` (runtime mechanism)

Historical G04 BLOCKED (no concede decision) is superseded by WS211
`canConcede`/`concede` on this pin.

- Offer: `get_concede_offer` returns native `Game.canConcede` availability
  per exact principal plus a `concede` LegalAction (no heuristic; CR 104.3a /
  723.6: no priority/stack/turn-control requirement — conceding during
  another principal's pending decision works).
- Execution: `submit_concede` requires actor == subject == exact session
  player UUID, re-checks `canConcede` live, arms a one-shot principal-bound
  token, and calls native `Game.concede` (`PlayerImpl.concede` path:
  queue + `lost`); the player override releases only the armed call, else
  `OUT_OF_SCOPE_DECISION` (existing fail-closed test preserved).
- Negatives: unknown principal / actor≠subject (controller-for-controlled)
  / malformed id → `PILOT_RESPONSE_INVALID`; post-loss resubmit →
  `CONCEDE_UNAVAILABLE`; unattributed `player.concede` still fail-closed.
- Runtime (G04 decks, seed 9112, 500 budget, primary+twin): seat 3 offered +
  executed at decision 60 in BOTH runs; game continued to budget with the
  conceder lost and all other principals deciding (twin_match TRUE).
- Unit: `XmageFullGameConcedeActionTest` 5/5 (offer, execute+lost, continue,
  foreign/mismatch/stale negatives, unattributed fail-closed).

Scenario credit stays 0: the pack's G04 terminal (P0 leaves with the stolen
Bear reverting) requires the Control-Magic setup, which did not assemble in
budget; the interrogation deliberately used seat 3 to leave scenario seats
intact. Mechanism requalification is complete; behavior credit is not claimed.

Machine companion: `CONCESSION_G04.json`.
