# Forge AF07 29-card matrix (ScenarioBootstrap lane, #453)

Status: measured on a local dev runner. It is not a clean-runner receipt and earns no credit.
Lane: `forge_scenario_lane` over the 29 effective 1.0.18 AF07 records, against the pinned Forge
bridge `20e3e1f7ff8e` (ScenarioBootstrap source blob `9ae04d53dba4`).

**Result: 29 / 29 `UNSUPPORTED_DIMENSION`. AF07 on Forge: NOT QUALIFIED.**

The engine built every row it could. Where it did, its readback was compared field by field (the
checkpoint column). No row reaches its obligation:

- 28 rows declare decisions the lane cannot execute. The lane answers only
  engine-authored pass, mulligan, starting-player and cost-order frames. Scripted casts, targets,
  modes, attacks and orders need the shared mid-game selector surface, which this lane must not
  rebuild.
- CARD_07 requests a stack object, which the bootstrap cannot place.

| Row | Unsupported dimensions | Checkpoint fields |
| --- | --- | --- |
| CARD_01 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_player`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 14 |
| CARD_02 | `action_cost_state`, `decision_execution.priority.semantic_action` | EXACT 9 |
| CARD_03 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_objects`, `decision_execution.target_amount.amount_assignment`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 37 |
| CARD_04 | `combat_state`, `decision_execution.declare_attacker.attacker_assignment`, `decision_execution.target.semantic_object`, `temporal_state.combat_step` | not compared |
| CARD_05 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_player`, `decision_execution.trigger_order.order`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 13, MISMATCH 1 |
| CARD_06 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_player`, `decision_execution.trigger_order.order`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 15, MISMATCH 1 |
| CARD_07 | `semantic_objects.zone:stack`, `stack_state` | EXACT 9, MISMATCH 1 |
| CARD_08 | `action_cost_state`, `combat_state`, `commander_state.prior_command_zone_cast_count`, `decision_execution.declare_attacker.attacker_assignment`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_object`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 17, MISMATCH 2 |
| CARD_09 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_objects`, `decision_execution.target_amount.amount_assignment`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 31, MISMATCH 1 |
| CARD_10 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_object`, `semantic_objects.zone:stack`, `stack_state`, `temporal_state.active_player` | not compared |
| CARD_11 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_object`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 19, MISMATCH 1 |
| CARD_12 | `action_cost_state`, `decision_execution.choose_object.order`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_objects`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 13, MISMATCH 1 |
| CARD_13 | `action_cost_state`, `decision_execution.choose_use.boolean`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_object`, `decision_execution.target.semantic_player`, `semantic_objects.zone:stack`, `stack_state`, `temporal_state.active_player` | not compared |
| CARD_14 | `action_cost_state`, `decision_execution.priority.semantic_action`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 27, MISMATCH 1 |
| CARD_15 | `action_cost_state`, `decision_execution.announce_x.integer`, `decision_execution.choose_object.semantic_objects`, `decision_execution.priority.semantic_action`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 41, MISMATCH 3 |
| CARD_16 | `decision_execution.trigger_order.order`, `semantic_objects.zone:stack`, `stack_state`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 8, MISMATCH 4 |
| CARD_17 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_player`, `temporal_state.active_player` | not compared |
| CARD_18 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_object`, `decision_execution.trigger_order.order`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 15, MISMATCH 1 |
| CARD_19 | `decision_execution.choose_object.semantic_object`, `decision_execution.priority.semantic_action` | EXACT 21 |
| CARD_20 | `decision_execution.choose_object.semantic_object`, `semantic_objects.zone:stack`, `stack_state`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 12 |
| CARD_21 | `combat_state`, `decision_execution.declare_attacker.attacker_assignment` | EXACT 13 |
| CARD_22 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_object`, `decision_execution.target.semantic_player`, `semantic_objects.zone:stack`, `stack_state`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 10, MISMATCH 4 |
| CARD_23 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_object`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 19, MISMATCH 1 |
| CARD_24 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_player`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 15, MISMATCH 1 |
| CARD_25 | `combat_state`, `decision_execution.declare_attacker.attacker_assignment`, `decision_execution.declare_blocker.blocker_assignment`, `temporal_state.combat_step` | not compared |
| CARD_26 | `action_cost_state`, `decision_execution.choose_mode.semantic_mode_key`, `decision_execution.priority.semantic_action`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 19, MISMATCH 1 |
| CARD_27 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_objects`, `decision_execution.target.semantic_player`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 13, MISMATCH 1 |
| CARD_28 | `action_cost_state`, `decision_execution.choose_object.semantic_object`, `decision_execution.priority.semantic_action`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 10, MISMATCH 10 |
| CARD_29 | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_object`, `decision_execution.target.semantic_objects`, `temporal_checkpoint.exact_hand_after_draw` | EXACT 24, MISMATCH 2 |

| Dimension class | Rows |
| --- | --- |
| `decision_execution` | 28 |
| `action_cost_state` | 22 |
| `temporal_checkpoint.exact_hand_after_draw` | 20 |
| `semantic_objects.zone:stack` | 6 |
| `stack_state` | 6 |
| `combat_state` | 4 |
| `temporal_state.active_player` | 3 |
| `temporal_state.combat_step` | 2 |
| `commander_state.prior_command_zone_cast_count` | 1 |

Next on Forge, in order: the shared mid-game selector surface (decision execution), then stack and
causal entry, then the action-cost state. None of these can be built inside this lane.
