# Multiplayer Comparison — XMage vs Forge (FINAL-PROVIDER-CDQ-20260927)

Primary player count: 4. Technical conformance requirement: 2–5 players.
6 players: bounded secondary evidence only. 7 players: explicit FAIL_CLOSED
is acceptable (and proven for XMage).

## XMage evidence (reconciled authority `59332671…`)

- 2P/3P/4P/5P lane gates PASS with replay MATCH (Isamaru+Plains scope;
  SUPPORTING at fixture level — not the bound Rograkh+Mountain/424242
  fixtures, so PLAYER_COUNT rows stay SUPPORTING per Gate B).
- L3 temporal driver: 2–5P postcombat progression, real attack/no-block flow,
  extra-turn ordering, simultaneous beginning-trigger ordering.
- L4 stack: Lightning Bolt at 3P/4P/5P; TRIG-3/5 DIRECT (Soul Warden APNAP).
- L6 elimination 21/21: lethal/Commander/active-player loss, winner/draw,
  cleanup discards under caller-owned expendable-name contract, priority-ring
  and turn recomputation at 2P/3P/4P/5P; active-player departure proven
  behaviorally against CR 800.4j diagnostic (Outcome B semantics; raw-null-
  active retained UNKNOWN with reason); poison/deck-out causation UNKNOWN.
- Commander DIRECTs at exact counts: TAX-2/4, MULL-2/4, PARTNER suite (4P),
  DMG-SPLIT + PARTNER-DMG (4P independent edges), START-3 (3P first-turn draw
  8/7/7).
- Bounded 6P smoke PASS (general surface only — explicitly NOT
  mechanism-specific elimination evidence). 7P FAIL_CLOSED.
- Injection-blocked multiplayer fixtures (13 rows: PRIO-3/5, COMBAT-4/5,
  BLOCK-4, TURN-3/5, ELIM-OWNED/CONTROL/STACK/PRIO/TURN-3, ELIM-5) stay
  NOT_RUN_BLOCKED: `starting_state_injection_supported=false`
  (contract-locked); L-layer causal cells used genuine transactions + bounded
  initial config, not generic injection.
- Readiness: 2P/3P/5P SUPPORTING; 4P TECHNICALLY_CONFORMANT; 6P SUPPORTING
  (bounded); 7P TECHNICALLY_CONFORMANT (fail-closed); starting-player
  TECHNICALLY_CONFORMANT; mulligan DIRECT; commander_damage DIRECT; partner
  DIRECT; commander_tax DIRECT.

## Forge evidence

- WSR20 `MULTIPLAYER_RESULTS.json` contract-claimed but ABSENT locally:
  UNKNOWN. H4 Forge materialization PASS is technical-only (container
  materialization, not Rules behavior).
- No 2–5P conformance evidence for Forge exists in Lab source truth.

## Comparison

All 101 common fixtures NON_COMPARABLE (Gate C): no cross-engine
same-deck/same-seed execution exists in Lab truth. The Gate D matrix
(rank 14, multiplayer_blocked + per-count conformance) defines the minimal
runtime to make multiplayer comparable: 4P primary; 2P/3P/5P conformance for
promoted rows; same decks/cards; seed 424242 where both engines expose a real
Rules-RNG binding; same discretionary choices; same semantic stopping
condition.
