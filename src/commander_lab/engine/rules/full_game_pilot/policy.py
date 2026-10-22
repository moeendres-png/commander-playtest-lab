"""The full-game decision policy: one entry point over the decision layers."""

from __future__ import annotations

import re
from typing import Any

from .common import (
    FullGameProtocolError,
    public_full_game_errors,
)
from .priority import _PriorityDecisions

# Mizzix's Mastery (overload) asks for one copied card at a time and removes it
# only when one was chosen; see ``_decide_boolean`` for the matching guard.
_COPY_CAST_PROMPT = re.compile(r"Select up to one copied card to cast")
# Slaughter the Strong ("chooses any number of creatures ... with total power 4 or less") asks for
# one creature at a time and reports the running total; choosing a creature again takes it back out.
_RUNNING_SELECTION_PROMPT = re.compile(r"\(already selected\b")


class ExternalPilotDecisionPolicy(_PriorityDecisions):
    """Decision-complete adapter from XMage typed choices to Commander Lab pilots.

    This is the primary policy, not a fallback. Every supported decision class
    has an explicit deterministic/stochastic rule. Unknown classes fail closed.
    """

    _SUPPORTED_CLASSES = frozenset(
        {
            "priority",
            "target",
            "choose_object",
            "target_amount",
            "mulligan",
            "choose_use",
            "choice",
            "pile",
            "mana_payment",
            "announce_x",
            "amount",
            "multi_amount",
            "replacement_effect",
            "trigger_order",
            "mode",
            "declare_attacker",
            "declare_blocker",
        }
    )

    @public_full_game_errors
    def decide(self, request: dict[str, Any]) -> dict[str, Any]:
        decision_id = self._required_text(request, "decision_id")
        actor_id = self._required_text(request, "actor_id")
        decision_class = self._required_text(request, "decision_class")
        if decision_class not in self._SUPPORTED_CLASSES:
            raise FullGameProtocolError(
                f"unsupported discretionary decision class: {decision_class}"
            )
        pilot_state = self._required_object(request, "pilot_state")
        seat = int(pilot_state.get("seat", -1)) + 1
        runtime = self._pilots.get(seat)
        if runtime is None:
            raise FullGameProtocolError(f"decision actor has unmapped seat: {seat}")
        if decision_class not in {"mana_payment", "choose_object"}:
            self._special_mana_pending.pop(seat, None)
            self._payment_source.pop(seat, None)
        # #802 review P1: a decision of any other class for this seat ends the
        # current block-declaration round. After a declaration the engine
        # accepts, the seat's next decision is a priority window in the
        # declare-blockers step, so an extra combat phase later in the same
        # turn (Aggravated Assault, Moraug, Aurelia) must start the ladder
        # over instead of counting as engine rejections. A rejected
        # declaration is re-asked with no other decision in between, so
        # genuine re-asks still reach the ladder in ``_decide_blocks``.
        if decision_class != "declare_blocker":
            self._block_frame_asks.pop(seat, None)
        # #920: the asks of one Phyrexian payment are back to back, so a
        # decision of any other class ends the life they promised.
        if decision_class != "choose_use":
            self._phyrexian_life_promised.pop(seat, None)
            self._selection_ended.discard(seat)
        options = self._legal_options(request)
        context = dict(request.get("context") or {})
        min_selections = int(request.get("minimum_selections", request.get("min_selections", 0)))
        max_selections = int(request.get("maximum_selections", request.get("max_selections", 0)))
        decision_offset = int(request.get("decision_offset", -1))
        if decision_offset < 1:
            raise FullGameProtocolError("decision_offset must be a positive integer")
        rng = self._rng(decision_offset, decision_class, seat)

        selected: list[str] = []
        numeric_choice: int | None = None
        numeric_choices: list[int] | None = None
        prompt = str(request.get("prompt", ""))
        running_selection = (
            decision_class == "target"
            and min_selections == 0
            and _RUNNING_SELECTION_PROMPT.search(prompt) is not None
        )

        if decision_class == "mulligan":
            selected = [self._decide_mulligan(runtime, pilot_state, options, rng)]
        elif decision_class in {"announce_x", "amount"}:
            numeric_choice = self._decide_numeric(
                runtime,
                pilot_state,
                context,
                rng,
                decision_class=decision_class,
                prompt=prompt,
                source_object=request.get("source_object"),
            )
        elif decision_class == "multi_amount":
            numeric_choices = self._decide_multi_amount(
                runtime, pilot_state, context, rng, prompt=prompt
            )
        elif decision_class == "mana_payment":
            self._last_unpaid_mana[seat] = str(context.get("unpaid_mana") or "")
            payer = request.get("source_object")
            if isinstance(payer, dict) and payer.get("source_object_id"):
                self._payment_source[seat] = str(payer["source_object_id"])
            selected = [self._decide_mana(runtime, pilot_state, options, context, rng)]
            chosen_type = next(
                (
                    str(option.get("option_type", ""))
                    for option in options
                    if option.get("option_id") == selected[0]
                ),
                "",
            )
            self._special_mana_pending[seat] = chosen_type == "special_mana_action"
            if chosen_type == "cancel_mana_payment":
                self._remember_failed_payment(seat, pilot_state)
        elif decision_class == "choose_use":
            selected = [
                self._decide_boolean(
                    runtime,
                    pilot_state,
                    options,
                    context,
                    rng,
                    prompt=prompt,
                    source_object=request.get("source_object"),
                )
            ]
        elif decision_class == "pile":
            selected = [self._decide_pile(runtime, pilot_state, options, context, rng)]
        elif decision_class == "choice":
            selected = [
                self._decide_choice(runtime, pilot_state, options, context, rng, prompt=prompt)
            ]
        elif decision_class in {"replacement_effect", "trigger_order"}:
            selected = [self._decide_semantic_option(runtime, pilot_state, options, rng)]
        elif decision_class == "mode":
            mode = self._decide_mode(runtime, pilot_state, options, rng, min_selections)
            selected = [] if mode is None else [mode]
        elif decision_class == "priority":
            # #700: this seat's remembered cost describes the action it chose
            # last time, and the next priority decision of this seat is a
            # different action, so it is dropped before a new one is picked.
            # #815: same for failed X announcements — a new priority action
            # starts with a clean retry slate.
            self._priority_cost_facts.pop(seat, None)
            self._priority_x_counter_caps.pop(seat, None)
            self._failed_x_announcements.pop(seat, None)
            self._last_priority_label.pop(seat, None)
            self._last_priority_source.pop(seat, None)
            # A priority window means the effect that was asking has resolved.
            self._life_dig_yes.pop(seat, None)
            self._counter_cost_progress.pop(seat, None)
            selected = [self._decide_priority(runtime, pilot_state, options, rng)]
            self._remember_priority_cost_facts(seat, options, selected, pilot_state)
            self._remember_own_cast(seat, options, selected, turn=pilot_state.get("turn_number"))
            # Measured where the cast was chosen: a cancelled payment leaves
            # its sources tapped in the cancel's own state view.
            if seat in self._last_priority_label:
                self._last_priority_visible_mana[seat] = self._available_mana(
                    self._actor(pilot_state)
                )
        elif (
            decision_class == "choose_object"
            and self._special_mana_pending.pop(seat, False)
            and max_selections >= 1
            and options
        ):
            # #732: a Delve-style payment ("exile a card from your graveyard")
            # asks which card pays. Choosing none leaves the cost unpaid and
            # the engine offers the same payment again, forever. Pay with
            # the cheapest card, which is the least likely to matter later.
            selected = [self._cheapest_object(options)]
        elif decision_class in {"target", "choose_object", "target_amount"}:
            # A running selection offers the creatures already picked again (picking one
            # takes it back out), so the pilot is shown only the ones it has not picked.
            picked = self._running_selection.get(seat, set()) if running_selection else set()
            asking_source = request.get("source_object")
            paying_counters = (
                self._decide_counter_cost_objects(seat, pilot_state, options, min_selections)
                if decision_class == "choose_object"
                else None
            )
            selected = (
                paying_counters
                if paying_counters is not None
                else self._decide_targets(
                    runtime,
                    pilot_state,
                    request,
                    self._without_tapped_objects(
                        pilot_state,
                        context,
                        self._without_payment_source(
                            seat,
                            decision_class,
                            context,
                            [option for option in options if option.get("option_id") not in picked],
                            asking=str(asking_source.get("source_object_id", ""))
                            if isinstance(asking_source, dict)
                            else "",
                            minimum=min_selections,
                        ),
                        minimum=min_selections,
                    ),
                    min_selections,
                    max_selections,
                    rng,
                )
            )
            if decision_class == "target_amount":
                numeric_choice = self._decide_numeric(
                    runtime,
                    pilot_state,
                    context,
                    rng,
                    decision_class=decision_class,
                    prompt=prompt,
                    source_object=request.get("source_object"),
                )
        elif decision_class == "declare_attacker":
            selected = [self._decide_attack(runtime, pilot_state, options, rng)]
        elif decision_class == "declare_blocker":
            selected = self._decide_blocks(
                runtime,
                pilot_state,
                options,
                min_selections,
                max_selections,
                rng,
            )
        else:  # pragma: no cover - guarded by exhaustive supported class set
            raise FullGameProtocolError(f"unhandled decision class: {decision_class}")

        if decision_class in {"target", "choose_object"} and _COPY_CAST_PROMPT.match(prompt):
            if selected:
                self._copy_cast_declined.discard(seat)
            else:
                self._copy_cast_declined.add(seat)

        if running_selection and selected:
            self._running_selection.setdefault(seat, set()).update(selected)
        else:
            self._running_selection.pop(seat, None)
            if running_selection:
                self._selection_ended.add(seat)

        if len(selected) < min_selections or len(selected) > max_selections:
            raise FullGameProtocolError(
                f"policy produced {len(selected)} selections outside "
                f"{min_selections}..{max_selections} for {decision_class}"
            )

        response: dict[str, Any] = {
            "decision_id": decision_id,
            "actor_id": actor_id,
            "selected_option_ids": selected,
            "ordering": [],
        }
        if numeric_choice is not None:
            response["numeric_choice"] = numeric_choice
        if numeric_choices is not None:
            response["numeric_choices"] = list(numeric_choices)
        return response
