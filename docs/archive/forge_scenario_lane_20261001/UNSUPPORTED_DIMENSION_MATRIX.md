# Unsupported and unobservable dimension matrix

Machine-readable authority: `receipts/STRUCTURAL_CENSUS.json` (per-row findings)
and `receipts/EXECUTION_RECEIPT.json` (runtime probes for attempted rows).

Dimensions follow the deterministic classifier in
`forge_scenario_lane.model_requested_state`. A dimension is:
* `UNSUPPORTED` — the pinned bootstrap cannot represent it, so construction is
  impossible and the row fails closed;
* `UNOBSERVABLE` — construction may be possible, but the generic readback cannot
  prove equivalence, so the row cannot be credited.

## Dimension frequency over the effective denominator (107 rows)

| Dimension | Rows | Class |
| --- | --- | --- |
| `temporal_checkpoint.exact_hand_after_draw` (3P+, explicit hand at a post-draw checkpoint) | 49 | UNSUPPORTED |
| `action_cost_state` | 32 | UNSUPPORTED |
| `decision_execution.priority.semantic_action` (cast selection not implemented in this lane) | 32 | UNSUPPORTED |
| `semantic_objects.zone:library` | 27 | UNOBSERVABLE |
| `semantic_objects.zone:stack` | 24 | UNSUPPORTED |
| `stack_state` | 24 | UNSUPPORTED |
| `semantic_objects.controlled_since_turn_began` | 23 | UNOBSERVABLE |
| `semantic_objects.zone:exile` | 20 | UNOBSERVABLE |
| `semantic_objects.face_down` | 20 | UNSUPPORTED |
| `combat_state` | 12 | UNSUPPORTED |
| `knowledge_state` (material permissions) | 11 | UNSUPPORTED |
| `temporal_state.combat_step` | 8 | UNSUPPORTED |
| `decision_execution.choose_mode.semantic_mode_key` | 7 | UNSUPPORTED |
| `decision_execution.mulligan.semantic_action` | 7 | UNSUPPORTED |
| `temporal_state.turn_number` (turn ≠ 1) | 7 | UNSUPPORTED |
| `decision_execution.replacement_effect.boolean` | 5 | UNSUPPORTED |
| `decision_execution.target.semantic_player` | 5 | UNSUPPORTED |
| `decision_execution.choice.boolean` | 4 | UNSUPPORTED |
| `owner_controller_divergence` | 3 | UNOBSERVABLE |
| `commander_state.prior_command_zone_cast_count` | 3 | UNSUPPORTED |
| `decision_execution.declare_attacker.attacker_assignment` | 3 | UNSUPPORTED |
| `decision_execution.mana_payment.mana_payment` | 3 | UNSUPPORTED |
| `temporal_state.active_player` (not the starting player) | 3 | UNSUPPORTED |
| `semantic_objects.attached_to` | 2 | UNOBSERVABLE |
| `semantic_objects.zone:graveyard` | 2 | UNOBSERVABLE |
| `decision_execution.target.semantic_object` | 2 | UNSUPPORTED |
| `decision_execution.target.semantic_stack_object` | 2 | UNSUPPORTED |
| `decision_execution.declare_blocker.blocker_assignment` | 2 | UNSUPPORTED |
| other decision families (announce_x, choose_ability, choose_object, choose_use, multi_amount, pile, target_amount, trigger_order, fail_closed_probe) | 1–2 each | UNSUPPORTED |
| `rules_randomness.predetermined_semantic_draws` | 1 | UNSUPPORTED |
| `semantic_objects.zone:revealed` | 1 | UNOBSERVABLE |

## Runtime probes for unsupported dimensions

* **Enforced rejections** (stack, decision injection): the exact requested field
  is sent inside a neutral state and the engine is required to reject the create.
  Result per attempt: `game_creation_failed` with the exact rejection message.
  Recorded per row (`scenario_parse.rejection_probes`) and once globally in
  `LIVE_REJECTION_PROBE.json`.
* **Silently ignored dimensions** (combat state, cost state, temporal state,
  knowledge state): the supported subset plus the unknown fields is sent; the
  engine accepts the create and the first observable checkpoint demonstrably
  cannot contain the dimension. The lane classifies it itself; engine
  acceptance is never treated as construction.
* **Unreachable temporal checkpoints**: turn ≠ 1, a non-starting active player,
  or a combat step are refused before any drive, because the hook runs at the
  first-turn untap and bootstrap-placed attackers are summoning-sick.

## Why exact hand checkpoints are a major structural blocker

For 3P+ games the starting player draws during the first turn. A fixture whose
requested explicit hand is stated at a `precombat_main` checkpoint cannot be
satisfied by a scripted hand alone: the natural draw adds a card, and the
bootstrap has no library-order field. This run proved it live on `MICRO_MODES`
(field-level `hands.p1` mismatch at the requested checkpoint). Any future
consumer of this seam needs either a fixture convention that states the hand at
the bootstrap checkpoint, or an engine-side (Forge) supported way to hold
library order / suppress the draw. The lane does not fabricate either.
