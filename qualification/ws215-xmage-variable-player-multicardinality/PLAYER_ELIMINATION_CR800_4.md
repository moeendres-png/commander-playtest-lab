# WS215 PLAYER_ELIMINATION_CR800_4 — PASS (3P/5P concession + owned/priority/active/5P)

Elimination is engine-owned (`Game.canConcede` / `Game.concede`); the Lab
only observes/projects. Proven in 3P and 5P (not only 4P) via JUnit
`XmageVariablePlayerLifecycleTest` (in-process, real sessions, Lions
develop where boards matter):

- CR8004_OWNED_OBJECTS: 3P + 5P develop-then-concede the richest seat
  (non-vacuous: pre-concede owned-object score > 0 asserted). Native
  oracle post-concede: leaver graveyard = 0, hand = 0, controlled
  permanents = 0. PASS.
- CR8004_CONTROL_EFFECTS: UNKNOWN — no active control-changing effect
  existed in the bounded windows (Control-Magic setup unassembled, as in
  WS213 G04). Mechanism engine-owned, untouched. Exact cause recorded.
- CR8004_STACK: PASS (vacuous within windows, documented): stack empty at
  every elimination moment (max observed stack depth 1 in lifecycles, 0
  at all concedes); no leaver-owned stack object existed to clean; no
  residue wedged any game (all continued or terminated natively).
- CR8004_PRIORITY_HOLDER: 3P concede-the-pending-actor test — priority
  recomputed natively to a survivor (leaver never acts again). PASS.
- CR8004_ACTIVE_PLAYER: 5P concede-the-active-player test — turn
  continued and turn number recomputed natively; 5-entry map exact. PASS.
- CR8004_5P_RECOMPUTATION: 5P elimination → 4 survivors keep deciding
  through the recomputed ring (40+ post-leave decisions); outcomes map
  stays exact. PASS.
- Concession negatives preserved per count: unknown principal /
  actor≠subject / malformed id → `PILOT_RESPONSE_INVALID`; post-loss
  resubmit → `CONCEDE_UNAVAILABLE`; controller-for-controlled rejected.
- 2P natural terminal (develop, turn 17): seat 0 won, seat 1 lost at
  negative life with `lost=true, left=true` — loss/elimination integrated
  with cleanup (winner adjudicated natively).

Fixtures `WS05-MP-ELIM-OWNED-3`, `-CONTROL-3`, `-STACK-3`, `-PRIO-3`,
`-TURN-3`, `WS05-MP-ELIM-5`: RERUN → PASS except `-CONTROL-3` UNKNOWN.

Machine companion: `PLAYER_ELIMINATION_CR800_4.json`.
