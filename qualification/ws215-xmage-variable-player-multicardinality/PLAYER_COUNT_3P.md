# PLAYER_COUNT_3P — PASS

Fresh runtime evidence (not retained WS213; WS213 was NOT_SUPPORTED):

- Native construction with `setNumPlayers(3)`; 3 registrations; seed
  binding proof live on every payload (matches/explicit/supported,
  `rules_random_calls>0`).
- Bounded lifecycle (fresh JVM, RogShai neutral, seed 424242, budget 150):
  150 authoritative decisions, turn 1→6, mulligan flow (3 keeps),
  starting-player choice + priority ring across all three seats, no
  failure. Transcript hash `3af22b141f7e`.
- Fresh-process twin: `3af22b141f7e` — MATCH.
- Distinct-seed control (seed 777001): `c7224e50cc54` — DIVERGES.
- Developed game (fresh JVM, Lions develop, seed 424242, budget 600):
  600 decisions, turn 1→17, combat (10 declare_attacker frames,
  3 distinct defenders, 10 block pairs over 10 frames), commander casts
  and recasts with tax, zone choices (both branches), mana payments,
  no failure. Transcript hash `73505f9ba9b9`; twin MATCH;
  distinct-seed (777001) `d8dd35a12f99` DIVERGES.
- Elimination (JUnit, in-process): concession of one seat marks exactly
  that principal lost/left; survivors continue deciding; owned zones
  cleaned (CR800.4a oracle asserts); seat map stays exact. See
  `PLAYER_ELIMINATION_CR800_4.md`.
- Hidden information: structural 0 violations; oracle 0 violations
  (150 + 600 frames); 3-principal cross-scoping every frame.
- Starting draw: opening 7s; starter draws turn 1 (see
  `COMMANDER_START_DRAW.md`).

Runs: `runs/3p-seed424242-*`, `runs/3p-seed777001-*`, sealed in
`runs/WS215_MATRIX.json`.

Machine companion: `PLAYER_COUNT_3P.json`.
