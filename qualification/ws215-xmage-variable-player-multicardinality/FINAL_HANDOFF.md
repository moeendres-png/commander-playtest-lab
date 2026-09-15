# WS215 FINAL_HANDOFF — XMage Variable-Player Full-Game Multicardinality

## Source Lock

- Lab `moeendres-png/commander-playtest-lab`,
  `ws215/xmage-variable-player-multicardinality-20260915`, audit base
  WS213 `592f23c9` (tree `33e8cef4`).
- Production XMage `db134b9737` (tree `4c7cae47`); WS214 `c044d40f6`
  TEST-ONLY.
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`.
  `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Work Completed

1. Generalized the production full-game orchestration from exactly-4P to
   authoritative 2–5P Commander Free-for-All under one cardinality
   contract (Java session/bridge + Python runner/policy/scenario/batch +
   lane min/max capabilities), all invalid cardinalities fail-closed
   before partial execution (0/1/6+, mismatches, seat gaps, bad seats).
2. Qualified 2P/3P/4P/5P lifecycles in fresh JVMs with same-seed twins
   (all match) and distinct-seed controls (all diverge), seed binding
   preserved per count, hidden-info re-proven per count (9985 oracle
   frames, 0 violations).
3. Exercised multiplayer/Commander semantics natively: 3P/5P priority
   rings, 4P/5P multi-defender combat + blocker partition, 3P/5P
   concession with CR800.4 owned/priority/active/5P cleanup, Commander
   tax recasts, GY zone choices both branches, partner zone, free + paid
   London mulligan, uniform FFA first-draw, 2P natural terminal.
4. Repaired two genuine hazards found by probing (no credit claimed):
   deterministic harness/target selection (TD01) and the mana-payment
   livelock guard (TD02, production + unit tests).
5. Impact-adjudicated all 135 canonical fixtures (72 rerun PASS,
   47 retained with rationale, 16 honest UNKNOWNs); replay PARTIAL
   retained; FULL107 NOT_RUN; behavior credit 0; 6P NOT_SUPPORTED
   with exact fail-closed evidence.

## New Findings

- The engine offers the CR 103.2 starting-player choice to the
  seed-chosen seat; harness UUID-order answers picked process-random
  starters (twin divergence). Fixed by stable-content selection; the
  orchestration seat selects the *chooser*, the native choice selects
  the starter (TD04).
- The engine over-offers unpayable casts (e.g. Silence with no white
  source); spending wrong-color pool mana loops the payment natively.
  Fixed by the liveness guard (TD02); failed activations remain
  fail-closed terminal (correct production behavior, not silent skip).
- London paid-bottom arrives as hand-target choices (not choose_object).
- `casts_from_command` watcher confirms tax recasts (casts = 2);
  commander damage ledger live (peak single-commander total 8 in
  windows; 21 threshold unreached → UNKNOWN).
- APNAP orderings, extra-turn insertions, 21/split/control damage,
  partner tax/damage, exile/hand/library zone branches, and CR800.4
  control-effects did not arise in bounded windows → honest UNKNOWNs
  with bounded successors (never PASS by assumption).

## Changes

- `engine-bridge`: session MIN/MAX_PLAYERS + per-game count, bridge
  range validation + min/max lane, rewritten player-count gates, updated
  lane contract test, new 12-test variable-player lifecycle class.
- `src/`: variable-cardinality runner/policy/scenario/batch, mana
  liveness guard, target tiebreak, contract-artifact invariant.
- `tests/`: new 32-test variable-player file; handoff contract test
  updated to 2–5P.
- `qualification/ws215-xmage-variable-player-multicardinality/`:
  authority/contract/impact docs, probe + driver, Lions technical deck,
  24-run sealed matrix + observations, 30 evidence files, artifact seal.

## Tests / Evidence

- Bridge 121/121; Python impacted 62 + handoff update; ruff PASS;
  broader unit 640 passed with 5 + 40 pre-existing environmental
  (WS213-class, none WS215-caused).
- Fresh-process matrix 24/24 clean; 8/8 twin MATCH; 8/8 controls
  DIVERGE; oracle 9985/0.
