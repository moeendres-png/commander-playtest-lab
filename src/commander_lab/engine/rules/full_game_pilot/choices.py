"""Mulligans, targets, modes, may-prompts, piles and named choices."""

from __future__ import annotations

import random
import re
from collections.abc import Mapping
from typing import Any

from commander_lab.agents.card_knowledge import card_facts
from commander_lab.models import (
    PilotActionView,
)

from ..full_game_pilot_lands import choose_lands_to_fetch
from ..full_game_pilot_targets import commander_clock_bonus, target_side
from ..full_game_pilot_views import (
    color_choice_rank,
    commander_creature_ids,
    counter_cost_kinds,
    is_unsuspendable_target,
    named_choice_rank,
    named_counter_piles,
    needed_colors,
    needs_commander_target,
    own_counter_stacks,
    own_counters_by_kind,
    permanent_owner,
    sweep_mode_net,
    target_object_bonus,
)
from .common import (
    _LOG,
    DECLINE_ALIGNED_BOOLEAN_OUTCOMES,
    FullGameProtocolError,
    _multikicker_offer,
    _MultikickerOffer,
    _optional_mana_cost,
    _RuntimePilot,
)
from .payment import _PaymentDecisions

# The engine's own tag for "choose a card to cast or play without paying for it". Picking one is
# a benefit to the chooser. Scored like a neutral target, every card of a free-cast choice such as
# Izzet Chemister's "Select up to one card to cast" came out negative, the pilot picked none, and
# then answered Yes to "Continue casting?" for ever (precon pod, 50000 decisions, no cast).
_FREE_PLAY_OUTCOMES = frozenset({"playforfree"})
_FREE_CAST_PROMPT = re.compile(r"Cast spell without paying its mana cost")
_PHYREXIAN_LIFE_PROMPT = re.compile(r"Pay (\d+) life instead of ")
_FREE_CAST_CONTINUE_PROMPT = re.compile(
    r"You can cast \d+ more spells? for free\. Continue casting"
)
_COPY_CAST_CONTINUE_PROMPT = re.compile(r"Continue to choose copies and cast\?")
_INFINITE_LOOP_PROMPT = re.compile(r"Draw game because of infinite looping\?")
# Lim-Dul's Vault: "As many times as you choose, you may pay 1 life, put those cards on the bottom
# of your library, then look at the top five cards." The pilot cannot judge the five cards it
# digs past, so it answered Yes every time (precon pod, plan seed 5: thousands of times, one game
# of nearly an hour). A seat stops after a few digs, like a player who does not find what it wants.
_LIFE_DIG_PROMPT = re.compile(r"Pay 1 life and look at the next 5 cards\?")
_LIFE_DIG_CAP = 3
# Wild Ricochet ("copy target instant or sorcery spell, you may choose new targets for the copy"):
# the engine asks "Change this 1 of 1 target: <spell>?" for every copy. The pilot said Yes and
# aimed the copy at another Wild Ricochet each time, so every copy made another copy and the
# stack grew without end (precon pod 031, plan seed 1, game seed 1: 6000 decisions at turn 21,
# 4363 spells alive, each priority window slower than the last). A seat re-aims a few copies a
# turn, like a player who has a reason to; the rest keep the targets they were copied with.
_RETARGET_PROMPT = re.compile(r"\AChange this \d+ of \d+ targets?: ")
_RETARGET_TURN_CAP = 4
_CONTINUE_SELECTION_LABEL = "continue the selection"

# "Choose a counter to remove from <name>": the pick among the counter types of a permanent that
# pays a "remove N counters" cost.
_COUNTER_KIND_PROMPT = re.compile(r"Remove an? .+ counter from an? permanent you control or ")
_COUNTER_CHOICE_PROMPT = re.compile(
    r"Choose a counter to remove from (?:<[^>]*>)?(?P<name>[^<\[]+)"
)


def _targets_own_spell(option: Mapping[str, object], own_ids: set[str]) -> bool:
    """Whether a stack-zone target option is the spell that is choosing its targets."""
    metadata = option.get("metadata")
    meta = metadata if isinstance(metadata, Mapping) else {}
    if meta.get("zone") != "stack":
        return False
    return bool({str(meta.get("object_id") or ""), str(meta.get("source_card_id") or "")} & own_ids)


