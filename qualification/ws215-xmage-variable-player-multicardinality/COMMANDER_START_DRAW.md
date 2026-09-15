# WS215 COMMANDER_START_DRAW — PASS (uniform FFA first-draw)

`CommanderFreeForAll.init` sets `startingPlayerSkipsDraw = false` for
every player count (engine-owned; overrides the duel default). Observed
in neutral lifecycles at all counts via per-frame hand traces:

- Opening hands: exactly 7 per seat (mulligan keeps) at 2P/3P/4P/5P.
- The starting player (chosen deterministically by the seed-chosen seat
  through the native CR 103.2 choice) DRAWS on turn 1 (7→8) in every
  count — including 2P (no duel skip in Free-for-All).
- All other seats stay at 7 until their own first draw steps; life stays
  40/40 until combat develops; turn order stays cyclic (no extra-turn
  distortion in windows).
- The orchestration `starting_player_seat = seed mod N` selects the
  CR 103.2 *choosing* player; the actual starter is the native choice
  outcome (observed: registration seat 1 in the sealed runs). Both steps
  are deterministic per seed; twins agree exactly.

Fixtures `WS05-CMD-START-2`, `WS05-CMD-START-3`: RERUN → PASS.
`WS05-CMD-ELIM-4` (Commander loss integrated with multiplayer cleanup):
RERUN → PASS — commanders die in multiplayer combat (zone choices),
owners later lose/leave with native cleanup (2P terminal; 3P/5P
concession cleanup; losers' zones cleaned per WS213 finding, re-verified
via CR800.4a oracle asserts).

Machine companion: `COMMANDER_START_DRAW.json`.
