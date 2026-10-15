"""Priority windows: what to cast, activate or play."""

from __future__ import annotations

import random
from typing import Any

from commander_lab.models import (
    PilotActionView,
)

from ..full_game_pilot_views import (
    priority_view_fields,
)
from .combat import _CombatDecisions
from .common import (
    _LOG,
    FullGameProtocolError,
    _RuntimePilot,
)


class _PriorityDecisions(_CombatDecisions):
    def _decide_priority(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        rng: random.Random,
    ) -> str:
        pass_option = self._option_by_type(options, "pass_priority")
        pass_id = self._required_text(pass_option, "option_id")
        # Forced pass-only rounds carry no discretion: take them without
        # touching guard memory, so they can neither trip the guard nor
        # break a genuine no-progress chain interleaved around them.
        if len(options) == 1:
            return pass_id
        seat = runtime.binding.seat
        # Priority no-progress guard (liveness only, no MTG semantics):
        # identical window fingerprint on consecutive same-seat priority
        # decisions means prior selections changed nothing the offer
        # reflects (turn/phase/step/stack/pool/options all equal). Any real
        # progress (tapped land, spent pool, new trigger, advanced phase)
        # alters the fingerprint and resets the count.
        stack = state.get("stack")
        stack_names = (
            tuple(sorted(str(item.get("name", "")) for item in stack if isinstance(item, dict)))
            if isinstance(stack, list)
            else ()
        )
        pool = self._actor(state).get("mana_pool")
        pool_tuple = (
            tuple(sorted((str(key), str(value)) for key, value in pool.items()))
            if isinstance(pool, dict)
            else ()
        )
        fingerprint = (
            seat,
            state.get("turn_number"),
            state.get("phase"),
            state.get("step"),
            stack_names,
            pool_tuple,
            tuple(
                sorted(
                    (
                        self._required_text(option, "option_type"),
                        str(option.get("label", "")),
                    )
                    for option in options
                )
            ),
        )
        if self._priority_last_fingerprint.get(seat) == fingerprint:
            repeats = self._priority_repeat_count.get(seat, 1) + 1
        else:
            repeats = 1
        self._priority_last_fingerprint[seat] = fingerprint
        self._priority_repeat_count[seat] = repeats
        # #718: a window recurring inside one step is the same no-progress
        # shape as a consecutive repeat, so count occurrences of this exact
        # fingerprint within the current (turn_number, phase, step). The key
        # is the existing fingerprint plus nothing else, so no observation
        # the seat cannot already see enters it; a changed step, stack, pool
        # or offer is a different key and never inherits a count.
        step_key = (state.get("turn_number"), state.get("phase"), state.get("step"))
        if self._priority_step_key.get(seat) != step_key:
            self._priority_step_key[seat] = step_key
            self._priority_step_windows[seat] = []
        step_windows = self._priority_step_windows[seat]
        window_occurrences = 1
        for index, (known, _count) in enumerate(step_windows):
            if known == fingerprint:
                window_occurrences = _count + 1
                step_windows[index] = (known, window_occurrences)
                break
        else:
            step_windows.append((fingerprint, window_occurrences))
            if len(step_windows) > self._PRIORITY_STEP_WINDOW_LIMIT:
                # Bounded memory: a step that shows more distinct windows than
                # this is not the two-window ping-pong this counts, so drop the
                # oldest entry. The ping-pong keeps both windows and is
                # unaffected; this only prevents the guard itself growing
                # without limit in a long step.
                del step_windows[: len(step_windows) - self._PRIORITY_STEP_WINDOW_LIMIT]
        if self._priority_latched.get(seat) == fingerprint:
            # Latched: window never changed since the trip; keep passing.
            return pass_id
        if seat in self._priority_latched:
            # Window changed: unlatch and resume normal choice.
            del self._priority_latched[seat]
            self._priority_repeat_count[seat] = 1
        if repeats >= 4:
            self._priority_repeat_count[seat] = 0
            self._priority_latched[seat] = fingerprint
            _LOG.info(
                "priority no-progress guard: identical window %d times, passing priority",
                repeats,
            )
            return pass_id
        if window_occurrences >= 4:
            # #718: same threshold and the same latch as the consecutive
            # guard above -- a free action (Equip {0}) that alternates between
            # an empty stack and the ability on the stack never repeats
            # consecutively, so this is the bound that actually converges it.
            # Passing priority is always legal and never chooses on the
            # player's behalf: the seat is offered the same window again and
            # the pilot decides normally once that window changes.
            self._priority_latched[seat] = fingerprint
            _LOG.info(
                "priority no-progress guard: window recurred %d times in this step, "
                "passing priority",
                window_occurrences,
            )
            return pass_id
        non_mana = [
            option
            for option in options
            if self._required_text(option, "option_type") not in {"pass_priority", "mana_ability"}
        ]
        # Affordability-aware pilot judgment: an activated ability whose
        # engine-reported costs provably exceed the actor's free resources
        # (pool mana plus, for tap costs, an untapped source) is not offered
        # for immediate selection. Withheld options stay engine-offered.
        # Unknown/absent cost facts mean no gating: the engine remains the
        # authority.
        #
        # An action withheld ONLY for a pool shortfall on an ability that
        # spends its own source (Hedron Archive's {2}, {T}, Sacrifice) is still
        # offered, marked needs_mana_first: the pilot chooses the intent and
        # the Lab answers with a mana ability from another source. Withholding
        # it outright, while every priority mana ability scores below passing
        # because activating one there only floats mana, made the pool
        # impossible to fill and left that activation unreachable
        # (F-RULES-03). An action withheld for any other reason (a tap cost on
        # an already tapped source) is impossible whatever mana exists and
        # stays withheld.
        affordable: list[dict[str, Any]] = []
        needs_mana_first: list[dict[str, Any]] = []
        unreachable = 0
        for option in non_mana:
            if self._priority_action_affordable(option, state):
                affordable.append(option)
            elif self._priority_awaits_mana(option):
                needs_mana_first.append(option)
            else:
                unreachable += 1
        if unreachable:
            _LOG.info(
                "withheld %d priority action(s) the actor cannot fund from free resources at all",
                unreachable,
            )
        # #732: pilot judgment, like affordability above: an action a player
        # would not take because it only hurts themselves (countering only
        # their own spells, removal with no opposing target, a wipe that
        # costs them the most) is not put up for selection. It stays
        # engine-offered and passing is always legal.
        own_stack = self._own_stack_names(seat)
        self_defeating = 0
        kept: list[dict[str, Any]] = []
        for option in affordable:
            if priority_view_fields(option, state, own_stack_names=own_stack)[1] is None:
                kept.append(option)
            else:
                self_defeating += 1
        affordable = kept
        kept = []
        for option in needs_mana_first:
            if priority_view_fields(option, state, own_stack_names=own_stack)[1] is None:
                kept.append(option)
            else:
                self_defeating += 1
        needs_mana_first = kept
        # #732: an action chosen its cap of times this turn is not put up
        # again. Real games showed a cast that never reaches the stack (an
        # additional cost the seat cannot pay) or a no-gain loop (Basalt
        # Monolith untapping itself) selected over a thousand times in one
        # turn; a player stops trying after a few attempts.
        turn = state.get("turn_number")
        tried = self._turn_actions.get(seat)
        if tried is not None and tried[0] == turn:
            capped = [
                option
                for option in (*affordable, *needs_mana_first)
                if tried[1][str(option.get("label", ""))] >= self._turn_action_cap(option)
            ]
            if capped:
                capped_ids = {id(option) for option in capped}
                affordable = [o for o in affordable if id(o) not in capped_ids]
                needs_mana_first = [o for o in needs_mana_first if id(o) not in capped_ids]
                self_defeating += len(capped)
        failed = self._failed_payments.get(seat)
        if failed is not None and failed[0] == turn and failed[1]:
            visible = self._available_mana(self._actor(state))
            unpaid = [
                option
                for option in (*affordable, *needs_mana_first)
                if visible <= failed[1].get(str(option.get("label", "")), -1)
            ]
            if unpaid:
                unpaid_ids = {id(option) for option in unpaid}
                affordable = [o for o in affordable if id(o) not in unpaid_ids]
                needs_mana_first = [o for o in needs_mana_first if id(o) not in unpaid_ids]
                self_defeating += len(unpaid)
        if self_defeating:
            _LOG.info("withheld %d self-defeating priority action(s)", self_defeating)
        if needs_mana_first:
            _LOG.info(
                "offered %d pool-shortfall priority action(s) as needing mana first",
                len(needs_mana_first),
            )
        # WS229 F-RULES-03 disposition: Core-authorized mana abilities were
        # withheld from the pilot. Mana abilities are discretionary actions,
        # so they are offered to the pilot with explicit mana metadata
        # instead of being hidden. Only a lone pass (no discretion) is
        # auto-submitted, with a forced-move record.
        #
        # Affordability applies to mana abilities with activation mana costs
        # too (e.g. signets): selecting one the pool cannot fund spends a
        # shared resource mid-payment and fails activation. Pure mana
        # abilities (no mana cost, untapped source) always pass the gate.
        mana_options = [
            option
            for option in options
            if self._required_text(option, "option_type") == "mana_ability"
        ]
        affordable_mana = [
            option for option in mana_options if self._priority_action_affordable(option, state)
        ]
        if len(affordable_mana) != len(mana_options):
            _LOG.info(
                "withheld %d unaffordable mana abilit(ies) from pilot selection",
                len(mana_options) - len(affordable_mana),
            )
        pilot_state = self._pilot_state(runtime, state)
        # Twin-stable view identities (WS92-D5 pattern): raw engine option
        # ids embed per-process UUIDs, so pilot tiebreaks on them would make
        # same-seed fresh-process twins diverge. Views carry content-derived
        # stable ids (type + label + content occurrence, all Rules-visible);
        # the pilot's pick maps back to the raw engine id here. Occurrence
        # counting is keyed by content, never by bridge order, so input
        # permutation cannot change the outcome.
        raw_by_stable_id: dict[str, str] = {}
        deferred_by_stable_id: dict[str, dict[str, Any]] = {}
        occurrences: dict[str, int] = {}
        action_views: list[PilotActionView] = []
        for option in affordable:
            base = (
                "priority:"
                f"{self._required_text(option, 'option_type')}:"
                f"{str(option.get('label', 'action')).casefold()}"
            )
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            action_views.append(
                self._priority_action(option, state).model_copy(update={"action_id": stable_id})
            )
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
        for option in needs_mana_first:
            base = (
                "priority:"
                f"{self._required_text(option, 'option_type')}:"
                f"{str(option.get('label', 'action')).casefold()}"
            )
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            view = self._priority_action(option, state)
            view = view.model_copy(
                update={
                    "action_id": stable_id,
                    "metadata": {
                        **view.metadata,
                        "xmage_option_type": self._required_text(option, "option_type"),
                        # The pilot is choosing the intent, not an immediate
                        # activation: selecting this answers with a mana
                        # ability from another source first.
                        "needs_mana_first": True,
                    },
                }
            )
            action_views.append(view)
            deferred_by_stable_id[stable_id] = option
        for option in affordable_mana:
            base = f"priority:mana:{str(option.get('label', 'mana')).casefold()}"
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            action_views.append(
                self._priority_mana_action(option, state).model_copy(
                    update={"action_id": stable_id}
                )
            )
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
        action_views.append(
            PilotActionView(
                action_id=pass_id,
                action_kind="pass",
                card_name="Pass priority",
                floor_value=0.15,
                immediate_impact=0.0,
                metadata={"flexible_interaction": bool(state.get("stack"))},
            )
        )
        if len(action_views) == 1:
            _LOG.info("forced priority pass: no discretionary action offered")
            return pass_id
        decision = runtime.pilot.choose_action(pilot_state, action_views, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no priority action")
        if decision.selected_action_id == pass_id:
            return pass_id
        deferred = deferred_by_stable_id.get(decision.selected_action_id)
        if deferred is not None:
            return self._priority_mana_for(deferred, affordable_mana, pass_id)
        try:
            return raw_by_stable_id[decision.selected_action_id]
        except KeyError:
            raise FullGameProtocolError("pilot returned unknown stable priority action") from None