- Classifications: lifecycle/twin/rng/hidden/combat/tax/zone/mulligan/
  start-draw/concede evidence is RUNTIME_VERIFIED; unknowns are UNKNOWN
  (never PASS); retained fixtures are CODE_DERIVED + adjudication
  rationale (never RUNTIME_VERIFIED by inheritance).

## PASS / FAIL / UNKNOWN

- PASS: 2P, 3P, 4P (fresh regression), 5P; priority 3P/5P; multi-
  defender 4P/5P + partition; CR800.4 owned/stack-vacuous/priority/
  active/5P; tax; GY zone yes/no; partner zone; mulligan; start-draw;
  hidden-info cardinality; seed binding cardinality; pilot boundary
  cardinality; 4P regression.
- UNKNOWN (fresh, with cause): APNAP 3P/5P; extra-turn 3P/5P;
  CR800.4-control; exile/hand/library zone branches; 21/split/control
  damage; partner tax/damage.
- NOT_SUPPORTED (evidenced): 6P. NOT_RUN: FULL107. PARTIAL: replay.

## Remaining Blockers

None in-scope: all WS215 gates terminal. Bounded successors only:
APNAP/extra-turn/threshold/partner-tax-damage evidence (trigger-rich or
longer-window runs), replay/checkpoint contract, FULL107 matrix,
remaining setup closure, 6P only after architecture review.

## Outputs

- `qualification/ws215-xmage-variable-player-multicardinality/`
  (30 evidence files + driver/probe/deck + sealed runs + artifact
  index).
- Local commits on
  `ws215/xmage-variable-player-multicardinality-20260915` (no push yet).

## Dependencies Unblocked

- Variable-player session is production-ready for 2–5P qualification
  consumers; replay/FULL107/setup successors have exact bounded specs;
  no engine change required.

## Exact Next Action

- Coordinator: review this handoff + sealed evidence; publish via
  canonical safe_push (dry-run first; no raw push/PR/merge); then
  charter bounded successors as directed. Do not start Semantic Replay,
  WS209, or any successor from the WS215 session.

## Terminal fields

WS215_XMAGE_VARIABLE_PLAYER_MULTICARDINALITY = COMPLETE (2P–5P qualified)
PLAYER_COUNT_2P = PASS
PLAYER_COUNT_3P = PASS
PLAYER_COUNT_4P = PASS (fresh regression)
PLAYER_COUNT_5P = PASS
PLAYER_COUNT_6P = NOT_SUPPORTED
MIN_PLAYERS_CAPABILITY = 2
MAX_PLAYERS_CAPABILITY = 5
PRIORITY_3P = PASS
PRIORITY_5P = PASS
APNAP_3P = UNKNOWN
APNAP_5P = UNKNOWN
MULTI_DEFENDER_4P = PASS
MULTI_DEFENDER_5P = PASS
EXTRA_TURN_3P = UNKNOWN
EXTRA_TURN_5P = UNKNOWN
CR8004_OWNED_OBJECTS = PASS
CR8004_CONTROL_EFFECTS = UNKNOWN
CR8004_STACK = PASS (vacuous-documented)
CR8004_PRIORITY_HOLDER = PASS
CR8004_ACTIVE_PLAYER = PASS
CR8004_5P_RECOMPUTATION = PASS
COMMANDER_TAX = PASS
COMMANDER_ZONE_CHOICES = PARTIAL (GY PASS; exile/hand/library UNKNOWN)
COMMANDER_DAMAGE = UNKNOWN (mechanism observed; thresholds unreached)
COMMANDER_PARTNER = PARTIAL (zone PASS; tax/damage UNKNOWN)
COMMANDER_MULLIGAN = PASS
COMMANDER_START_DRAW = PASS
HIDDEN_INFORMATION_CARDINALITY = PASS
RULES_SEED_BINDING_CARDINALITY = PASS
PER_COUNT_TWINS = PASS (8/8 match, fresh processes)
COMMON_FIXTURE_DISPOSITION_COUNTS = 72/47/0/16
SEMANTIC_REPLAY_STATUS = PARTIAL
GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0
FULL107 = NOT_RUN
RAW_GIT_PUSH_USED = NO
ARCHITECTURE_FREEZE = NOT_CLAIMED
PRODUCTION_PROVIDER = NOT_SELECTED
