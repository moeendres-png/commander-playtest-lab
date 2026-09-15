# PLAYER_COUNT_2P — PASS

Fresh runtime evidence (not retained WS213; WS213 was NOT_SUPPORTED):

- Native construction: `CommanderFreeForAll(MULTIPLE, ALL, LONDON(1 free),
  40 life, 7 cards)` with `setNumPlayers(2)`; 2 player registration;
  `XMAGE_PLAYER_SETUP_FAILED` gate passed.
- Rules-seed binding: `setRulesSeed(424242)` + `setRequireExplicitSeed(true)`
  before start; every payload carries live proof (`rules_seed_matches=true`,
  `rules_seed_explicit=true`, `seed_supported=true`,
  `rules_random_calls>0`).
- Bounded lifecycle (fresh JVM, RogShai neutral, seed 424242, budget 150):
  150 authoritative decisions, turn 1→9, mulligan flow (2 keeps),
  starting-player choice + priority ring across both seats, no failure,
  no silently skipped callback.
  Transcript hash `b939a7f7bbb8`.
- Fresh-process twin (same seed, fresh JVM): hash `b939a7f7bbb8` — MATCH.
- Distinct-seed control (seed 424243): hash `f26f2024baf8` — DIVERGES
  (seed influence live).
- Developed game (fresh JVM, Lions develop, seed 424242, budget 600):
  600 decisions, turn 1→20, combat (declare_attacker ×5,
  declare_blocker ×4, 2 distinct defenders, block pairs observed),
  commander casts, zone choices, mana payments, no failure.
  Transcript hash `0f1fa6e0d3f9`; twin MATCH; distinct-seed
  (424243) `a434d0e7c821` DIVERGES.
- Natural terminal (supplemental 2P develop runs, seed 424242, one with
  forced mulligan): games ended natively (turn 17) — seat 0 won with
  positive life, seat 1 lost at negative life (`lost=true`, `left=true`).
  Winner natively adjudicated; transcript hashes `1f38a37d42e7` (473
  decisions, forced-mulligan path) and `e9a9edea7692` (503 decisions,
  mulligan-variant path).
- Hidden information: 150 + 600 + supplemental frames, structural 0
  violations, oracle (opponent hand/library UUID scan) 0 violations.
- Starting draw: opening 7s; starting player draws on turn 1 (8 cards;
  FFA `startingPlayerSkipsDraw=false` uniform — see
  `COMMANDER_START_DRAW.md`).

All runs: `runs/2p-seed424242-{neutral,develop}-*/primary|twin`,
`runs/2p-seed424243-*/distinct-seed`, sealed in `runs/WS215_MATRIX.json`.

Machine companion: `PLAYER_COUNT_2P.json`.