class _ChoiceDecisions(_PaymentDecisions):
    def _decide_mulligan(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        rng: random.Random,
    ) -> str:
        seat = runtime.binding.seat
        actor = self._actor(state)
        hand = actor.get("hand")
        if not isinstance(hand, list):
            raise FullGameProtocolError("mulligan requires actor hand visibility")
        cards = tuple(self._hand_action(card) for card in hand if isinstance(card, dict))
        keep, _score = runtime.pilot.should_keep_opening_hand(
            cards,
            mulligans=self._mulligan_count[seat],
            free_first=True,
            commander_names=runtime.binding.commander_names,
            rng=rng,
        )
        if self._mulligan_count[seat] >= 3:
            # WS229 F-RULES-03 disposition: the cap overrides pilot discretion,
            # so the forced keep is a logged forced-move record, never silent.
            if not keep:
                _LOG.info(
                    "forced mulligan keep: seat=%s mulligans=%s pilot_wanted_mulligan=true",
                    seat,
                    self._mulligan_count[seat],
                )
            keep = True
        desired = "keep" if keep else "mulligan"
        chosen = self._option_by_type(options, desired)
        if desired == "mulligan":
            self._mulligan_count[seat] += 1
        return self._required_text(chosen, "option_id")

    def _decide_targets(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        request: dict[str, Any],
        options: list[dict[str, Any]],
        min_selections: int,
        max_selections: int,
        rng: random.Random,
    ) -> list[str]:
        context = request.get("context")
        structured_context = context if isinstance(context, dict) else {}
        # WS229 F-RULES-03 disposition: London-bottom routing is driven by
        # the bridge-supplied structured flag
        # (context.bottom_of_library_selection), never by prompt-text
        # heuristics. The flag is set only inside the native
        # putCardsOnBottomOfLibrary selection path.
        if structured_context.get("bottom_of_library_selection") is True:
            actor = self._actor(state)
            hand = actor.get("hand")
            if not isinstance(hand, list):
                raise FullGameProtocolError("London bottom decision requires actor hand visibility")
            legal_ids = {self._required_text(option, "option_id") for option in options}
            hand_ids = {
                self._required_text(card, "object_id") for card in hand if isinstance(card, dict)
            }
            # Two engine-native shapes share the bottom-selection path:
            # London mulligan bottoms cards FROM HAND (options are hand
            # cards), while library effects (e.g. Dig Through Time) order
            # looked-at LIBRARY cards (options are not hand cards). Only
            # the London shape uses opening-hand bottom valuation; library
            # bottom-ordering falls through to generic offered-option
            # ranking below (highest utility first: last chosen ends
            # bottommost, so the best card stays most accessible).
            if legal_ids and legal_ids <= hand_ids:
                count = min_selections
                card_actions = tuple(
                    self._hand_action(card) for card in hand if isinstance(card, dict)
                )
                selected = runtime.pilot.choose_bottom_cards(
                    card_actions,
                    count,
                    commander_names=runtime.binding.commander_names,
                )
                if not set(selected).issubset(legal_ids):
                    raise FullGameProtocolError("pilot bottom-card selection is not XMage-legal")
                return list(selected)

        if not options:
            return []
        source = request.get("source_object")
        if (
            isinstance(source, dict)
            and source.get("ability_type") == "spell"
            and needs_commander_target(
                str(source.get("source_name") or ""), state, spell_on_stack=True
            )
        ):
            # Cast outside a sorcery window, the spell only works against a commander.
            commanders = commander_creature_ids(state)
            options = [
                option
                for option in options
                if str((option.get("metadata") or {}).get("object_id", "")) in commanders
            ] or options
        if isinstance(source, dict):
            # A token aimed at an exile-and-suspend trigger kills the game; every other
            # creature, and passing on "up to one", stays open.
            source_name = str(source.get("source_name") or "")
            options = [
                option for option in options if not is_unsuspendable_target(source_name, option)
            ]
            # CR 115.5: a spell cannot target itself. XMage still lists the spell being cast among
            # "target instant or sorcery spell" (Wild Ricochet, Expansion), the pilot picked it,
            # and the copies of a Wild Ricochet aimed at itself copied one another for ever
            # (precon pod 031, plan seed 1, game seed 1: 6000 decisions at turn 21).
            if source.get("ability_type") == "spell":
                options = self._targets_the_discount_pays_for(state, source_name, options)
                own = {
                    str(source.get("source_object_id") or ""),
                    str(source.get("ability_original_id") or ""),
                } - {""}
                spared = [option for option in options if not _targets_own_spell(option, own)]
                if spared or min_selections == 0:
                    options = spared
            if not options and min_selections == 0:
                return []
        outcome = str((request.get("context") or {}).get("outcome", "neutral")).casefold()
        pilot_state = self._pilot_state(runtime, state)
        # Twin-stable target identities: (zone, zone_index) pins the same
        # physical card across fresh processes (identical zone-event
        # streams); occurrence fallback is content-keyed and order-free.
        # Raw engine ids never order or identify pilot inputs.
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[str, int] = {}
        source_name = str(source.get("source_name") or "") if isinstance(source, dict) else ""
        actor_id = self._required_text(state, "actor_id")
        built: list[tuple[dict[str, object], PilotActionView]] = []
        for option in options:
            metadata = option.get("metadata")
            meta = metadata if isinstance(metadata, dict) else {}
            zone = meta.get("zone")
            zone_index = meta.get("zone_index")
            if (
                isinstance(zone, str)
                and zone
                and isinstance(zone_index, int)
                and not isinstance(zone_index, bool)
                and zone_index >= 0
            ):
                base = (
                    "target:"
                    f"{self._required_text(option, 'option_type')}:"
                    f"{str(option.get('label', 'target')).casefold()}:"
                    f"{zone}:{zone_index}"
                )
            else:
                base = (
                    "target:"
                    f"{self._required_text(option, 'option_type')}:"
                    f"{str(option.get('label', 'target')).casefold()}"
                )
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
            built.append(
                (
                    option,
                    self._target_action(option, state, outcome).model_copy(
                        update={"action_id": stable_id}
                    ),
                )
            )
        # A gift ("target opponent draws a card", Humble Defector's "gains control of this
        # creature"): the opponent offered is the one that gets it, so it goes to the weakest,
        # not to the one a removal ranking would aim at. Gifts only ever offer opponents.
        gift = outcome == "drawcard" and all(
            action.metadata.get("target_is_player") is True and action.target_player_id != actor_id
            for _option, action in built
        )
        strongest = max((action.target_threat for _option, action in built), default=0.0)
        side = target_side(outcome, source_name)
        mixed = len({action.target_player_id == actor_id for _option, action in built}) > 1
        ranked: list[tuple[float, str, str]] = []
        for option, action in built:
            if gift:
                score = strongest - action.target_threat
            else:
                breakdown = runtime.pilot.evaluate_action(pilot_state, action)
                score = (
                    breakdown.total_utility
                    + self._target_alignment(action, state, outcome, source_name, mixed=mixed)
                    + target_object_bonus(
                        option,
                        state,
                        outcome,
                        own_stack_names=self._own_stack_names(runtime.binding.seat),
                        source_name=source_name,
                    )
                )
                metadata = option.get("metadata")
                object_id = (metadata.get("object_id") if isinstance(metadata, dict) else None) or (
                    option.get("option_id")
                )
                found = permanent_owner(str(object_id), state)
                if side == "opponent" and found is not None:
                    score += commander_clock_bonus(found[1], found[0], state, actor_id, outcome)
            ranked.append((score, action.card_name, action.action_id))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        ranked = self._rank_land_search(ranked, built, state, rng, max_selections)

        if max_selections <= 0:
            return []
        if outcome in {"benefit", "benefit_to_controller"} | _FREE_PLAY_OUTCOMES:
            take = max_selections
        elif min_selections == 0:
            take = 0 if all(score < 0.0 for score, _label, _oid in ranked) else 1
        else:
            take = min_selections
        take = max(min_selections, min(max_selections, take))
        try:
            return [raw_by_stable_id[stable_id] for _score, _label, stable_id in ranked[:take]]
        except KeyError:
            raise FullGameProtocolError("pilot returned unknown stable target action") from None

    @staticmethod
    def _rank_land_search(
        ranked: list[tuple[float, str, str]],
        built: list[tuple[dict[str, object], PilotActionView]],
        state: Mapping[str, object],
        rng: random.Random,
        max_selections: int,
    ) -> list[tuple[float, str, str]]:
        """A search of the library for lands is ranked by the colours the actor still needs.

        All the lands of one search scored alike, so the one that sorted last by name was taken:
        Swamp 79 times, Plains 64 and Island never in 24 recorded games (#989 phase 6).
        """
        names: dict[str, str] = {}
        for option, action in built:
            meta = option.get("metadata")
            if not isinstance(meta, dict) or meta.get("zone") != "library":
                return ranked
            name = str(meta.get("name") or option.get("label") or "")
            facts = card_facts(name)
            if facts is None or not facts.is_land:
                return ranked
            names[action.action_id] = name
        if len(set(names.values())) < 2:
            return ranked
        order = choose_lands_to_fetch(
            list(names.values()), state, rng, count=max(1, max_selections)
        )
        position = {name: index for index, name in enumerate(dict.fromkeys(order))}
        return sorted(ranked, key=lambda item: position.get(names.get(item[2], ""), len(position)))

    def _decide_semantic_option(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        rng: random.Random,
    ) -> str:
        if not options:
            raise FullGameProtocolError("semantic decision has no legal options")
        pilot_state = self._pilot_state(runtime, state)
        # Twin-stable identities (same pattern as priority/targets).
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[str, int] = {}
        actions: list[PilotActionView] = []
        for option in options:
            base = f"semantic:{str(option.get('label', 'option')).casefold()}"
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
            actions.append(
                self._semantic_action(option).model_copy(update={"action_id": stable_id})
            )
        decision = runtime.pilot.choose_action(pilot_state, actions, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no semantic option")
        try:
            raw_id = raw_by_stable_id[decision.selected_action_id]
        except KeyError:
            raise FullGameProtocolError("pilot returned unknown stable semantic option") from None
        return self._require_offered(raw_id, options, "semantic option")

    def _decide_mode(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        rng: random.Random,
        min_selections: int = 1,
    ) -> str | None:
        """Modal choice with native target-availability ranking.

        The bridge projects per-mode ``mode_targets_available`` from the
        engine's own ``Target.canChoose`` verdict and, per CR 700.2a, offers
        only choosable modes whenever at least one is (F-35). Modes explicitly
        lacking targets are still depreferred here, for older transcripts;
        unknown/absent flags mean no filtering and the engine stays the
        authority. When every mode lacks targets the bridge lists them all,
        the pilot still chooses (transcript agency), and the bridge maps the
        doomed cast to pass via its no-viable-mode flag.
        """
        if not options:
            raise FullGameProtocolError("mode decision has no legal options")
        viable = [
            option
            for option in options
            if not isinstance(option.get("metadata"), dict)
            or option["metadata"].get("mode_targets_available") is not False
        ]
        # A "choose one or more" sweep (Farewell) is chosen mode by mode, the
        # way a player reads it: take the sweeps that cost the table more than
        # the actor and stop (an empty answer, offered once the minimum is
        # met) when none is left. Any mode that is not such a sweep keeps the
        # pilot's own choice.
        candidates = viable or options
        actor_id = str(state.get("actor_id") or "")
        nets = [
            sweep_mode_net(str(option.get("label", "")), state, actor_id) for option in candidates
        ]
        if candidates and all(net is not None for net in nets):
            ranked = sorted(
                zip(nets, candidates, strict=True),
                key=lambda pair: (-float(pair[0] or 0.0), str(pair[1].get("label", "")).casefold()),
            )
            best_net, best = ranked[0]
            if min_selections == 0 and float(best_net or 0.0) <= 0.0:
                return None
            return self._required_text(best, "option_id")
        return self._decide_semantic_option(runtime, state, candidates, rng)

    def _decide_boolean(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        context: dict[str, Any],
        rng: random.Random,
        *,
        prompt: str = "",
        source_object: Any = None,
    ) -> str:
        if not options:
            raise FullGameProtocolError("boolean decision has no legal options")
        offered = list(options)
        outcome = str(context.get("outcome", "neutral")).casefold()
        values: dict[str, bool] = {}
        for option in options:
            metadata = option.get("metadata")
            value = metadata.get("value") if isinstance(metadata, dict) else None
            if not isinstance(value, bool):
                raise FullGameProtocolError("boolean option is missing explicit boolean value")
            values[self._required_text(option, "option_id")] = value
        # Multikicker-chain guard (liveness only, no may-semantics). Only the
        # engine's multikicker offer repeats: its own affordability check
        # covers one payment, so KickerAbility re-asks "Pay N times ..." with
        # N = previous N + 1 for as long as the pilot says Yes. Counting is
        # therefore scoped to that chain -- same ability, same outcome, the
        # next ordinal -- and the affirmative option is withheld only once the
        # pilot's own visible mana cannot fund another payment. Every other
        # decision (a different ability, outcome, ordinal, a No, or a prompt
        # with no ordinal at all) resets the count, and a prompt the Lab cannot
        # parse is never capped: the Lab never decides a discretionary choice
        # for a player (F-RULES-03).
        seat = runtime.binding.seat
        # Phyrexian-life guard (legality, #920). ManaCostsImpl asks once per
        # Phyrexian symbol, "Pay 2 life instead of {B}?", and tests every ask
        # against the life total as it stands before any of them is paid, so
        # at 2 life both asks of {B/P}{B/P} (Lashwrithe's Equip) are offered
        # although CR 119.4 lets a player pay no more life than they have. A
        # second Yes then leaves an unpayable PayLifeCost and the engine
        # fails the whole activation. The life the earlier Yes answers of
        # this payment already promised is therefore taken off before the next
        # Yes is offered. The asks of one payment are consecutive, so any
        # other prompt (and, in ``decide``, any other decision class) starts
        # the count over.
        life_prompt = _PHYREXIAN_LIFE_PROMPT.match(prompt)
        life_promised = 0
        life_yes_blocked = False
        if life_prompt is None:
            self._phyrexian_life_promised.pop(seat, None)
        else:
            life_promised = self._phyrexian_life_promised.get(seat, 0)
            life = self._actor(state).get("life")
            life_yes_blocked = isinstance(life, int | float) and (
                life < life_promised + int(life_prompt.group(1))
            )
        offer = _multikicker_offer(prompt)
        chain_key = (self._boolean_source_key(source_object), outcome)
        prior = self._boolean_repeat.get(seat)
        answered_yes = 0
        cap: int | None = None
        if (
            offer is not None
            and prior is not None
            and prior[0] == chain_key
            and prior[1] == offer.ordinal - 1
        ):
            answered_yes = prior[2]
            cap = self._boolean_yes_cap(offer, self._actor(state), source_object)
        dig_key = self._boolean_source_key(source_object)
        dug = 0
        if _LIFE_DIG_PROMPT.match(prompt):
            prior_dig = self._life_dig_yes.get(seat)
            dug = prior_dig[1] if prior_dig is not None and prior_dig[0] == dig_key else 0
        dig_yes_blocked = dug >= _LIFE_DIG_CAP
        # Optional-cost guard (payment, #989 phase 5b). The engine asks "Pay Kicker {3}{B} ?" after
        # checking that one cost, not that cost on top of the spell, and a "you may pay" trigger
        # after the same single check. A Yes the seat's own mana provably cannot fund only cancels
        # the payment, and the spell is not cast either (the unkicked Nullpriest of Oblivion
        # stayed in hand). Cost text the model cannot read is never withheld.
        optional_cost = _optional_mana_cost(prompt)
        cost_yes_blocked = optional_cost is not None and self._cost_cannot_be_paid(
            state, optional_cost * (offer.ordinal if offer is not None else 1), source_object
        )
        yes_withheld = (
            life_yes_blocked
            or dig_yes_blocked
            or cost_yes_blocked
            or (cap is not None and answered_yes >= cap)
        )
        selectable = [
            option
            for option in options
            if not (values[self._required_text(option, "option_id")] and yes_withheld)
        ]
        # Free-cast retry guard (liveness only, #816/#817). XMage's
        # castMultipleWithAttributeForFree keeps a card whose free cast was
        # reversed (no legal target) and, for a non-computer player, re-asks
        # "Continue casting?" forever. A cast prompt this seat already
        # answered Yes to, followed by "Continue casting?", failed to cast;
        # the identical cast prompt is not offered Yes again this turn.
        turn = state.get("turn_number")
        failed_turn, failed = self._free_cast_failed.get(seat, (None, set()))
        if failed_turn != turn:
            failed = set()
        if _FREE_CAST_PROMPT.match(prompt) and prompt in failed:
            kept = [o for o in selectable if not values[self._required_text(o, "option_id")]]
            if kept:
                selectable = kept
                self._free_cast_refused[seat] = turn
                _LOG.info("free-cast guard: %s already failed this turn; declining", prompt)
        elif (
            _FREE_CAST_CONTINUE_PROMPT.match(prompt)
            and seat in self._free_cast_refused
            and self._free_cast_refused[seat] == turn
        ):
            # The refused retry above would be re-offered by the engine for as
            # long as this seat keeps saying Yes to "Continue casting?".
            del self._free_cast_refused[seat]
            kept = [o for o in selectable if not values[self._required_text(o, "option_id")]]
            if kept:
                selectable = kept
        # Copy-cast retry guard (liveness only). Mizzix's Mastery's overload loop
        # removes a copied card only when one was chosen, then asks "Continue to
        # choose copies and cast?" for as long as cards remain. A seat that just
        # chose none would be asked the same question again with the same answer,
        # so a Yes only restarts the loop without end; the chain ends here.
        if _COPY_CAST_CONTINUE_PROMPT.match(prompt) and seat in self._copy_cast_declined:
            self._copy_cast_declined.discard(seat)
            kept = [o for o in selectable if not values[self._required_text(o, "option_id")]]
            if kept:
                selectable = kept
        # Running-selection guard (liveness only). Once a seat picks no further creature, Slaughter
        # the Strong asks "End the selection" or "Continue the selection"; Continue only reopens the
        # pick, which this seat has just declined, so the selection ends here.
        # The same ask straight after a "Continue" (no pick in between) means nothing is left to
        # pick: Slaughter the Strong with every creature within the power already chosen asked
        # "Continue the selection" 50000 times (plan seed 6, game seed 206, pod 039).
        if seat in self._selection_ended or seat in self._selection_reopened:
            self._selection_ended.discard(seat)
            self._selection_reopened.discard(seat)
            kept = [o for o in selectable if values[self._required_text(o, "option_id")]]
            if kept:
                selectable = kept
        # Infinite-loop guard (liveness only). After fifteen turns of the stack that never empties
        # XMage asks every player in range "Draw game because of infinite looping?" and re-asks every
        # fifteen rounds after a No. Flourishing Defenses ("may" create an Elf Warrior for each -1/-1
        # counter) against Blowfly Infestation (a -1/-1 counter on the new token) looped 50000
        # decisions with a stack of 199 abilities, answered No each time (plan seed 1, game seed
        # 401, pod 017). CR 104.4b ends such a game as a draw; the Yes is kept.
        if _INFINITE_LOOP_PROMPT.match(prompt):
            kept = [o for o in selectable if values[self._required_text(o, "option_id")]]
            if kept:
                selectable = kept
        # Counter-kind guard (legality). Ion Storm's "remove a +1/+1 counter or remove a charge
        # counter" asks which kind to pay with; the cost fails unless a permanent holds that kind,
        # so only the kind the seat can pay is offered (the permanent is picked to match).
        paying_kind = self._paying_counter_kind(seat, state)
        if paying_kind is not None and _COUNTER_KIND_PROMPT.match(prompt):
            kept = [
                o
                for o in selectable
                if counter_cost_kinds(str(o.get("label", ""))) == (paying_kind,)
            ]
            if kept:
                selectable = kept
        # Re-target guard (liveness only): after a few re-aimed copies this turn the seat keeps the
        # targets (CR 707.10c: a copy keeps its original targets unless its controller changes them).
        retarget = _RETARGET_PROMPT.match(prompt) is not None
        retargeted_turn, retargeted = self._retarget_yes.get(seat, (None, 0))
        if retargeted_turn != turn:
            retargeted = 0
        retarget_blocked = retarget and retargeted >= _RETARGET_TURN_CAP
        if retarget_blocked:
            kept = [o for o in selectable if not values[self._required_text(o, "option_id")]]
            if kept:
                selectable = kept
        if selectable and len(selectable) != len(options):
            if retarget_blocked:
                _LOG.info(
                    "re-target guard: %d copies re-aimed this turn; keeping the targets of %r",
                    retargeted,
                    prompt,
                )
            elif life_yes_blocked:
                _LOG.info(
                    "phyrexian life guard: %d life already promised in this payment; declining %r",
                    life_promised,
                    prompt,
                )
            elif dig_yes_blocked:
                _LOG.info(
                    "life-dig guard: %d consecutive digs for %s; declining %r",
                    dug,
                    dig_key or "<unidentified source>",
                    prompt,
                )
            elif cost_yes_blocked:
                _LOG.info(
                    "optional-cost guard: the seat's mana cannot pay %s on top of the cost it "
                    "already owes; declining %r",
                    optional_cost,
                    prompt,
                )
            elif cap is not None:
                _LOG.info(
                    "multikicker guard: %d consecutive yes payments for %s/%s reached the "
                    "cap %d funded by the pilot's visible mana; declining",
                    answered_yes,
                    chain_key[0] or "<unidentified source>",
                    outcome,
                    cap,
                )
            options = selectable
        actions: list[PilotActionView] = []
        raw_by_stable_id: dict[str, str] = {}
        for option in options:
            value = values[self._required_text(option, "option_id")]
            aligned = (value and outcome in {"benefit", "benefit_to_controller"}) or (
                not value and outcome in DECLINE_ALIGNED_BOOLEAN_OUTCOMES
            )
            # Twin-stable: boolean value words are Rules-visible content.
            stable_id = f"boolean:{value}"
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
            actions.append(
                PilotActionView(
                    action_id=stable_id,
                    action_kind="card",
                    card_name=str(option.get("label", value)),
                    floor_value=0.8 if aligned else 0.35,
                    immediate_impact=0.45 if aligned else 0.15,
                    metadata={"boolean_value": value, "decision_outcome": outcome},
                )
            )
        decision = runtime.pilot.choose_action(self._pilot_state(runtime, state), actions, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no boolean decision")
        try:
            raw_id = raw_by_stable_id[decision.selected_action_id]
        except KeyError:
            raise FullGameProtocolError("pilot returned unknown stable boolean option") from None
        if _FREE_CAST_PROMPT.match(prompt):
            self._free_cast_last_yes[seat] = prompt if values[raw_id] else None
        elif _FREE_CAST_CONTINUE_PROMPT.match(prompt):
            last_yes = self._free_cast_last_yes.pop(seat, None)
            if last_yes is not None:
                failed.add(last_yes)
        self._free_cast_failed[seat] = (turn, failed)
        if retarget and values[raw_id]:
            self._retarget_yes[seat] = (turn, retargeted + 1)
        if _LIFE_DIG_PROMPT.match(prompt) and values[raw_id]:
            self._life_dig_yes[seat] = (dig_key, dug + 1)
        if life_prompt is not None and values[raw_id]:
            self._phyrexian_life_promised[seat] = life_promised + int(life_prompt.group(1))
        if offer is None:
            # Not a repeating offer: it is a single discretionary question, so
            # it clears any chain and is never capped.
            self._boolean_repeat.pop(seat, None)
        else:
            self._boolean_repeat[seat] = (
                chain_key,
                offer.ordinal,
                (answered_yes + 1) if values[raw_id] else 0,
            )
        chosen_label = next(
            (
                str(option.get("label", ""))
                for option in offered
                if option.get("option_id") == raw_id
            ),
            "",
        )
        if chosen_label.casefold() == _CONTINUE_SELECTION_LABEL:
            self._selection_reopened.add(seat)
        else:
            self._selection_reopened.discard(seat)
        return self._require_offered(raw_id, offered, "boolean decision")

    @staticmethod
    def _boolean_source_key(source_object: Any) -> str:
        """Identity of the ability a may-prompt came from.

        ``ability_original_id`` is the engine's original (card-definition)
        identity, identical in every process that casts the same card, so
        chain memory does not depend on a per-instance object id. A source
        reporting no original id falls back to its Rules-visible name, and
        only when neither is reported to the engine's per-instance
        ``source_object_id``; that last fallback only ever discriminates a
        chain against the immediately preceding decision in this same
        process, so it cannot desynchronize twins.
        """
        if not isinstance(source_object, dict):
            return ""
        original = str(source_object.get("ability_original_id") or "").strip()
        if original:
            return f"original:{original}"
        name = str(source_object.get("source_name") or "").strip()
        if name:
            return f"name:{name.casefold()}"
        instance = str(source_object.get("source_object_id") or "").strip()
        return f"instance:{instance}" if instance else ""

    def _boolean_yes_cap(
        self, offer: _MultikickerOffer, actor: dict[str, Any], source_object: object = None
    ) -> int:
        """How many multikicker payments the pilot's mana can fund in all.

        The engine's affordability check covers a single payment, so the Lab
        reads the pilot-visible total instead: available mana less the cost of
        the spell itself, divided by what one payment of the cost the prompt
        prints is worth. The spell's own cost is paid out of the same mana, so
        leaving it out let a chain promise more payments than the mana could
        fund and the whole cast was reversed at the payment. A prompt that
        prints no mana symbol states no per-payment value to divide by, so one
        further payment is assumed -- the minimum a bound needs to hold.
        """
        return max(
            1,
            (self._available_mana(actor) - self._spell_base_cost(source_object))
            // (offer.per_payment or 1),
        )

    @staticmethod
    def _spell_base_cost(source_object: object) -> int:
        """Mana value of the spell a cost prompt belongs to; 0 when it is not a known spell."""
        if not isinstance(source_object, dict) or source_object.get("ability_type") != "spell":
            return 0
        facts = card_facts(str(source_object.get("source_name") or ""))
        return int(facts.mana_value) if facts is not None else 0

    def _decide_pile(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        context: dict[str, Any],
        rng: random.Random,
    ) -> str:
        if not options:
            raise FullGameProtocolError("pile decision has no legal options")
        outcome = str(context.get("outcome", "benefit")).casefold()
        benefit = outcome not in {"detriment", "detriment_to_controller"}
        actions: list[PilotActionView] = []
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[str, int] = {}
        for option in options:
            metadata = option.get("metadata")
            cards = metadata.get("cards", []) if isinstance(metadata, dict) else []
            size = len(cards) if isinstance(cards, list) else 0
            scaled = min(2.0, size / 4.0)
            # Twin-stable: pile identity is its Rules-visible content
            # (sorted member names), never engine UUIDs.
            names: list[str] = []
            if isinstance(cards, list):
                for card in cards:
                    if isinstance(card, dict):
                        names.append(str(card.get("name", "")).casefold())
                    else:
                        names.append(str(card).casefold())
            base = f"pile:{size}:{'+'.join(sorted(names))}"
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
            actions.append(
                PilotActionView(
                    action_id=stable_id,
                    action_kind="card",
                    card_name=str(option.get("label", "Pile")),
                    floor_value=(0.4 + scaled * 0.25) if benefit else max(0.0, 0.9 - scaled * 0.25),
                    immediate_impact=(0.3 + scaled * 0.2)
                    if benefit
                    else max(0.0, 0.7 - scaled * 0.2),
                    metadata={"pile_size": size, "decision_outcome": outcome},
                )
            )
        decision = runtime.pilot.choose_action(self._pilot_state(runtime, state), actions, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no pile decision")
        try:
            raw_id = raw_by_stable_id[decision.selected_action_id]
        except KeyError:
            raise FullGameProtocolError("pilot returned unknown stable pile option") from None
        return self._require_offered(raw_id, options, "pile decision")

    def _decide_counter_cost_objects(
        self,
        seat: int,
        state: dict[str, object],
        options: list[dict[str, object]],
        min_selections: int,
    ) -> list[str] | None:
        """Pick the permanents that pay a "remove N counters" cost: biggest pile first.

        XMage removes counters of one type from each chosen permanent and asks only how many when
        the pile holds several, so the cost is paid when the chosen piles add up to N. The seat
        takes the largest pile first and stops once N are covered (None: not such a payment).
        """
        wanted = self._paying_counters(seat)
        if wanted is None:
            return self._decide_kind_cost_object(seat, state, options, min_selections)
        stacks = own_counter_stacks(state, str(state.get("actor_id", "")))
        if any(str(option.get("option_id")) not in stacks for option in options):
            return None
        picked = self._counter_cost_progress.setdefault(seat, {})
        offered = [
            (stacks[str(option.get("option_id"))], index)
            for index, option in enumerate(options)
            if str(option.get("option_id")) not in picked
        ]
        if min_selections == 0 and (sum(picked.values()) >= wanted or not offered):
            return []
        if not offered:
            return None
        stack, index = max(offered, key=lambda entry: (entry[0], -entry[1]))
        if min_selections == 0 and stack == 0:
            return []
        option_id = self._required_text(options[index], "option_id")
        picked[option_id] = stack
        return [option_id]

    def _decide_kind_cost_object(
        self,
        seat: int,
        state: dict[str, object],
        options: list[dict[str, object]],
        min_selections: int,
    ) -> list[str] | None:
        """Pick the permanent that pays "remove a K counter from a permanent you control".

        XMage offers every permanent the player controls and fails the activation when the one
        picked holds no such counter, so the seat picks the permanent with the biggest pile of the
        kind it is paying with (None: not such a payment).
        """
        kind = self._paying_counter_kind(seat, state)
        if kind is None or min_selections < 1:
            return None
        held = own_counters_by_kind(state, str(state.get("actor_id", "")))
        ids = [str(option.get("option_id")) for option in options]
        if any(option_id not in held for option_id in ids):
            return None
        best = max(range(len(ids)), key=lambda index: (held[ids[index]].get(kind, 0), -index))
        return [ids[best]] if held[ids[best]].get(kind, 0) > 0 else None

    def _counter_type_for_cost(
        self,
        seat: int,
        state: dict[str, object],
        options: list[dict[str, object]],
        prompt: str,
    ) -> str | None:
        """The counter type to remove from a permanent that pays a cost: its biggest pile."""
        if self._paying_counters(seat) is None:
            return None
        found = _COUNTER_CHOICE_PROMPT.search(prompt)
        if found is None:
            return None
        piles = named_counter_piles(
            state, str(state.get("actor_id", "")), found.group("name").strip()
        )
        if not piles:
            return None
        best = max(
            range(len(options)),
            key=lambda index: (
                piles.get(str(options[index].get("label", "")).casefold(), 0),
                -index,
            ),
        )
        return self._require_offered(
            self._required_text(options[best], "option_id"), options, "counter option"
        )

    def _decide_choice(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        context: dict[str, Any],
        rng: random.Random,
        *,
        prompt: str = "",
    ) -> str:
        """Named choice: mana colour, protection colour, creature type, ...

        A mana colour pick serves the cost still being paid, then the hand; a
        named choice follows the board. When nothing distinguishes the options
        the generic semantic ranking decides, as before.
        """
        if not options:
            raise FullGameProtocolError("choice decision has no legal options")
        seat = int(state.get("seat", -1)) + 1
        paying = self._counter_type_for_cost(seat, state, options, prompt)
        if paying is not None:
            return paying
        options = self._alternative_costs_that_pay(state, options, prompt)
        actor = self._actor(state)
        hand = actor.get("hand")
        battlefield = actor.get("battlefield")
        hand_names = [
            str(item.get("name", ""))
            for item in (hand if isinstance(hand, list) else [])
            if isinstance(item, dict) and item.get("name")
        ]
        text = f"{prompt} {context.get('outcome', '')}".casefold()
        if "mana" in text:
            options = self._colours_that_complete(seat, options)
            identity: set[str] = set()
            own_id = str(state.get("actor_id", ""))
            status = state.get("commander_status")
            for entry in status if isinstance(status, list) else ():
                if isinstance(entry, dict) and str(entry.get("owner_id")) == own_id:
                    facts = card_facts(str(entry.get("name") or ""))
                    if facts is not None:
                        identity |= facts.color_identity
            # A payment inside the payment (a mana ability with a cost of its own) leaves only
            # its generic cost behind; the colour it adds must serve the payment around it:
            # Hall of Oracles picked red for a Shriekmaw that needed {B}, and the cast was
            # cancelled (#989 phase 6).
            unpaid = self._last_unpaid_mana.get(seat, "")
            if not needed_colors(unpaid):
                unpaid = self._outer_unpaid_mana.get(seat) or unpaid
            ranked = color_choice_rank(
                options,
                unpaid_mana=unpaid,
                hand_names=hand_names,
                identity=identity,
            )
        else:
            ranked = named_choice_rank(
                options,
                prompt=prompt,
                state=state,
                own_names=[
                    str(item.get("name", ""))
                    for item in (battlefield if isinstance(battlefield, list) else [])
                    if isinstance(item, dict)
                ],
            )
        scores = [score for score, _label in ranked]
        if not scores or max(scores) <= 0.0 or len(set(scores)) == 1:
            return self._decide_semantic_option(runtime, state, options, rng)
        best = max(
            range(len(options)),
            key=lambda index: (ranked[index][0], -index),
        )
        return self._require_offered(
            self._required_text(options[best], "option_id"), options, "choice option"
        )
