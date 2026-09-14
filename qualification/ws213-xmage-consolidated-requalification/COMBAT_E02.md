# WS213 COMBAT_E02 — `E02_COMBAT = PASS` (runtime mechanism)

Historical E02 BLOCKED (no Player damage hook) is superseded by the WS206
engine path on this pin. Runtime proof (seed 29108, budget 6000, fresh
processes, offered-only press/block-all, one-shot spoil):

- Native `declare_attacker` offers → generic submit (Tyrant ×19 attacks).
- Native `declare_blocker` offers → generic submit (Elves+Bear double-block
  at offsets 4164–4165; Bear single-block at 4310).
- Native trample `multi_amount` dialogue through
  `requestLegalTrampleBlockerAssignment` (bounds-verified against
  `CombatGroup.java:280-310,909-935`): frame 1 bounds (0..7) answered 7
  (spoil-max), frame 2 bounds (0..0) forced 0 — natively LEGAL first attempt
  (total ≥ lethal floor 3; through-damage 0 short-circuits; 702.19b
  over-assignment permitted), no re-request; frame 3 (second combat) bounds
  (2..7) answered 2 (lethal min).
- Correct Rules resolution: blockers dead, Tyrant 7/6 alive throughout, game
  continued to its natural conclusion (seat 1 wins; losers' zones cleaned on
  leave); twin followed all 5746 decisions with zero divergence and identical
  hash (incl. the spoil replay).
- Current CR510 honored: free distribution, complete-assignment validation;
  no Damage Assignment Order semantics anywhere
  (`DAMAGE_ASSIGNMENT_ORDER_PRESENT = NO` per WS206 audit).

Boundaries (honest): the pack-exact 2/1/4 split and P0@36 were not
reproduced (engine accepted the legal 7/0 first attempt); a runtime illegal
allocation was never offered (bounds + validation make it unreachable here)
— illegal handling is covered by Java unit negatives (out-of-range rejected,
infeasible fail-closed) and the WS206 native matrix (validation +
5-attempt re-request + fallback, 13 tests). Scenario behavior credit stays 0.

Machine companion: `COMBAT_E02.json`.
