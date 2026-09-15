# WS215 CARDINALITY_CONTRACT (authoritative)

One authoritative cardinality contract for the production full-game surface.
No divergent 2P/3P/4P/5P Rules semantics.

## Supported range

- `MIN_PLAYERS = 2`, `MAX_PLAYERS = 5`. Seats are exactly `1..N`.
- `deck_handles.length == pilots.length == principals.length == N ==
  scenario.player_count`.
- `scenario.seat` in `1..N`. Zero-based `starting_player_seat = seed mod N`.
- Deck identities distinct; seat-ordered deck/pilot binding; `deck_hash`
  required per seat.
- Capability truth after terminal evidence: `min_players = 2` only if 2P PASS;
  `max_players = 5` only if 2P–5P all PASS. 6P is `NOT_SUPPORTED`.

## Fail-closed cardinality (all before partial game execution)

- 0/1 decks/pilots → `FULL_GAME_INVALID_PLAYER_COUNT` (Java) /
  `FullGameConformanceError` (Python) before deck resolution / engine contact.
- N > 5 (including 6) → same rejection. No silent seat creation, no default
  fourth player, no hidden dummies, no partial lifecycle.
- Mismatched deck/pilot/principal counts, duplicate deck ids, seat-coverage
  gaps, out-of-range `scenario.seat`, out-of-range `starting_player_seat` →
  rejection.
- Unknown decision classes, wrong-actor responses, stale decisions →
  unchanged fail-closed behavior (count-free).

## Identity

- Seat→principal map is exact per game (`outcomes` seat-ordered).
- `actor == authoritative principal` (controller enforces UUID equality).
- Observations, legal actions, and concession are principal-scoped;
  concession is actor==subject==exact principal.
- Losers receive no production decisions (engine stops offering; Lab never
  synthesizes). Surviving priority/turn rings remain engine-owned.

## Rules RNG (all counts)

- `game.setRulesSeed(orchestrationSeed)` + `game.setRequireExplicitSeed(true)`
  after construction, before start/init or any Rules-random consumption.
- Live proof per payload: `rulesSeedExplicit`, seed equality,
  `getRulesRandomCalls`, truthful `seed_supported`.
- Fresh-process same-seed twins per mandatory count; distinct-seed controls
  on representative counts. No `RandomUtil` Rules authority.

## Engine authority (unchanged)

Priority, APNAP, combat, elimination, Commander rules/tax/zones/damage/
partner, turn structure, SBAs, legal actions, and Rules randomness remain
solely XMage-owned. Construction is always
`CommanderFreeForAll(MULTIPLE, ALL, LONDON(1 free), 40 life, 7 cards)` with
`setNumPlayers(N)`.

Machine companion: `CARDINALITY_CONTRACT.json`.
