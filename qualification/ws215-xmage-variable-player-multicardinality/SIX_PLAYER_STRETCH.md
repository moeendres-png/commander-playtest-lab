# WS215 SIX_PLAYER_STRETCH — NOT_SUPPORTED (bounded, not attempted as gameplay)

Gate (all required before any 6P attempt): 2P/3P/4P/5P PASS ✓,
no material cardinality defect ✓, no hidden-info regression ✓
(9985 oracle frames, 0 violations), no process/reliability blocker ✓
(all 24 matrix + 10 observation/supplemental runs clean).

Bounded 6P evidence (exact):

- Construction with 6 deck handles fails closed at the session boundary
  with `FULL_GAME_INVALID_PLAYER_COUNT` before deck resolution
  (`XmageFullGamePlayerCountTest.sixPlayerConstructionFailsClosed` PASS);
  the JSONL bridge rejects 6 handles with `invalid_player_count`
  (`XmageFullGameBridgeContractTest.rejectsSixPlayerFullGameBeforeDeckResolution`
  PASS). No silent game, no partial lifecycle, no dummy seats.
- Supporting 6P would require: raising `MAX_PLAYERS`, re-qualifying the
  full per-count matrix at 6P (lifecycle/twins/controls), hidden-info
  oracle at 6 principals, and Commander Free-for-All 6P Rules review —
  material architecture expansion beyond this workstream's mandate
  (2P–5P qualification must not be delayed for 6P).

Disposition: `PLAYER_COUNT_6P = NOT_SUPPORTED` (fail-closed, evidenced),
never UNKNOWN-as-PASS. Bounded successor specified above.

Machine companion: `SIX_PLAYER_STRETCH.json`.
