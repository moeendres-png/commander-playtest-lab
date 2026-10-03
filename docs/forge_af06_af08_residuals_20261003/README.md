# #459 Forge AF06/AF08 residuals: first missing mechanism per row

Workstream `FORGE-AF06-AF08-RESIDUAL-CLOSURE-20261003` (parent #255). Forge is measured on
the same micro-rules (`MICRO_*`), pilot-decision (`PILOT_*`) and multiplayer/Commander
(`WS05-*`) rows as XMage. Forge itself is not modified.

## Baseline (re-derived, not inherited)
PB-03 on main `286f78d0` (epoch `18f0097373e6-8f04fe18d6c9`), Forge Rules Core
`bb0a740d`, bridge `20e3e1f7`:
- AF06 UNKNOWN, 40 blocking (BLOCKED) rows;
- AF08 UNKNOWN, 29 non-PASS WS05 rows;
- 63 of the 70 in-scope rows are not PASS.

Most of those rows carried a generic reason ("no current-boundary execution seam", or
"no current-boundary execution path for this obligation in this run").

## What this workstream changes
1. **Exact reasons.** `current_boundary/forge_residuals.py` classifies every in-scope
   row by its first missing mechanism. The runner gives each Forge row that reason and
   keeps its outcome. No row is executed, and nothing is credited, by classification.
2. **WS05-CMD-START-3 executes.** The Forge scenario lane now observes
   `starting_player` / `first_turn_draw` from the engine's own counts across the
   starting player's turn-1 draw step (see below). It earns credit only through the
   lane's runner-bound receipt in PB-03.

## How a row is classified
A row passes through three stages. Every missing mechanism is recorded in pipeline order.
The row's class is that of the first provider gap, if there is any, because no Lab work
alone closes such a row; otherwise it is the first Lab gap:

1. **Construction**, from the Forge scenario lane's own model
   (`forge_scenario_lane.model_requested_state`):
   - a dimension no provider field or engine action can produce is a
     `PROVIDER_ADAPTER_GAP` (predetermined draws, face-down state, knowledge state);
   - a dimension the engine causes on its own decision frames (a cast, a payment, an
     attack, a later turn) is a `LAB_EXECUTION_GAP`;
   - a requested field the readback cannot show is a `PROVIDER_ADAPTER_GAP` of
     observation (owner, attachment, object identity in a public zone).

2. **Execution**: each scripted decision family maps to the pinned bridge's frame kinds
   that carry it (`_DECISION_FAMILIES`), and is a `LAB_EXECUTION_GAP` while the lane has
   no selector for it. The exception is a **mulligan**: the bridge frames keep or
   mulligan, but taking one calls `tuckCardsViaMulligan`, which the pinned bridge always
   rejects. That makes it a `PROVIDER_ADAPTER_GAP`.
3. **Observation**: each required obligation token is observable through
   - the **state readback** (life, loss, zones, P/T, stack, command zone, commander damage
     and cast counts, turn position);
   - the engine's own **decision frames** (the decision tape); or
   - only an **engine event stream**. The pinned bridge exports no event log
     (`EVENT_LOG_UNSUPPORTED`), so an event-only token is a `PROVIDER_ADAPTER_GAP`.

   A readback or frame token whose observation contract the lane does not implement is a
   `LAB_EXECUTION_GAP`.

An unmapped dimension or token raises instead of defaulting to a class.

## Result
| Class | Rows (of 70) |
|---|---|
| `LAB_EXECUTION_GAP` | 46 |
| `PROVIDER_ADAPTER_GAP` | 17 |
| `SCENARIO_LANE_EXECUTABLE` | 7 (six already PASS in the baseline epoch, plus WS05-CMD-START-3) |

The matrix describes the scenario lane only. WS05-CMD-START-2 passes in the baseline on
the generic lane's own route, and the scenario lane has no contract for its
`first_turn_draw_step_skipped` token, so it is counted under `LAB_EXECUTION_GAP` here. Its
receipt, not this matrix, decides its row.

The 17 provider gaps break down as follows:
- 11 rows need an event log;
- three need a mulligan (PILOT_MULLIGAN, WS05-CMD-MULL-2 and WS05-CMD-MULL-4);
- one needs predetermined draws (MICRO_RULES_RANDOMNESS);
- five need a readback of owner, attachment, a revealed zone, the library, or object
  identity in a public zone.

Some rows have more than one provider gap. Each row's matrix entry lists every
mechanism.

**The larger blocker is Lab-side.** The Forge bridge projects the engine's choices as
decision frames, among them:
- `ATTACK_DECLARATION` and `BLOCK_DECLARATION`;
- `TARGETING` and `MODE_SUBSET`;
- `BOOLEAN` and `ANNOUNCE`;
- `AMOUNT_DISTRIBUTION_SELECTION` and `ORDER`;
- `REPLACEMENT_EFFECT`;
- the mana and cost frames.

The Forge scenario lane answers only priority passes, mulligans (keep), the starting
player and the cost-part order. A shared, engine-authored selector surface for the Forge
lane is the next mechanism. It is the Forge counterpart of the XMage mid-game executor.
Whether each scripted selector maps one-to-one onto a Forge frame is part of that work.

## Per-row matrix
`FORGE_RESIDUAL_MATRIX.json` is written by `scripts/run_forge_residual_census.py` and
bound to the effective contract (`contract_id`, `canonical_bundle_digest`). It lists
every mechanism of every row; the table shows the first one.

| Row | Class | First missing mechanism | Event-only tokens |
|---|---|---|---|
| MICRO_COMBAT | PROVIDER_ADAPTER_GAP | observation: `event_log` | `combat_damage:attacker_to_blocker:2`, `combat_damage:blocker_to_attacker:2`, `state_based_actions` |
| MICRO_CONTINUOUS_EFFECTS | LAB_EXECUTION_GAP | construction: `temporal_checkpoint.exact_hand_after_draw` | — |
| MICRO_CONTROL | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| MICRO_COPY | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| MICRO_COSTS | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| MICRO_LAYERS | PROVIDER_ADAPTER_GAP | observation: `event_log` | `layer6_remove_abilities`, `layer7b_set_pt:1/1`, `layer7c_modify_pt:+1/+1` |
| MICRO_MANA_PAYMENT | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| MICRO_MODES | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| MICRO_PREVENTION | PROVIDER_ADAPTER_GAP | observation: `event_log` | `combat_damage_would_be:P2:2`, `prevention_applied`, `combat_damage_prevented:P2:2` |
| MICRO_PRIORITY | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| MICRO_REPLACEMENT | PROVIDER_ADAPTER_GAP | observation: `event_log` | `damage_would_be:P2:3`, `replacement_effect:double` |
| MICRO_RULES_RANDOMNESS | PROVIDER_ADAPTER_GAP | construction: `rules_randomness.predetermined_semantic_draws` | `rules_rng:coin_flip:HEADS`, `extra_turn_created:P1` |
| MICRO_STACK | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| MICRO_STATE_BASED_ACTIONS | PROVIDER_ADAPTER_GAP | observation: `event_log` | `state_based_actions` |
| MICRO_TARGETS | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| MICRO_TRIGGERS | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| MICRO_ZONE_CHANGES | PROVIDER_ADAPTER_GAP | observation: `event_log` | `new_object_incarnation:line:micro-bolt` |
| PILOT_ANNOUNCE_X | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| PILOT_CHOICE | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| PILOT_CHOOSE_ABILITY | LAB_EXECUTION_GAP | execution: `decision_execution.choose_ability.semantic_ability_key` | — |
| PILOT_CHOOSE_MODE | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| PILOT_CHOOSE_OBJECT | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| PILOT_CHOOSE_USE | PROVIDER_ADAPTER_GAP | checkpoint_readback: `semantic_objects.zone:library` | — |
| PILOT_DECLARE_ATTACKER | LAB_EXECUTION_GAP | construction: `combat_state` | — |
| PILOT_DECLARE_BLOCKER | LAB_EXECUTION_GAP | construction: `combat_state` | — |
| PILOT_MANA_PAYMENT | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| PILOT_MULLIGAN | PROVIDER_ADAPTER_GAP | execution: `decision_execution.mulligan.semantic_action` | — |
| PILOT_MULTI_AMOUNT | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| PILOT_PILE | PROVIDER_ADAPTER_GAP | checkpoint_readback: `semantic_objects.zone:revealed` | — |
| PILOT_PRIORITY | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| PILOT_REPLACEMENT_EFFECT | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| PILOT_TARGET | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| PILOT_TARGET_AMOUNT | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| PILOT_TRIGGER_ORDER | LAB_EXECUTION_GAP | execution: `decision_execution.trigger_order.order` | — |
| WS05-CMD-DMG-CONTROL | LAB_EXECUTION_GAP | construction: `combat_state` | — |
| WS05-CMD-DMG-SAME-21 | LAB_EXECUTION_GAP | construction: `combat_state` | — |
| WS05-CMD-DMG-SPLIT (PASS in epoch `18f0097373e6`) | SCENARIO_LANE_EXECUTABLE | — | — |
| WS05-CMD-ELIM-4 | LAB_EXECUTION_GAP | construction: `combat_state` | — |
| WS05-CMD-MULL-2 | PROVIDER_ADAPTER_GAP | execution: `decision_execution.mulligan.semantic_action` | — |
| WS05-CMD-MULL-4 | PROVIDER_ADAPTER_GAP | execution: `decision_execution.mulligan.semantic_action` | — |
| WS05-CMD-PARTNER-DMG (PASS in epoch `18f0097373e6`) | SCENARIO_LANE_EXECUTABLE | — | — |
| WS05-CMD-PARTNER-TAX | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| WS05-CMD-PARTNER-ZONE (PASS in epoch `18f0097373e6`) | SCENARIO_LANE_EXECUTABLE | — | — |
| WS05-CMD-START-2 (PASS in epoch `18f0097373e6`) | LAB_EXECUTION_GAP | observation: `observation_contract` | — |
| WS05-CMD-START-3 | SCENARIO_LANE_EXECUTABLE | — | — |
| WS05-CMD-TAX-2 | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| WS05-CMD-TAX-4 | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| WS05-CMD-ZONE-EXILE-NO | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| WS05-CMD-ZONE-EXILE-YES | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| WS05-CMD-ZONE-GY-NO | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| WS05-CMD-ZONE-GY-YES | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| WS05-CMD-ZONE-HAND-NO | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| WS05-CMD-ZONE-HAND-YES | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| WS05-CMD-ZONE-LIB-NO | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| WS05-CMD-ZONE-LIB-YES | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| WS05-MP-BLOCK-4 | LAB_EXECUTION_GAP | construction: `combat_state` | — |
| WS05-MP-COMBAT-4 | LAB_EXECUTION_GAP | construction: `combat_state` | — |
| WS05-MP-COMBAT-5 | LAB_EXECUTION_GAP | construction: `combat_state` | — |
| WS05-MP-ELIM-5 (PASS in epoch `18f0097373e6`) | SCENARIO_LANE_EXECUTABLE | — | — |
| WS05-MP-ELIM-CONTROL-3 | PROVIDER_ADAPTER_GAP | checkpoint_readback: `owner_controller_divergence` | — |
| WS05-MP-ELIM-OWNED-3 (PASS in epoch `18f0097373e6`) | SCENARIO_LANE_EXECUTABLE | — | — |
| WS05-MP-ELIM-PRIO-3 (PASS in epoch `18f0097373e6`) | SCENARIO_LANE_EXECUTABLE | — | — |
| WS05-MP-ELIM-STACK-3 | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| WS05-MP-ELIM-TURN-3 | LAB_EXECUTION_GAP | construction: `temporal_state.active_player` | — |
| WS05-MP-PRIO-3 | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| WS05-MP-PRIO-5 | LAB_EXECUTION_GAP | construction: `stack_state` | — |
| WS05-MP-TRIG-3 | PROVIDER_ADAPTER_GAP | observation: `event_log` | `simultaneous_trigger_event` |
| WS05-MP-TRIG-5 | PROVIDER_ADAPTER_GAP | observation: `event_log` | `simultaneous_trigger_event` |
| WS05-MP-TURN-3 | PROVIDER_ADAPTER_GAP | checkpoint_readback: `semantic_objects.zone:graveyard` | `extra_turn_created:P2`, `extra_turn_created:P3` |
| WS05-MP-TURN-5 | PROVIDER_ADAPTER_GAP | checkpoint_readback: `semantic_objects.zone:graveyard` | `extra_turn_created:P2`, `extra_turn_created:P3` |

## WS05-CMD-START-3: first-turn draw from the engine's own counts
After each priority pass the lane records the engine's turn position and each player's
hand and library counts. It records counts only, never names.

The obligation holds when, across the starting player's turn-1 draw step (the last
snapshot before it against the first one in it), all of these hold:
- the starter's hand rises by exactly one;
- the starter's library falls by exactly one;
- no other player's counts change;
- the engine's active player is the requested starter.

