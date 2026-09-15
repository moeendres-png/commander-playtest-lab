# PLAYER_COUNT_4P — PASS (fresh regression)

Fresh 4P regression (WS213 4P PASS retained as provenance, NOT as WS215
evidence):

- Native construction with `setNumPlayers(4)`; seed binding proof live
  (matches/explicit/supported, `rules_random_calls>0`).
- Bounded lifecycle (fresh JVM, RogShai neutral, seed 424242, budget 150):
  150 decisions, turn 1→5, 4 keeps, priority ring across all four seats,
  no failure. Hash `b17378f33952`.
- Fresh-process twin: `b17378f33952` — MATCH.
- Distinct-seed control (seed 424243): `e1fdfadead93` — DIVERGES.
- Developed game (fresh JVM, Lions develop, seed 424242, budget 600):
  600 decisions, turn 1→13, combat (6 declare_attacker frames,
  4 distinct defenders, block pairs), commander casts/recasts with tax,
  zone choices (both branches), no failure. Hash `713e9d963e9d`
  (matrix build); twin MATCH; distinct-seed (424243) `d77004d087c2`
  DIVERGES.
- Forced-mulligan run (seed 424242): 2 takes by one actor, paid London
  bottom-1 target frame answered legally, keeps 6 thereafter; no failure.
- Hidden information: structural + oracle 0 violations.
- Starting draw: opening 7s; starter draws turn 1.

JUnit `XmageVariablePlayerLifecycleTest` (12/12 with the 3P/5P/6P-gate
classes): 4P lifecycle, 4P multi-defender (≥2 distinct native defenders),
4P concession flows — all PASS in-process.

Runs: `runs/4p-seed424242-*`, `runs/4p-seed424243-*`, sealed in
`runs/WS215_MATRIX.json`.

Machine companion: `PLAYER_COUNT_4P.json`.
