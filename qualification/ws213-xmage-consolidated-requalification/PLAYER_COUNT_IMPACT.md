# WS213 PLAYER_COUNT_IMPACT

The freeze contract wants independent full-lifecycle 2P/3P/4P/5P. The WS213
production path (`XmageFullGameSession`) is operationally scoped to exactly
four players by construction (`FULL_GAME_REQUIRES_EXACTLY_FOUR_PLAYERS`;
`PLAYER_COUNT = 4`). This matches the mission's primary 4P benchmark; it is
not an architecture anchor (no 4P assumption leaks into shared contracts).

- 4P: PASS — full requalification matrix on this lane (12 constructions,
  twins, E02/G04 mechanisms, hidden-info, D1–D5).
- 2P/3P/5P: NOT_SUPPORTED (evidenced, not assumed):
  `XmageFullGamePlayerCountTest` 3/3 proves 2/3/5-handle construction fails
  closed with `FULL_GAME_REQUIRES_EXACTLY_FOUR_PLAYERS` before any engine
  contact. No silent game, no fallback, no partial lifecycle.
- Technical Rules-Core conformance for 2–5P is NOT established by WS213.

Bounded successor requirement (no broad rewrite in WS213): a
`VariablePlayerFullGameSession` workstream that (1) parameterizes player
count 2–5 through `CommanderFreeForAll`/`GameOptions`, (2) replays the WS213
binding/concede/combat/hidden-info proofs per count, (3) seals per-count
twin evidence, (4) records per-count credit independently. Until then 2P/3P/5P
stay NOT_SUPPORTED (fail closed), never UNKNOWN-as-PASS.

Machine companion: `PLAYER_COUNT_IMPACT.json`.
