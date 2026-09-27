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

## Forge evidence (ingested WSR20, tip `18bba95a…`)

- `MULTIPLAYER_RESULTS.json`: 2P/3P/4P/5P DIRECTLY_VERIFIED (WS233 lifecycles
  + R15 combat/trigger/concede/hidden + R20 start/tax/elim/commander suites +
  R9–R13 + G02/G03 + Propaganda split at 4P); 6P bounded SUPPORT
  (R16 lifecycle/combat/fanout/concede/hidden/twins; extra-denominator);
  7P FAIL_CLOSED (PLAYER_COUNT_UNSUPPORTED, no session, no truncation).
- Zone-replacement branches all 8 DIRECT (incl. library-bottom via Condemn);
  partner zone/tax DIRECT; damage suite (21-lethal/split/control) DIRECT;
  elim stack/ring/turn/owned/control DIRECT at 3P (+ ELIM-5 mechanism TC:
  5P ring-recompute assert missing); MP-TURN-3/5 TC (two-extra ordering
  residual); START-2/START-3 DIRECT (first-turn draw skip/grant).
- Readiness: Forge 2P/3P/4P/5P DIRECT, 6P SUPPORTING (bounded), 7P
  TECHNICALLY_CONFORMANT (fail-closed), mulligan TECHNICALLY_CONFORMANT
  (MULL-4 DIRECT; MULL-2 London-tuck seam → BOUNDED_NON_BLOCKING).

## Comparison (adjudicated, Gate C)

14 SAME_SEMANTICS (13 both-DIRECT + TAX-4 with run-shape-only Forge
residual); 25 ENGINE_CAPABILITY_GAP (all XMage injection-blocked rows, which
Forge executes: 22 DIRECT + MP-TURN-3/5 and ELIM-5 TC); 62 NON_COMPARABLE
(XMage exact evidence absent); 0 UNKNOWN_PENDING (no recorded Rules-visible
delta on any of the 101 rows).