Local run against the pinned bridge: P1 7→8 in hand and 92→91 in library; P2 and P3
unchanged.

**Basis of the starter.** The starting player is not an engine observation. The engine
picks a chooser (P2 in the local run) and offers it every seat, and the lane answers with
the record's requested active player (`requested_starting_seat`, an engine-offered option).
The verdict requires that recorded selection, names its basis
(`LAB_SELECTED_ENGINE_OFFERED`) and checks only that the engine then started that seat's
turn. The draw half (CR 103.8) is the engine-observed fact. Whether a selection derived
from the requested state counts as a scripted response when the record's decision script
is empty is put to #255 as a flag; the receipt names the basis either way.

Wrong-reason controls, run on the engine locally and as unit tests:
- the wrong value (`first_turn_draw:false`) is refused;
- the wrong starter is refused;
- a hand change that did not come from the library is refused;
- a change in another player's counts is refused;
- the right final hand size without a draw-step change is refused;
- a later turn's draw step is refused;
- a missing snapshot on either side is refused.

In a two-player game Forge offers no priority on both sides of the draw step, and the
check fails closed instead of guessing. WS05-CMD-START-2 passes on its own route.

## Findings for #255
1. **Hand comparison.** The Forge lane compares a requested hand by exact equality. The
   engine's natural turn-1 draw adds a card before a main-phase checkpoint, so every row
   with an explicit hand (`temporal_checkpoint.exact_hand_after_draw`) is unconstructible
   on Forge today. XMage uses presence semantics: requested cards present, extra natural
   cards allowed. A provider-neutral rule would require the requested cards plus the
   engine-observed draw count. This is Lab work.
2. **MICRO_CONTINUOUS_EFFECTS** stays construction-dependent. Forge's bootstrap gives P1
   six cards at the checkpoint, so the 1.0.20 obligation's 13/13 P/T is XMage's
   construction. This repeats flag 1 of the #456 comment on #255.
3. **Event-only obligations**, 11 rows: layers, prevention, replacement, state-based
   actions, simultaneous triggers, CR 400.7 new objects, coin flips and queued extra
   turns. They cannot be observed on Forge without an engine event stream. That needs a
   separately authorized Forge bridge issue.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`
