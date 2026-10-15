"""Mulligans, targets, modes, may-prompts, piles and named choices."""

from __future__ import annotations

import random
from typing import Any

from commander_lab.agents.card_knowledge import card_facts
from commander_lab.models import (
    PilotActionView,
)

from ..full_game_pilot_views import (
    color_choice_rank,
    named_choice_rank,
    sweep_mode_net,
    target_object_bonus,
)
from .common import (
    _LOG,
    DECLINE_ALIGNED_BOOLEAN_OUTCOMES,
    FullGameProtocolError,
    _multikicker_offer,
    _MultikickerOffer,
    _RuntimePilot,
)
from .payment import _PaymentDecisions


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
        outcome = str((request.get("context") or {}).get("outcome", "neutral")).casefold()
        pilot_state = self._pilot_state(runtime, state)
        # Twin-stable target identities: (zone, zone_index) pins the same
        # physical card across fresh processes (identical zone-event
        # streams); occurrence fallback is content-keyed and order-free.
        # Raw engine ids never order or identify pilot inputs.
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[str, int] = {}
        ranked: list[tuple[float, str, str]] = []
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
            action = self._target_action(option, state, outcome).model_copy(
                update={"action_id": stable_id}
            )
            breakdown = runtime.pilot.evaluate_action(pilot_state, action)
            score = (
                breakdown.total_utility
                + self._target_alignment(action, state, outcome)
                + target_object_bonus(
                    option,
                    state,
                    outcome,
                    own_stack_names=self._own_stack_names(runtime.binding.seat),
                )
            )
            ranked.append((score, action.card_name, stable_id))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

        if max_selections <= 0:
            return []
        if outcome in {"benefit", "benefit_to_controller"}:
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
        nets = [sweep_mode_net(str(option.get("label", "")), state, actor_id) for option in candidates]
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
            cap = self._boolean_yes_cap(offer, self._actor(state))
        selectable = [
            option
            for option in options
            if not (
                values[self._required_text(option, "option_id")]
                and cap is not None
                and answered_yes >= cap
            )
        ]
        if selectable and len(selectable) != len(options):
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

    def _boolean_yes_cap(self, offer: _MultikickerOffer, actor: dict[str, Any]) -> int:
        """How many further multikicker payments the pilot's mana can fund.

        The engine's affordability check covers a single payment, so the Lab
        reads the pilot-visible total instead: available mana divided by what
        one payment of the cost the prompt prints is worth. A prompt that
        prints no mana symbol states no per-payment value to divide by, so one
        further payment is assumed -- the minimum a bound needs to hold.
        """
        return max(1, self._available_mana(actor) // (offer.per_payment or 1))

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
            identity: set[str] = set()
            own_id = str(state.get("actor_id", ""))
            status = state.get("commander_status")
            for entry in status if isinstance(status, list) else ():
                if isinstance(entry, dict) and str(entry.get("owner_id")) == own_id:
                    facts = card_facts(str(entry.get("name") or ""))
                    if facts is not None:
                        identity |= facts.color_identity
            ranked = color_choice_rank(
                options,
                unpaid_mana=self._last_unpaid_mana.get(seat, ""),
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
