# Mid-game lane selector design — multi-select targets and divided-damage assignment

Workstream: `MIDGAME-LANE-MULTISELECT-AMOUNT-CLOSURE-20261001` (issue #449)
Parent: #255, Coordinator sequencing comment 5931735894.
`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

## Decision-frame semantics observed on the current lane

These shapes were reproduced against the pinned candidate mechanics on the
production mid-game lane (`create_midgame_game` / `get_midgame_decision` /
`get_legal_actions` / `submit_action`). The local development artifact predates
the final pin, so the observation is `MODELED` for pin purposes; the frame
structure is engine-authored and read verbatim from the engine.

### Divided damage (Magma Opus; `PILOT_TARGET_AMOUNT`, `PILOT_MULTI_AMOUNT`)

1. `priority` — the scripted cast of `obj:pilot-opus` is an engine-offered
   action (`xmage_option_metadata.ability_type == "spell"`).
2. `target_amount` frame #1 — prompt
   `Select targets (selected 0 of 4) (damage)`, `minimum_selections = 1`,
   `maximum_selections = 1`, context
   `{numeric_min: 1, numeric_max: 4, amount_remaining: 4}`. Options are
   `target_amount` options for players and permanents, each carrying
   `metadata.object_id` (native id) and `metadata.name` (e.g.
   `Full Game Seat 2`).
3. `target_amount` frame #2 — same class, `amount_remaining: 2`,
   `numeric_max: 2`; the already-chosen object is no longer offered.
4. `target` frame — prompt `Select permanents (selected 0 of 2, min 2) (tap)`
   with `minimum_selections = 2`, `maximum_selections = 2`: the engine's own
   true multi-select frame, in one response.

The record's `decision_script` scripts steps 1–3 only. The record's required
events (`target_amount_frame:P1`, `amount_assignment:2+2`) and its terminal
postcondition ("Assignment totals exactly 4 and each selected damage target
receives at least 1") are satisfied at step 3. The row therefore stops there,
with the engine parked on the spell's tap-target frame: the record does not
script tap targets and the lane never invents one.

### Six-creature target (`MICRO_COSTS`)

1. `priority` — the scripted cast of `obj:micro-hex`.
2. `target` frame — prompt `Select creatures (selected 0 of 6, min 6)`,
   `minimum_selections = 6`, `maximum_selections = 6`, with seven eligible
   creatures offered (Esior, four Grizzly Bears, Kediss and Rograkh). The
   record requests exactly six semantic objects; all six are submitted in one
   response.
3. `mana_payment` frames — the first exposes the engine's own determined cost
   in `context.unpaid_mana` (`{7}{B}{B}` = printed `{4}{B}{B}` plus the {3}
   increase), and the run charges it with one pool spend per mana.

## Selectors

Both selectors live in `_scripted_answer` and consume only the engine's
`legal_options` and the pending decision's own bounds. Neither computes
legality, targets, amounts, or ordering.

### `semantic_objects` (multi-select)

Input: the record's ordered list of semantic identities. For each identity the
selector resolves exactly one engine offer in one of two authoritative
namespaces — a fixture semantic object bound to a placed native id, or a
principal label (`P<n>`) — and requires the requested cardinality to lie inside
the pending frame's own `minimum_selections..maximum_selections`. The response
submits every offered option id in one `selected_option_ids` vector, with
`legal_action_id` one of them.

Fail-closed: absent identity; malformed/non-string entry; repeated identity; two
requests resolving to one offer; two offers resolving one identity; cardinality
outside the engine frame; a frame that exposes no selection bounds; an offer
without an option id. The engine independently rejects a stale decision id,
foreign actor, out-of-domain option, or duplicate id; the lane only ever reads
the current pending frame, so it cannot submit a stale one.

### `amount_assignment` (divided damage)

Input: an ordered mapping semantic target → positive integer amount. Each
engine `target_amount` frame consumes one declared leg: the selector resolves
the leg's semantic target against the frame's offers and requires the declared
amount to lie inside the frame's own `numeric_min..numeric_max` (the engine's
leg bounds, never a Lab rule). It submits the option id plus `numeric_choice`
in one proposal. The step completes when every declared leg has been consumed;
if the engine asks for another assignment while the step is still current, the
selector fails closed rather than defaulting. (In the executor loop the success
check runs before the next pending frame is read once the obligation tokens
hold, so a record whose legs already total the engine's `amount_remaining`
stops there; the engine cannot ask for another assignment after the remaining
total reaches zero.)

Fail-closed: missing/ambiguous target; non-integer, boolean, zero or negative
amount; amount outside the engine's numeric bounds; an extra assignment frame
beyond the declared legs; a frame that exposes no numeric bounds; an offer
without an option id.

## Token verifiers

### `amount_assignment:<a>+<b>...`

Evidence is the ordered list of divided-damage assignment frames this run
actually submitted: each must be a `target_amount` frame the executor scripted,
with a semantic key bound to the record, an accepted explicit amount, the
engine's own `decision_id`, and the selected label present among the frame's
offered labels. The observed amount sequence must equal the token's, and the
sum must equal the first frame's own `amount_remaining` when exposed.

This is the wrong-reason control at the verifier level: a frame that was only
reached, an unscripted frame, a frame without an engine decision identity, or a
correct-looking final board with no decision trace cannot satisfy it.

### `cost_determined:base_plus_<N>_generic`

The row declares the cost obligation `(source semantic id, base mana,
determined mana)`. Evidence is the engine's own payment run after that exact
scripted cast (the cast frame's submitted option names the native source): the
first payment frame's `context.unpaid_mana` must parse to symbol vectors equal
to the declared determined cost and equal to the declared base plus exactly
`N` generic; and the run must actually have charged exactly that many mana
(pool spends, with no floating tap) with an engine `decision_id` on every
payment frame.

This distinguishes the intended cost from: merely reaching the target frame
(no payment frames), resolving without the intended payment (determined cost
mismatch), preconstructed post-payment resources (no spends), or an adjacent
native mechanism (wrong cast source, unscripted cast).

## Terminal checks

`assignment_total` and `assignment_minimum` read the same accepted assignment
frames; `assignment_total` additionally requires agreement with the engine
frame's own remaining total when exposed.

## Files

- `src/commander_lab/qualification/current_boundary/midgame_rows.py`
- `scripts/run_midgame_capability_probe.py` (`submit_proposal` gains the
  multi-select vector; no new protocol surface)
- `tests/qualification/test_current_boundary_midgame_rows.py`
