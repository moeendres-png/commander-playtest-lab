# PLAYER_COUNT_5P — PASS

Fresh runtime evidence (not retained WS213; WS213 was NOT_SUPPORTED):

- Native construction with `setNumPlayers(5)`; 5 registrations; seed
  binding proof live on every payload.
- Bounded lifecycle (fresh JVM, RogShai neutral, seed 424242, budget 150):
  150 decisions, turn 1→4, 5 keeps, priority ring across all five seats,
  no failure. Hash `ae8230646f9b`.
- Fresh-process twin: `ae8230646f9b` — MATCH.
- Distinct-seed control (seed 999003): `a2d1e8d37e41` — DIVERGES.
- Developed game (fresh JVM, Lions develop, seed 424242, budget 600):
  600 decisions, turn 1→12, combat (4 declare_attacker frames,
  5 distinct defenders, block pairs over 2 frames),   commander
  casts/recasts with tax (watcher `casts_from_command = 2` observed for a
  recast commander), zone choices (both branches), no failure.
  Hash `4b930a17aa8d`; twin MATCH; distinct-seed (999003)
  `6579d673f621` DIVERGES.
- Elimination incl. active-player-leaves and 5-player recomputation
  (JUnit, in-process): conceder lost/left, 5-entry map exact, survivors
  continue, turn recomputed natively. See
  `PLAYER_ELIMINATION_CR800_4.md`.
- Hidden information: structural 0 violations; oracle 0 violations
  (150 + 600 frames); P1 vs P2/P3/P4/P5 scoping every frame.
- Starting draw: opening 7s; starter draws turn 1.

Runs: `runs/5p-seed424242-*`, `runs/5p-seed999003-*`, sealed in
`runs/WS215_MATRIX.json`.

Machine companion: `PLAYER_COUNT_5P.json`.
