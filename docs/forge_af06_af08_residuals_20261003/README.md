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
2. **WS05-CMD-START-3 is not credited: CONTRACT_AUTHORITY_GAP (review P1, adjudicated).**
   The lane can observe `first_turn_draw` from the engine's own counts, but the
   starting player is a player's choice (CR 103.1). The effective record scripts no
   starting-player response, and choosing the starter from the requested end state would
   satisfy the obligation by construction (requested-option selection). The lane
   therefore refuses every row whose obligation names a starting player without a
   scripted `starting_player` decision. The verdict also requires the authorized basis
   `FIXTURE_DECISION_SCRIPT`; `LAB_SELECTED_ENGINE_OFFERED` earns nothing. Closing the
   gap needs a Coordinator-adjudicated contract erratum that scripts the decision.
3. **Six commander zone rows execute causally (#520).** WS05-CMD-ZONE-{GY,EXILE,HAND}-
   {YES,NO} ask for an opponent's spell on the stack aimed at P1's commander. The
   bootstrap cannot place a stack object, so the lane's causal stack route
   (`current_boundary/forge_causal_route.py`) puts the spell in its controller's hand and
   the row's declared fuel (the same `CAUSAL_ROWS` declaration XMage uses) on the
   battlefield, then has the controller cast, target and pay on the engine's own frames
   through the shared fail-closed selector (`scripted_selection.py`). The owner answers
   the engine's COMMANDER_MOVE (graveyard, exile; CR 903.9a) or REPLACEMENT_CONFIRM
   (hand; CR 903.9b) frame as scripted, and the lane judges `commander_zone_event` /
   `commander_choice` from the owner's own readback before the answer and after the stack
   settles. The library rows stay a gap: the readback never shows library contents.

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
Updated for contract 1.0.21 (#441: the TURN-3/5, PILOT_PILE, PILOT_CHOOSE_USE,
NEGATIVE_DEFAULT_YES_NO, MULL-2/4 and MICRO_LAYERS errata); the matrix is regenerated from
the effective contract.

| Class | Rows (of 70) |
|---|---|
| `LAB_EXECUTION_GAP` | 40 |
| `PROVIDER_ADAPTER_GAP` | 16 |
| `SCENARIO_LANE_EXECUTABLE` | 12 (six already PASS in the baseline epoch, and the six causal commander zone rows) |
| `CONTRACT_AUTHORITY_GAP` | 2 (WS05-CMD-START-2, WS05-CMD-START-3: unscripted starting player) |

The matrix describes the scenario lane only. WS05-CMD-START-2 passes in the baseline on
the generic lane's own route; in the scenario lane it is now a `CONTRACT_AUTHORITY_GAP`
for the same unscripted starting player. Whether the generic route's starter selection
(`game_driver.STARTING_PLAYER_POLICY`, default seat `p1`) has contract authority is an
open impact question for the #441 reassembly; see Findings.

The 16 provider gaps break down as follows:
- 10 rows need an event log (MICRO_LAYERS no longer does: its layer tokens are
  characteristic readbacks, CR 613);
- three need a mulligan (PILOT_MULLIGAN, WS05-CMD-MULL-2 and WS05-CMD-MULL-4), and
  WS05-CMD-MULL-2 also the London bottom selection;
- one needs predetermined draws (MICRO_RULES_RANDOMNESS);
- three need a readback of the library (PILOT_CHOOSE_USE, PILOT_PILE) or of owner and
  attachment (WS05-MP-ELIM-CONTROL-3).

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

The Forge scenario lane answers priority passes, mulligans (keep), the starting player
and the cost-part order itself. The shared fail-closed selector (`scripted_selection.py`,
#459 phase 2) adds casts, player and object targets, declared mana sources and yes/no
answers, and the causal stack route uses it for the six commander zone rows above. Every
other stack row still needs either a terminal the lane can judge, a mode or choice-key
selector, or several spells on the stack; the 13 rows whose first gap is `stack_state` and
the 14 whose first gap is `action_cost_state` are that next work (counts as of
contract 1.0.21).

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
| MICRO_LAYERS | LAB_EXECUTION_GAP | observation: `observation_contract` | — |
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
| PILOT_PILE | PROVIDER_ADAPTER_GAP | checkpoint_readback: `semantic_objects.zone:library` | — |
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
| WS05-CMD-START-2 (PASS in epoch `18f0097373e6`, generic route; authority to re-check) | CONTRACT_AUTHORITY_GAP | execution: `decision_execution.starting_player.unscripted` | — |
| WS05-CMD-START-3 | CONTRACT_AUTHORITY_GAP | execution: `decision_execution.starting_player.unscripted` | — |
| WS05-CMD-TAX-2 | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| WS05-CMD-TAX-4 | LAB_EXECUTION_GAP | construction: `action_cost_state` | — |
| WS05-CMD-ZONE-EXILE-NO | SCENARIO_LANE_EXECUTABLE | — | — |
| WS05-CMD-ZONE-EXILE-YES | SCENARIO_LANE_EXECUTABLE | — | — |
| WS05-CMD-ZONE-GY-NO | SCENARIO_LANE_EXECUTABLE | — | — |
| WS05-CMD-ZONE-GY-YES | SCENARIO_LANE_EXECUTABLE | — | — |
| WS05-CMD-ZONE-HAND-NO | SCENARIO_LANE_EXECUTABLE | — | — |
| WS05-CMD-ZONE-HAND-YES | SCENARIO_LANE_EXECUTABLE | — | — |
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
| WS05-MP-TURN-3 | PROVIDER_ADAPTER_GAP | observation: `event_log` | `extra_turn_created:P2`, `extra_turn_created:P3` |
| WS05-MP-TURN-5 | PROVIDER_ADAPTER_GAP | observation: `event_log` | `extra_turn_created:P2`, `extra_turn_created:P3` |

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

**Basis of the starter (adjudicated: no authority).** The starting player is not an
engine observation. The engine picks a chooser (P2 in the local run) and offers it every
seat. Answering with the record's requested active player is requested-option selection,
because the decision script is empty. So the row is refused (`decision_execution.
starting_player.unscripted`), and the verdict credits a starter only on the
`FIXTURE_DECISION_SCRIPT` basis (red control `test_a_lab_selected_starter_earns_no_credit`).
The draw-count verdict below remains implemented for a future erratum that scripts the
choice.

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
1. **Hand comparison (review P2, adjudicated).** The obligation
   `temporal_checkpoint.exact_hand_after_draw` is exact, and this workstream has no
   authority to weaken it. The engine's natural turn-1 draw adds a card the lane can
   neither control nor prove, so the 17 affected rows stay `LAB_EXECUTION_GAP`. The open
   mechanism is controlling or proving the drawn card, not presence semantics.
   **Impact flag for #441:** XMage was reported to compare with presence semantics
   (requested cards present, extra natural cards allowed). Any XMage credit that rests
   on that weakened comparison must be impact-adjudicated before reuse.
2. **Starting player (adjudicated).** A starting-player obligation without a scripted
   response is a `CONTRACT_AUTHORITY_GAP`. **Impact flag for #441:** WS05-CMD-START-2's
   baseline PASS on the generic route must be re-checked for the authority of its starter
   selection (`fixture_scripted_seat`, default `p1`).
3. **MICRO_CONTINUOUS_EFFECTS** stays construction-dependent. Forge's bootstrap gives P1
   six cards at the checkpoint, so the 1.0.20 obligation's 13/13 P/T is XMage's
   construction. This repeats flag 1 of the #456 comment on #255.
4. **Event-only obligations**, 10 rows: prevention, replacement, state-based
   actions, simultaneous triggers, CR 400.7 new objects, coin flips and queued extra
   turns. They cannot be observed on Forge without an engine event stream. That needs a
   separately authorized Forge bridge issue.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`
