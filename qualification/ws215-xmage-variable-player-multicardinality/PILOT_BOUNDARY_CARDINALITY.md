# WS215 PILOT_BOUNDARY_CARDINALITY — PASS (no fallback introduced)

Cardinality changes impact-adjudicated against the canonical
pilot-boundary families; the production decision surface is unchanged in
kind and extended in count only:

- All 17 supported decision classes flow identically for N = 2..5
  (priority, target, choose_object, target_amount, mulligan, choose_use,
  choice, pile, mana_payment, announce_x, amount, multi_amount,
  replacement_effect, trigger_order, mode, declare_attacker,
  declare_blocker). Unknown classes still fail closed
  (`unsupported discretionary decision class` — unit-tested).
- N-coverage proven without JVM: policy accepts 2..5 with exact
  1..N seats, rejects 1/6 and coverage gaps; `pod_size = N`,
  `opponents_to_act_before_next_turn = N-1`; per-count priority answers
  execute (`tests/unit/test_xmage_variable_player.py`, 32 tests PASS).
- Behavioral deltas from WS213 (both directions audited, no fallback):
  (a) target tiebreak `(score, card_name, action_id)` — stable-content
  ordering replaces UUID order (determinism repair, TD01);
  (b) mana liveness guard — pool pays only generic-only costs or exact
  colored matches, else abilities/cancel, else fail-closed (TD02).
  Neither introduces first-option, random-option, default yes/no,
  internal AI, GUI default, silent skip, parent fallback,
  requested-option filtering, or fabricated actions; unsupported paths
  still fail closed.
- Java WS204 generic battery rerun: **117/117 PASS** (105 preserved +
  WS215 additions), including projection/submission negatives.
- Per-count runtime: priority/target/choice/mana/mulligan/attack/block
  classes all answered legally in the N-player lifecycles with zero
  fallback markers (`fallback_used` false everywhere by construction).

`WS204_GENERIC_ACTION_BATTERY` (105/105) retained and extended to 117.
No behavior credit claimed (`GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0`).

Machine companion: `PILOT_BOUNDARY_CARDINALITY.json`.
