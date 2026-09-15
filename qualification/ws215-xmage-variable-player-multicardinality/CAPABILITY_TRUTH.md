# WS215 CAPABILITY_TRUTH

Authoritative capability after terminal evidence (all intermediate required
counts 2–5 production-supported and qualified):

- `min_players = 2` (2P PASS)
- `max_players = 5` (2P/3P/4P/5P PASS)
- `6P = NOT_SUPPORTED` (fail-closed construction rejection; see
  `SIX_PLAYER_STRETCH.md`)

Surfaces:

- Engine lane (`get_capabilities` / `full_game_lane` / `start_engine`):
  `min_players = 2`, `max_players = 5` (was: singular
  `operational_pod_size = 4`). Per-game truth stays in
  `statusPayload.player_count` / `operational_pod_size` (= N for the game).
- Python (`XmageFullGameRunner` handshake): scenario count must lie within
  the lane `[min_players, max_players]`; creation and result payloads must
  equal `scenario.player_count` exactly.
- Contract artifacts (`ARCHITECTURE_INVARIANT_REPORT.json`):
  `min_players / max_players / operational_pod_sizes = [2, 3, 4, 5]`
  (regenerate via `scripts/generate_full_game_contract_artifacts.py`).

Before qualification was complete the lane still advertised 4P-only; the
2–5 advertisement shipped only with this evidence.

Machine companion: `CAPABILITY_TRUTH.json`.
