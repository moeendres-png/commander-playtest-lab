# WS232 N-Scoped Summary (S8 successor disposition)

## Workload (mechanically derived, no drift)

- Common fixture total: 135 = 72 RERUN_REQUIRED + 47 RETAINED + 16 UNKNOWN + 0 BLOCKED.
- Retained partition: 29 actual_card + 13 micro_rules + 5 replay_rng.
- N-scoped cells: 47 x {2P,3P,5P} = 141.

## Terminal disposition (N_SCOPED_DISPOSITION.json)

- PASS: 121 (each with an exact current rerun pointer + STATIC_PASS predicate).
- UNKNOWN: 20 (each with an explicit sealed cause).
- By count: 2P 40/7, 3P 40/7, 5P 41/6.

## Actual-card 29 (ACTUAL_CARD_29_MATRIX.json): 79 PASS / 8 UNKNOWN

Systemic symmetric singleton-legal Commander decks through the unmodified
Rules Core; all-seats spotlight preference among engine-authorized options;
fresh process per game; public-only logs.

- PASS bars (uniform): offer + authorized selection + engine consumption
  (arrival for permanents, graveyard resolution for sorceries/instants,
  numeric-frame consumption for X-spells, damage/token support where the
  kind requires it) + advance. Adjudicated uniform consume-level rule
  WS232-ADJ-CARD-CONSUME-LEVEL-1.0.0 for permanent chains (provenance in
  matrix `adjudication_passes`).
- UNKNOWN (8), each with 24-32 documented attempts:
  CARD_12 (2P/3P/5P): Dig selected + take-2 answered, rest-on-bottom-5
  unanswerable in-lane (fail-closed pilot bottom-domain gap,
  FINDING_PILOT_BOTTOM_GAP.md).
  CARD_22 (2P/3P): Bolt Bend redirect coincidence too rare (1 stack window
  in 64 games, fizzled).
  CARD_23 (2P/3P/5P): Makeshift Mannequin never castable (yards empty in
  goldfish; 0 offers in 96 games).

## Micro-rules 13 (MICRO_RULE_13_MATRIX.json): 27 PASS / 12 UNKNOWN

Lions games (base + anthem/static spotlight waves) + exact cited card runs.

- PASS: STACK, PRIORITY (implied by decision flow), TRIGGERS, MODES (Burn
  modal runs at all N), REPLACEMENT (command-zone choices), RULES_RANDOMNESS
  (196->784 / 294->1176 / 490->1960), STATE_BASED_ACTIONS (post-combat
  destroy chains), ZONE_CHANGES (5 movement kinds), COMBAT, CONTINUOUS
  (Captain pt elevation / Gideon 6/6 type-application / Sovereign ETB-tapped).
- UNKNOWN (12): COPY x3, CONTROL x3 (no sources in any current fixture;
  S9 decks not built); PREVENTION x3 (no source/target pair in symmetric
  Lions); LAYERS x3 (no order-sensitive pair; Elesh application documented
  as adjacent non-ordering evidence).

## Replay/RNG 5 (REPLAY_RNG_5_MATRIX.json): 15 PASS / 0 UNKNOWN

Current record + dual independent fresh-process replay at each N (Lions
tapes 360/403/507 steps; RNG growth identical to WS218 lane values).

## Predicates

47/47 STATIC_PASS (checker) + 6/6 predicate unit tests green. Behavior
discharge joined per N cell (rerun pointer or explicit UNKNOWN).

## S9 set

16 UNKNOWN rows preserved verbatim (UNKNOWN_16_PRESERVATION.json); no
silent promotion; no trigger-rich S9 deck engineering inside WS232.
