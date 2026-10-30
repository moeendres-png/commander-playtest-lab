"""Mana payment, X announcements and numeric choices."""

from __future__ import annotations

import itertools
import math
import random
import re
from collections.abc import Mapping, Sequence
from typing import Any

from commander_lab.agents.card_knowledge import card_facts
from commander_lab.models import (
    PilotActionView,
)

from ..full_game_pilot_additional_cost import additional_mana_cost, reveal_alternative_in_hand
from ..full_game_pilot_mana_hold import (
    HOLD_TURNS_IN_A_ROW,
    held_instants,
    holds_in_a_row,
    is_plan_of_the_turn,
    own_main_phase,
    thin_board,
)
from ..full_game_pilot_payment_plan import (
    can_pay,
    colour_letter,
    completing_options,
    completing_outcomes,
)
from ..full_game_pilot_target_discount import (
    board_lowers_costs,
    damaged_opposing_creatures,
    damaged_target_discount,
)
from ..full_game_pilot_views import (
    best_cost_counter_kind,
    counter_cost_number,
    is_x_counter_pile_cost,
    players,
    tap_creature_cost_unpayable,
    x_counter_pile_cap,
)
from .common import (
    _LOG,
    _MANA_COST_COLORS,
    _MANA_SYMBOL,
    FullGameProtocolError,
    _alternative_cost_of,
    _alternative_cost_spell,
    _cost_amount,
    _mana_cost_text,
    _option_non_x_mana_value,
    _printed_spell_cost,
    _RuntimePilot,
    mana_needed_letters,
    mana_payment_fit,
    mana_produced_letters,
    mana_x_prompt_symbols,
    offers_mana_ability,
    option_x_counter_cap,
    option_x_tap_cap,
    tap_cost_needs_permanent,
    x_tap_prompt_cap,
)
from .state import _PolicyState

# Sources whose "pay any amount of {E}" question leads into an engine path the bridge keeps
# closed. Casefolded names as the bridge reports them in ``source_name``.
_UNSUPPORTED_ENERGY_PAYMENT_SOURCES = frozenset({"vault 112: sadistic simulation"})
# "Choose how many counters (+1/+1) to remove from <name> as payment": the engine's question
# when a "remove N counters" cost takes several counters from one permanent.
_COUNTER_COUNT_PROMPT = re.compile(r"Choose how many counters \(")
# "Announce the value for {X} (+1/+1 counters to remove)": the X of a cost that removes that many
# counters (Hierophant Bio-Titan's Frenzied Metabolism, Haruspex's mana ability).
_COUNTERS_TO_REMOVE_PROMPT = re.compile(r"\((?P<kind>[^()]+?) counters? to remove\)")
# "you may pay any amount of mana" (Minds Aglow, Mana-Charged Dragon) and the "pays {X}" of a
# counter-unless or reward clause: ``ManaUtil.playerPaysXGenericMana`` announces the amount with
# the engine's 2147483647 ceiling and no cost. An amount the seat cannot fund fails at the
# payment, the whole payment reverses and nothing was paid, so a seat that asks for the ceiling
# never paid anything.
_PAY_ANY_AMOUNT_PROMPT = re.compile(r"\AChoose how much mana to pay\Z")
# Spells that do something at X = 0, so a cast with nothing left for X is a real play: Chalice of
# the Void (counters {0} spells), Engineered Explosives (destroys tokens and {0} permanents).
_ZERO_X_SPELLS = frozenset({"chalice of the void", "engineered explosives"})
# An activated ability that adds mana ("{T}: Add {R}."): the cost, a colon, "Add".
_ADDS_MANA_RULE = re.compile(r":\s*add\s", re.IGNORECASE)
# A loyalty ability ("+1: Add {R}{R}.", Chandra, Torch of Defiance) is never a mana ability (CR
# 605.1a): the engine does not offer it inside a payment, so it is no source for one (#1067; 0 of
# 10,539 recorded payment prompts offered one).
_LOYALTY_COST = re.compile(r"^\s*(?:[+\u2212\u2013-]\s*)?(?:\d+|x)\s*:", re.IGNORECASE)


def _option_spends_own_source(label: str, metadata: Mapping[str, object]) -> bool:
    """True if this priority activation taps or sacrifices its own source (#1041).

    Derived from engine-reported flags (requires_tap_source, requires_sacrifice_source)
    or from the ability's cost prefix before the colon.
    """
    if (
        metadata.get("requires_tap_source") is True
        or metadata.get("requires_sacrifice_source") is True
    ):
        return True
    cost = label.casefold().split(" — ", 1)[-1].split("&mdash;", 1)[-1].partition(":")[0]
    if "{t}" in cost or "sacrifice {this}" in cost or "sacrifice this " in cost:
        return True
    if "sacrifice " in cost:
        source_name = str(metadata.get("source_name") or "").strip().casefold()
        if source_name and (
            f"sacrifice {source_name}" in cost
            or f"sacrifice {source_name.split(',')[0].strip()}" in cost
        ):
            return True
    return False


class _PaymentDecisions(_PolicyState):
    def _paying_counters(self, seat: int) -> int | None:
        """How many counters the "remove N counters ..." cost this seat is paying takes."""
        label = self._last_priority_label.get(seat)
        if label is None:
            return None
        number = counter_cost_number(label)
        if number is not None:
            return number
        if is_x_counter_pile_cost(label):
            # The cost takes the X this seat announced for the activation.
            announced = self._failed_x_announcements.get(seat, {})
            return next(iter(announced.values())) if len(announced) == 1 else None
        # A cast's own additional cost takes the counters its announced X names.
        reserved = self._reserved_counters.get(seat, {}).get(
            self._last_priority_source.get(seat, "")
        )
        return reserved[1] if reserved is not None else None

    def _reserve_counters(self, seat: int, source_object: object, prompt: str, chosen: int) -> None:
        """Keep the counters an announced "(K counters to remove)" X sets aside for the cast."""
        found = _COUNTERS_TO_REMOVE_PROMPT.search(prompt)
        if found is None or chosen <= 0 or not isinstance(source_object, dict):
            return
        source = str(source_object.get("source_object_id") or "")
        if source:
            self._reserved_counters.setdefault(seat, {})[source] = (
                found.group("kind").casefold(),
                chosen,
            )

    def _spends_counters_the_cast_reserves(self, seat: int, option: Mapping[str, object]) -> bool:
        """Whether this mana ability removes the counters the cast being paid for still has to remove.

        Hierophant Bio-Titan announced X = 3 counters to remove (3 of them on The Swarmlord and
        Haruspex), then paid {1} with Haruspex's "Remove X +1/+1 counters from {this}: Add X
        mana". The cost found only the Swarmlord's 2 counters left and the cast was reversed
        (plan seed 29, game seed 29, pod 000). The counters pay the cost; mana comes from
        elsewhere or the payment is cancelled.
        """
        reserved = self._reserved_counters.get(seat, {}).get(
            self._last_priority_source.get(seat, "")
        )
        if reserved is None:
            return False
        label = str(option.get("label", "")).casefold()
        return "remove" in label and f"{reserved[0]} counter" in label

    def _paying_counter_kind(self, seat: int, state: dict[str, object]) -> str | None:
        """The counter kind a "remove a K counter from a permanent you control" cost takes now."""
        label = self._last_priority_label.get(seat)
        if label is None:
            return None
        return best_cost_counter_kind(label, state, str(state.get("actor_id", "")))

    @staticmethod
    def _priority_awaits_mana(option: dict[str, Any]) -> bool:
        """True when the only proven obstacle to an action is the actor's pool.

        Engine-native cost facts only: the engine's own ``Mana.enough`` verdict
        is False and the activation also spends its own source. Paying from
        another source may still fail, which is exactly why the pilot -- not
        the Lab -- decides whether to try; the engine re-validates the
        activation and the priority no-progress guard bounds any repetition.
        A tap cost on an already tapped source, or an untap cost on an
        already untapped one, is impossible whatever mana exists and never
        reaches this route.
        """
        metadata = option.get("metadata")
        if not isinstance(metadata, dict):
            return False
        if metadata.get("pool_covers_mana_cost") is not False:
            return False
        source_tapped = metadata.get("source_tapped")
        if metadata.get("requires_tap_source") is True and source_tapped is True:
            return False
        if metadata.get("requires_untap_source") is True and source_tapped is False:
            return False
        return any(
            metadata.get(key) is True
            for key in (
                "requires_tap_source",
                "requires_sacrifice_source",
                "requires_untap_source",
            )
        )

    @staticmethod
    def _same_source(left: dict[str, Any], right: dict[str, Any]) -> bool:
        """Whether two engine options are activations of the same permanent.

        Two permanents of the same card are two different sources: a second
        Hedron Archive can pay for the first one's ``{2}``. So object ids
        decide whenever both sides report one, and the Rules-visible name is
        consulted only when at least one side does not.
        """
        left_meta = left.get("metadata")
        right_meta = right.get("metadata")
        left_meta = left_meta if isinstance(left_meta, dict) else {}
        right_meta = right_meta if isinstance(right_meta, dict) else {}
        left_id = str(left_meta.get("source_object_id") or "")
        right_id = str(right_meta.get("source_object_id") or "")
        if left_id and right_id:
            return left_id == right_id
        left_name = str(left_meta.get("source_name") or "")
        right_name = str(right_meta.get("source_name") or "")
        return bool(left_name) and left_name == right_name

    def _priority_mana_for(
        self,
        deferred: dict[str, Any],
        funding: list[dict[str, Any]],
        pass_id: str,
    ) -> str:
        """Answer a needs-mana-first intent with one mana ability from elsewhere.

        The funding source must not be the action's own permanent: paying
        Hedron Archive's ``{2}`` by tapping Hedron Archive would consume the
        source its own ``{T}, Sacrifice`` cost needs. Ranking is
        ``mana_payment_fit`` against the action's own mana cost, so the pilot's
        intent is answered with the mana that cost actually names; a source
        that cannot pay any part of that cost is not spent on it, and when no
        source can the Lab passes instead. The engine alone decides whether
        the resulting activation succeeds.
        """
        metadata = deferred.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        cost_text = _mana_cost_text(meta)
        # Twin-stable ordering: content-derived keys only. Equal fit and equal
        # label mean interchangeable sources, so the engine's own offered order
        # breaks the tie -- never a per-process engine UUID.
        usable = [
            option
            for option in funding
            if not self._same_source(deferred, option)
            and mana_payment_fit(str(option.get("label", "")), cost_text) > 0
        ]
        ranked = sorted(
            usable,
            key=lambda option: (
                -mana_payment_fit(str(option.get("label", "")), cost_text),
                str(option.get("label", "")).casefold(),
            ),
        )
        if not ranked:
            _LOG.info(
                "pilot chose %s, which needs mana first, but no other source can "
                "pay for it; passing priority",
                str(meta.get("source_name") or deferred.get("label") or "action"),
            )
            return pass_id
        chosen = self._required_text(ranked[0], "option_id")
        _LOG.info(
            "pilot chose %s, which needs mana first; paying with %s",
            str(meta.get("source_name") or deferred.get("label") or "action"),
            str(ranked[0].get("label", "mana ability")),
        )
        return chosen

    def _priority_action_affordable(
        self, option: dict[str, Any], state: dict[str, Any], *, pool_verified: bool = False
    ) -> bool:
        """Pilot-side discretionary ranking among engine-authorized options.

        Returns False only when engine-native cost facts prove the action
        cannot be funded from free resources: a tap cost on an already
        tapped source, an untap cost on an untapped source, or mana costs
        the current pool cannot cover (``pool_covers_mana_cost`` is the
        engine's own ``Mana.enough`` verdict, projected losslessly by the
        bridge) on an action that also taps or sacrifices its own source,
        and a Crew activation whose cost the engine's own check says the
        other creatures cannot pay (``crew_payable_without_source``).
        The mana case is the one a pool shortfall proves: paying the mana
        can consume the very source the tap/sacrifice cost needs (a fetch
        with ``{1}, {T}, Sacrifice`` and one untapped land). Any other
        action is paid through the engine's own mana-payment decisions from
        untapped sources, which the engine already counted when it offered
        the action, so an empty pool proves nothing there; withholding it
        kept every spell with a mana cost out of the pilot's reach unless
        mana had been floated first. Anything unknown means affordable.

        This is pilot choice, not a legality verdict: withheld options stay
        engine-offered, the pilot simply selects pass/another legal action
        instead, and the engine re-validates whatever is selected (a
        mid-payment cancel aborts to pass natively). No card names, no invented
        actions, and the only labels read are the "tap N untapped creatures you
        control" cost and a mana ability's "Tap X untapped ... you control"
        cost, which the bridge does not project as facts. A False
        result from a pool shortfall on an action that spends its own source is
        decided by _priority_awaits_mana: it is re-offered as needs-mana-first
        intent. Any other False result (a tapped source, a Crew the other
        creatures cannot pay, a tap-creature cost with nothing to tap) stays
        withheld.

        ``pool_verified`` is set by the payment model once it has read the pool itself and found
        the ability's cost covered: the flag counts a hybrid pip such as ``{R/W}`` as both of its
        colours, so a pool holding one of them reads as short (Rugged Prairie with a red mana
        floating). It lifts only that flag verdict, never a tapped source or a Crew check.
        """
        metadata = option.get("metadata")
        if not isinstance(metadata, dict):
            return True
        # A "tap an untapped creature you control" cost beside the source's own {T}: the engine
        # offers it with the source as the only candidate and fails it once chosen.
        if tap_creature_cost_unpayable(
            str(option.get("label", "")), str(metadata.get("source_object_id") or ""), state
        ):
            return False
        # #920: a mana ability that taps X untapped permanents and has none to tap makes no
        # mana for its other costs (Hazel of the Rootbloom pays 2 life for X = 0).
        label = str(option.get("label", ""))
        if (
            metadata.get("ability_type") == "activated_mana"
            and "tap x untapped" in label.casefold()
            and option_x_tap_cap(label, metadata, self._actor(state).get("battlefield")) == 0
        ):
            return False
        if metadata.get("requires_tap_source") is True and metadata.get("source_tapped") is True:
            return False
        if metadata.get("requires_untap_source") is True and metadata.get("source_tapped") is False:
            return False
        # #920: the engine's own crew-cost check with the Vehicle set aside
        # (``crew_payable_without_source``). The engine offers Crew when the
        # Vehicle's own power would pay for it, which no crew can ever use.
        if metadata.get("crew_payable_without_source") is False:
            return False
        if metadata.get("pool_covers_mana_cost") is not False or pool_verified:
            return True
        return not (
            metadata.get("requires_tap_source") is True
            or metadata.get("requires_sacrifice_source") is True
        )

    def _spends_the_activations_own_source(self, seat: int, option: Mapping[str, object]) -> bool:
        """Whether this mana ability is the source of the {T} ability being paid for (#920).

        Plan seed 15, game seed 115, pod 026: Alchemist's Refuge's ``{G}{U}, {T}: You may cast
        spells this turn as though they had flash`` was paid partly by tapping the Refuge for
        {C}. The mana cost is paid first, so the ability's own ``{T}`` then found its source
        tapped, the activation was reversed and the game stopped. Same cause as the sacrifice
        cost of #952, read from the label of the action the seat chose at priority.
        """
        payer = self._payment_source.get(seat)
        metadata = option.get("metadata")
        if (
            not payer
            or self._last_priority_source.get(seat) != payer
            or not isinstance(metadata, dict)
            or str(metadata.get("source_object_id") or "") != payer
        ):
            return False
        cost = self._last_priority_label.get(seat, "").casefold().split(" — ", 1)[-1]
        return "{t}" in cost.partition(":")[0]

    def _spends_a_permanent_the_tap_cost_needs(
        self, seat: int, option: Mapping[str, object], state: dict[str, object]
    ) -> bool:
        """Whether this mana ability taps a permanent the activation's tap cost still needs (#920).

        The ability's mana is paid before its "Tap X untapped artifacts you control" part, so the
        artifacts kept untapped are the ones that cost can use (Trazyn the Infinite, plan seed 3,
        game seed 203, pod 026). The announced X comes from the seat's own announce frame.
        """
        payer = self._payment_source.get(seat)
        metadata = option.get("metadata")
        if (
            not payer
            or self._last_priority_source.get(seat) != payer
            or not isinstance(metadata, dict)
        ):
            return False
        candidate = str(metadata.get("source_object_id") or "")
        if not candidate or candidate == payer:
            return False
        return tap_cost_needs_permanent(
            self._last_priority_label.get(seat, ""),
            self._failed_x_announcements.get(seat, {}).get(payer),
            payer,
            candidate,
            self._actor(state).get("battlefield"),
        )

    @staticmethod
    def _floats_mana_only(meta: dict[str, Any]) -> bool:
        """Whether activating this in a priority window only floats mana.

        True when the bridge's cost facts prove the ability costs nothing
        beyond spending its own source: that activation merely adds mana to
        the pool, which the step will empty (CR 106.4) without the window
        offering anything new to spend it on. Spending the source is part of
        producing the mana, not something the window could have spent it on:
        Treasure and Lotus Petal ("{T}, Sacrifice this: Add one mana") are
        pure floaters and must keep the flag, or every window spends the
        board's Treasures for mana that empties at the end of the step. A mana
        ability carrying its own mana cost (Agent of Stromgald's
        ``{R}: Add {B}``) buys something and is not scored below passing.
        Absent cost facts are unknown, and unknown keeps the conservative
        flag.

        Known limitation, not fixed here: ``requires_sacrifice_source`` is
        reported only for ``SacrificeSourceCost`` (see
        ``enrichAbilityCostFacts``), so an ability that sacrifices *another*
        permanent (Ashnod's Altar, "Sacrifice a creature: Add {C}{C}",
        answered in response to removal) reports no cost fact at all and keeps
        the float-only flag until the bridge emits a fact for it.
        """
        amounts: list[float] = []
        for key, _ in _MANA_COST_COLORS:
            amount = _cost_amount(meta, key)
            if amount is None:
                return True
            amounts.append(amount)
        generic = _cost_amount(meta, "mana_cost_generic")
        if generic is None:
            return True
        if generic > 0 or any(amount > 0 for amount in amounts):
            return False
        return meta.get("requires_untap_source") is not True

    def _priority_mana_action(
        self, option: dict[str, Any], state: dict[str, Any]
    ) -> PilotActionView:
        metadata = option.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        source_name = str(meta.get("source_name") or option.get("label") or "Mana ability")
        return PilotActionView(
            action_id=self._required_text(option, "option_id"),
            action_kind="card",
            card_name=source_name,
            mana_cost=0.0,
            floor_value=0.5,
            immediate_impact=0.35,
            remaining_mana=self._actor_mana(self._actor(state)),
            metadata={
                "xmage_option_type": "mana_ability",
                "is_mana_ability": True,
                # Offered in a priority window, not inside a payment. True only
                # when the bridge's cost facts show the activation costs
                # nothing beyond tapping its own source (see
                # _floats_mana_only and STANDALONE_MANA_ABILITY_UTILITY).
                "floats_mana_only": self._floats_mana_only(meta),
            },
        )

    def _available_mana(self, actor: dict[str, Any]) -> int:
        """Mana the pilot can see it could pay with right now.

        The pool, plus one payment for every untapped permanent that offers a
        mana ability. A permanent entry that reports no machine-readable mana
        fact at all is read as a land when its name says so, which is the
        conservative fallback; a permanent that reports nothing readable and
        is not a land contributes nothing rather than a guess.
        """
        total = int(self._actor_mana(actor))
        battlefield = actor.get("battlefield")
        if not isinstance(battlefield, list):
            return total
        for item in battlefield:
            if not isinstance(item, dict) or item.get("tapped") is True:
                continue
            offers = self._permanent_offers_mana(item)
            if offers is None:
                offers = self._looks_like_basic_land(str(item.get("name") or ""))
            if offers:
                total += 1
        return total

    @staticmethod
    def _permanent_offers_mana(permanent: dict[str, Any]) -> bool | None:
        """Whether a battlefield entry states that it offers mana.

        True/False when the entry carries a machine-readable fact, None when
        it carries none and the caller must fall back.
        """
        for key in ("is_mana_ability", "mana_ability"):
            value = permanent.get(key)
            if isinstance(value, bool):
                return value
        rules = permanent.get("abilities")
        if isinstance(rules, list):
            return any(
                isinstance(rule, str)
                and "add" in rule.casefold()
                and ("{" in rule or "mana" in rule.casefold())
                for rule in rules
            )
        return None

    @staticmethod
    def _visible_mana_offer(actor: Mapping[str, object]) -> list[dict[str, object]] | None:
        """The seat's pool and untapped mana abilities laid out like an engine payment prompt.

        Read from the public text of the seat's own board, the same facts ``_mana_budget`` counts.
        None when the board is not reported, or an untapped permanent states no abilities at all.
        A summoning-sick creature counts as usable, so the picture errs towards more mana.
        """
        battlefield = actor.get("battlefield")
        if not isinstance(battlefield, list):
            return None
        offer: list[dict[str, object]] = []
        pool = actor.get("mana_pool")
        if isinstance(pool, Mapping):
            for kind, amount in pool.items():
                if isinstance(amount, int) and amount > 0:
                    offer.append(
                        {
                            "option_type": "mana_pool",
                            "option_id": f"pool:{kind}",
                            "metadata": {"mana_type": str(kind), "mana_available": amount},
                        }
                    )
        for item in battlefield:
            if not isinstance(item, dict) or item.get("tapped") is True:
                continue
            if item.get("face_down") is True:
                continue
            rules = item.get("abilities")
            if not isinstance(rules, list):
                # A permanent that states no abilities may still make mana: not judged.
                return None
            name = str(item.get("name") or "")
            source = str(item.get("object_id") or name)
            for index, rule in enumerate(rules):
                # Not ``offers_mana_ability``: that reader is conservative for a budget (it misses
                # "three mana of any one color"), and a missed source reads as a shortfall here.
                if (
                    isinstance(rule, str)
                    and _ADDS_MANA_RULE.search(rule)
                    and not _LOYALTY_COST.match(rule)
                ):
                    offer.append(
                        {
                            "option_type": "mana_ability",
                            "option_id": f"{source}:{index}",
                            "label": f"{name} — {rule.replace('{this}', 'this permanent')}",
                            "metadata": {"source_object_id": source},
                        }
                    )
        return offer

    def _cost_cannot_be_paid(
        self, state: dict[str, object], extra: str, source_object: object = None
    ) -> bool:
        """Whether paying ``extra`` (an optional cost) can only fail the payment it joins.

        A kicker, a multikicker or a "you may pay" trigger is answered Yes by the pilot's ranking
        alone; the engine checks the one cost it prints, not that plus the spell it belongs to.
        A Nullpriest of Oblivion kicked with three lands is cast for {1}{B}{3}{B}, the payment
        is cancelled, and the unkicked creature is not cast either. True only when the seat's
        own mana provably falls short of the whole cost while the spell itself could be paid:
        anything the model cannot read, and a spell whose cost can change (convoke, delve, "costs
        {2} less"), is left to the pilot.
        """
        offer = self._visible_mana_offer(self._actor(state))
        if offer is None:
            return False
        base = ""
        if isinstance(source_object, dict) and source_object.get("ability_type") == "spell":
            printed = _printed_spell_cost(str(source_object.get("source_name") or ""))
            if printed is None or can_pay(offer, printed) is not True:
                return False
            base = printed
        return can_pay(offer, base + extra) is False

    def _discount_cast_without_target(
        self, option: Mapping[str, object], state: dict[str, object]
    ) -> bool:
        """Whether a cast is offered only for a discount no creature on the table can give.

        Bitter Downfall costs {3} less against a creature dealt damage this turn, and the engine
        offers it whenever that price is payable. With the full {3}{B} out of reach and no
        opposing creature damaged, the target can only be an undamaged one, and the payment
        is cancelled after the pilot spent decisions on it. True only when the model proves the
        full price short and finds no damaged target; a cost it cannot read is left to the pilot.
        """
        metadata = option.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("ability_type") != "spell":
            return False
        discount = damaged_target_discount(str(metadata.get("source_name") or ""))
        if discount is None:
            return False
        actor_id = str(state.get("actor_id") or "")
        offer = self._visible_mana_offer(self._actor(state))
        if (
            offer is None
            or board_lowers_costs(state, actor_id)
            or can_pay(offer, discount.full) is not False
        ):
            return False
        return not damaged_opposing_creatures(state, actor_id) or (
            can_pay(offer, discount.reduced) is False
        )

    def _extra_cost_cast_unpayable(
        self, option: Mapping[str, object], state: dict[str, object]
    ) -> bool:
        """Whether a cast is offered although its mandatory extra mana cannot be paid (#1067).

        Louisoix's Sacrifice ({U}, "sacrifice a legendary creature or pay {2}") is offered while
        the {U} is payable; the {2} is asked afterwards, and the payment is cancelled with the
        first mana gone. True only when the model proves the printed price plus the extra mana
        short and the hand holds no card to reveal in its place; a cost it cannot read, a cast
        for another price (flashback, an alternative cost) and a board with a cost reducer are
        left to the pilot.
        """
        metadata = option.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("ability_type") != "spell":
            return False
        label = str(option.get("label") or "").casefold()
        if "cast " not in label or any(word in label for word in ("flashback", " using ", "free")):
            return False
        name = str(metadata.get("source_name") or "")
        extra = additional_mana_cost(name)
        printed = _printed_spell_cost(name) if extra is not None else None
        actor_id = str(state.get("actor_id") or "")
        offer = self._visible_mana_offer(self._actor(state))
        if extra is None or printed is None or offer is None or board_lowers_costs(state, actor_id):
            return False
        if can_pay(offer, printed + extra.mana) is not False:
            return False
        if extra.reveal_kind is None:
            return True
        return reveal_alternative_in_hand(state, actor_id, name, extra.reveal_kind) is False

    def _targets_the_discount_pays_for(
        self,
        state: dict[str, object],
        source_name: str,
        options: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """The targets of a discounted spell that keep its price payable.

        With the full price out of the seat's reach, only an opposing creature that was dealt
        damage this turn makes the spell cost what the seat can pay. Without such a target among
        the options, or when the full price is payable or unreadable, the options stay as offered.
        """
        discount = damaged_target_discount(source_name)
        if discount is None:
            return options
        actor_id = str(state.get("actor_id") or "")
        offer = self._visible_mana_offer(self._actor(state))
        if (
            offer is None
            or board_lowers_costs(state, actor_id)
            or can_pay(offer, discount.full) is not False
        ):
            return options
        damaged = damaged_opposing_creatures(state, actor_id)
        kept: list[dict[str, object]] = []
        for option in options:
            metadata = option.get("metadata")
            if isinstance(metadata, dict) and str(metadata.get("object_id") or "") in damaged:
                kept.append(option)
        return kept or options

    def _mana_hold_run(self, seat: int, state: dict[str, object]) -> int | None:
        """How many own turns in a row before this one the seat held mana back; None if no turn."""
        turn = state.get("turn_number")
        if not isinstance(turn, int) or isinstance(turn, bool):
            return None
        return holds_in_a_row(self._mana_hold.get(seat), turn, len(players(state)))

    def _note_mana_hold(self, seat: int, state: dict[str, object]) -> None:
        """Count this turn as one the seat held mana back."""
        turn = state.get("turn_number")
        run = self._mana_hold_run(seat, state)
        if isinstance(turn, int) and run is not None:
            self._mana_hold[seat] = (run + 1, turn)

    def _casts_that_break_the_mana_hold(
        self, options: Sequence[Mapping[str, object]], state: dict[str, object], seat: int
    ) -> list[Mapping[str, object]]:
        """The casts that would leave a counterspell or removal in hand without the mana for it.

        In its own main phase a seat that holds an instant to answer an opponent keeps the mana
        for it open when the cast it is weighing would spend it, the way a player does: the
        instant is then cast on an opponent's turn. Only an optional extra waits. Left alone are
        a seat with a thin board, its commander, mana, wipes, instants, a spell whose cost the
        model cannot read, a board with a cost reducer, a seat that has already held mana back
        two turns in a row, and every cast when the instant would not be payable anyway.
        """
        actor_id = str(state.get("actor_id") or "")
        run = self._mana_hold_run(seat, state)
        if (
            run is None
            or run >= HOLD_TURNS_IN_A_ROW
            or not own_main_phase(state)
            or thin_board(state, actor_id)
            or board_lowers_costs(state, actor_id)
        ):
            return []
        held = held_instants(state, actor_id)
        offer = self._visible_mana_offer(self._actor(state)) if held else None
        if offer is None:
            return []
        reserve = [
            cost
            for instant in held
            if (cost := _printed_spell_cost(instant.name)) is not None
            and can_pay(offer, cost) is True
        ]
        if not reserve:
            return []
        breaking: list[Mapping[str, object]] = []
        for option in options:
            metadata = option.get("metadata")
            if not isinstance(metadata, dict) or metadata.get("ability_type") != "spell":
                continue
            name = str(metadata.get("source_name") or "")
            if is_plan_of_the_turn(
                state, actor_id, name, str(metadata.get("source_object_id") or "")
            ):
                continue
            cost = _printed_spell_cost(name)
            if cost is None or "{x}" in cost.casefold():
                continue
            if all(can_pay(offer, cost + kept) is False for kept in reserve):
                breaking.append(option)
        return breaking

    def _alternative_costs_that_pay(
        self, state: dict[str, object], options: list[dict[str, object]], prompt: str
    ) -> list[dict[str, object]]:
        """The options of an alternative-cost question the seat's mana can still pay.

        "You may choose an alternative cost for casting Shriekmaw" offers Evoke {1}{B} beside the
        full {4}{B}. The cast was offered at priority because the cheaper way is payable; with
        four sources the pilot chose the full cost, the payment was cancelled, and the spell was
        not cast at all. Options whose cost the model cannot read stay, and a question every
        option of which can be paid, or none, is left as offered.
        """
        spell = _alternative_cost_spell(prompt)
        if spell is None:
            return options
        offer = self._visible_mana_offer(self._actor(state))
        if offer is None:
            return options
        kept = [
            option
            for option in options
            if (cost := _alternative_cost_of(str(option.get("label", "")))) is None
            or can_pay(offer, cost) is not False
        ]
        return kept if 0 < len(kept) < len(options) else options

    def _decide_mana(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        context: dict[str, Any],
        rng: random.Random,
    ) -> str:
        if not options:
            raise FullGameProtocolError("mana decision has no legal options")

        # No-progress guard: an identical mana-payment offer repeating
        # consecutively means no selection advanced the payment (e.g. pool
        # spends the engine cannot apply, re-prompted unchanged). Take the
        # engine-offered cancel so the activation aborts gracefully instead
        # of looping forever. Any progress (pool drain, tapped source,
        # changed requirement) alters the fingerprint and resets the count.
        # This is liveness bookkeeping, not payment semantics: the engine
        # alone decides what each selection does.
        seat = runtime.binding.seat
        fingerprint = (
            seat,
            str(context.get("unpaid_mana", "")),
            tuple(
                sorted(
                    (
                        # Not the option id: the engine re-mints some ids
                        # (special mana actions such as Delve) on every
                        # offer, which hid an identical repeat (#732).
                        str(option.get("option_type", "")),
                        str(option.get("label", "")),
                        str((option.get("metadata") or {}).get("mana_available")),
                    )
                    for option in options
                )
            ),
        )
        if self._mana_last_fingerprint.get(seat) == fingerprint:
            repeats = self._mana_repeat_count.get(seat, 1) + 1
        else:
            repeats = 1
        self._mana_last_fingerprint[seat] = fingerprint
        self._mana_repeat_count[seat] = repeats
        if repeats >= 3:
            self._mana_repeat_count[seat] = 0
            for option in options:
                if self._required_text(option, "option_type") == "cancel_mana_payment":
                    _LOG.info(
                        "mana-payment no-progress guard: identical offer %d times, cancelling",
                        repeats,
                    )
                    return self._required_text(option, "option_id")
            raise FullGameProtocolError(
                "mana-payment no-progress guard tripped with no cancel offered"
            )
        return self._complete_payment(runtime, state, options, context, rng)

    def _colours_that_complete(
        self, seat: int, options: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """The colour options of a mana pick after which the payment can still be finished.

        An any-colour ability asks for its colour in a prompt of its own; the cost ranking of
        that prompt does not know what the other sources can make (Spire of Industry for a
        {B}{R} cost, with only black sources left, was set to black). Anything the model cannot
        read, and a pick every colour of which completes or none, leaves the options as offered.
        """
        offer = self._last_payment_offer.get(seat)
        letters = {
            str(option.get("option_id")): colour_letter(str(option.get("label", "")))
            for option in options
        }
        if offer is None or not letters or None in letters.values():
            return options
        outcomes = [(letter,) for letter in letters.values() if letter is not None]
        good = completing_outcomes(offer[0], offer[1], offer[2], outcomes)
        if not good:
            return options
        kept = [o for o in options if (letters[str(o.get("option_id"))] or "",) in good]
        return kept if 0 < len(kept) < len(options) else options

    def _vector_that_completes(
        self, seat: int, legs: list[tuple[int, int, str]], total: tuple[int, int], values: list[int]
    ) -> list[int]:
        """The pilot's mana split, or the nearest one that keeps the payment completable.

        The legs of a "any combination of" ability are its colours; the split decides which of
        the colours the rest of the payment gets.
        """
        offer = self._last_payment_offer.get(seat)
        letters = [colour_letter(prompt) for _low, _high, prompt in legs]
        if (
            offer is None
            or None in letters
            or math.prod(high - low + 1 for low, high, _ in legs) > 4096
        ):
            return values
        vectors = [
            vector
            for vector in itertools.product(*(range(low, high + 1) for low, high, _ in legs))
            if total[0] <= sum(vector) <= total[1]
        ]

        def outcome(vector: tuple[int, ...]) -> tuple[str, ...]:
            return tuple(
                sorted(
                    letter
                    for letter, count in zip(letters, vector, strict=True)
                    if letter
                    for _ in range(count)
                )
            )

        good = completing_outcomes(
            offer[0], offer[1], offer[2], sorted({outcome(v) for v in vectors})
        )
        if not good or outcome(tuple(values)) in good:
            return values
        near = min(
            (v for v in vectors if outcome(v) in good),
            key=lambda v: (sum(abs(a - b) for a, b in zip(v, values, strict=True)), v),
        )
        return list(near)

    def _complete_payment(
        self,
        runtime: _RuntimePilot,
        state: dict[str, object],
        options: list[dict[str, object]],
        context: dict[str, object],
        rng: random.Random,
    ) -> str:
        """The usual choice, unless it strands a payment that another option would finish.

        #989 phase 5: the choice below knows colours when it orders sources, but the check that
        feeds the pool into a filter land only counts mana. A Mountain's {R} spent on the {1} of a
        {1}{W} left the Rugged Prairie unable to pay its own {R/W}, and Hall of Oracles was tapped
        for {C} while the Swamp that pays its {1} stayed untapped: 56 of the 136 cancelled
        payments in 24 real games could still be paid at their first prompt. The model of
        ``full_game_pilot_payment_plan`` only reads the engine's own text; where it cannot read an
        offer, or the usual choice keeps the payment completable, nothing changes here.
        """
        choice = self._choose_mana_option(runtime, state, options, context, rng)
        completing = completing_options(options, str(context.get("unpaid_mana", "")))
        if not completing or choice in completing:
            return choice
        chosen = next((o for o in options if o.get("option_id") == choice), None)
        if chosen is None or chosen.get("option_type") == "cancel_mana_payment":
            return choice
        cancels = {
            option.get("option_id")
            for option in options
            if option.get("option_type") == "cancel_mana_payment"
        }
        narrowed = [
            option
            for option in options
            if option.get("option_id") in completing or option.get("option_id") in cancels
        ]
        _LOG.info(
            "mana payment: %r would strand the cost, paying with %d completing option(s)",
            chosen.get("label"),
            len(narrowed) - len(cancels),
        )
        alternative = self._choose_mana_option(
            runtime, state, narrowed, context, rng, payable=frozenset(map(str, completing))
        )
        # cancelling is the dead end this steers away from, never what it steers towards: the
        # pilot's own rules may withhold every option the model found
        return choice if alternative in cancels else alternative

    def _choose_mana_option(
        self,
        runtime: _RuntimePilot,
        state: dict[str, object],
        options: list[dict[str, object]],
        context: dict[str, object],
        rng: random.Random,
        payable: frozenset[str] = frozenset(),
    ) -> str:
        seat = runtime.binding.seat
        pool_options = [
            option
            for option in options
            if self._required_text(option, "option_type") == "mana_pool"
        ]
        if pool_options:
            unpaid = str(context.get("unpaid_mana", "")).casefold()

            def pool_symbol(option: dict[str, Any]) -> str:
                metadata = option.get("metadata")
                meta = metadata if isinstance(metadata, dict) else {}
                mana_type = str(meta.get("mana_type", "")).casefold()
                return {
                    "white": "w",
                    "blue": "u",
                    "black": "b",
                    "red": "r",
                    "green": "g",
                    "colorless": "c",
                }.get(mana_type, "")

            def pool_advances(option: dict[str, Any]) -> bool:
                # Engine-native affordance (ManaCost.testPay projected by
                # the bridge): one mana of this pool type advances the
                # unpaid cost. Unknown/absent means usable; the engine
                # stays the authority and re-prompts (guarded above) if a
                # spend cannot apply.
                metadata = option.get("metadata")
                if not isinstance(metadata, dict):
                    return True
                return metadata.get("advances_payment") is not False

            def pool_key(option: dict[str, Any]) -> tuple[int, str, str]:
                metadata = option.get("metadata")
                meta = metadata if isinstance(metadata, dict) else {}
                mana_type = str(meta.get("mana_type", "")).casefold()
                symbol = pool_symbol(option)
                exact_required = 1 if symbol and f"{{{symbol}}}" in unpaid else 0
                return exact_required, mana_type, str(option.get("label", "")).casefold()

            # A filter land or signet ("{1}, {T}: Add {R}{W}") turns pooled
            # mana into more mana. Spending the pool on the spell first
            # strands it, and the cancel repeats until the priority guard
            # latches (#732). When the pool and the free sources cannot
            # finish the unpaid cost alone, feed the costed ability the pool
            # already covers instead; the engine re-validates the activation.
            funded = self._pool_funded_mana_ability(options, pool_options, unpaid)
            if funded is not None:
                _LOG.info("feeding the pool into costed mana ability %s", funded)
                return funded

            # WS229 F-RULES-03 disposition: pool-first routing is kept, but
            # auto-submit is gated to the no-discretion case. A lone pool
            # candidate is a forced move (logged); several candidates hide
            # real discretion (which color to spend), so the pilot chooses.
            # Productive candidates are those the engine reports as
            # payment-advancing; the prompt-text heuristic below only orders
            # them and never excludes: exclusion is native-flag-only.
            candidates = [option for option in pool_options if pool_advances(option)]
            if len(candidates) == 1:
                chosen_pool = self._required_text(candidates[0], "option_id")
                _LOG.info(
                    "forced mana-pool spend: single productive pool candidate %s",
                    chosen_pool,
                )
                return chosen_pool
            if candidates:
                ordered = sorted(candidates, key=pool_key, reverse=True)
                pool_views: list[PilotActionView] = []
                raw_by_pool_view: dict[str, str] = {}
                for rank, option in enumerate(ordered):
                    view_id = f"mana:pool:{rank}"
                    raw_by_pool_view[view_id] = self._required_text(option, "option_id")
                    pool_views.append(
                        PilotActionView(
                            action_id=view_id,
                            action_kind="card",
                            card_name=str(option.get("label", "Spend pool mana")),
                            floor_value=max(0.05, 0.75 - 0.01 * rank),
                            immediate_impact=0.55,
                            metadata={"xmage_option_type": "mana_pool"},
                        )
                    )
                pool_decision = runtime.pilot.choose_action(
                    self._pilot_state(runtime, state), pool_views, rng
                )
                if pool_decision.selected_action_id is None:
                    raise FullGameProtocolError("Commander Lab pilot returned no mana decision")
                try:
                    return raw_by_pool_view[pool_decision.selected_action_id]
                except KeyError:
                    raise FullGameProtocolError(
                        "pilot returned unknown stable pool-mana action"
                    ) from None

        non_pool = [
            option
            for option in options
            if self._required_text(option, "option_type") != "mana_pool"
        ]
        if not non_pool:
            raise FullGameProtocolError(
                "mana decision has no productive option: pool cannot satisfy "
                "the colored requirement and no ability or cancel is offered"
            )
        # Affordability also governs mana abilities picked mid-payment: a
        # costed mana ability (signet, filter land) the current pool cannot
        # fund fails inside payManaMode with no pilot recourse. Withhold
        # such abilities from selection with the same native-flag gate used
        # at priority; pool spends and cancel are always selectable.
        selectable: list[dict[str, Any]] = []
        for option in non_pool:
            if self._required_text(option, "option_type") == "mana_ability" and (
                not self._priority_action_affordable(
                    option, state, pool_verified=str(option.get("option_id")) in payable
                )
                or self._spends_the_activations_own_source(seat, option)
                or self._spends_counters_the_cast_reserves(seat, option)
                or self._spends_a_permanent_the_tap_cost_needs(seat, option, state)
            ):
                continue
            selectable.append(option)
        if not selectable:
            raise FullGameProtocolError(
                "mana decision has no affordable option: every mana ability "
                "is natively unfunded and no cancel is offered"
            )
        if len(selectable) != len(non_pool):
            _LOG.info(
                "withheld %d unaffordable mana abilit(ies) from payment selection",
                len(non_pool) - len(selectable),
            )
        options = self._mana_before_alternate_payments(
            selectable, str(context.get("unpaid_mana", ""))
        )

        planned = self._planned_mana_source(options, str(context.get("unpaid_mana", "")))
        if planned is not None:
            return planned

        actions: list[PilotActionView] = []
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[tuple[str, str], int] = {}
        unpaid_mana = str(context.get("unpaid_mana", ""))
        for option in options:
            option_type = self._required_text(option, "option_type")
            label = str(option.get("label", option_type))
            key = (option_type, label.casefold())
            occurrence = occurrences.get(key, 0)
            occurrences[key] = occurrence + 1
            stable_id = f"mana:{option_type}:{label.casefold()}:{occurrence}"
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
            if option_type == "cancel_mana_payment":
                floor_value = 0.1
            elif option_type == "mana_ability":
                floor_value = 0.65 + 0.1 * mana_payment_fit(label, unpaid_mana)
            else:
                floor_value = 0.75
            actions.append(
                PilotActionView(
                    action_id=stable_id,
                    action_kind="pass" if option_type == "cancel_mana_payment" else "card",
                    card_name=label,
                    floor_value=floor_value,
                    immediate_impact=0.0 if option_type == "cancel_mana_payment" else 0.55,
                    metadata={"xmage_option_type": option_type},
                )
            )
        decision = runtime.pilot.choose_action(self._pilot_state(runtime, state), actions, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no mana decision")
        try:
            return raw_by_stable_id[decision.selected_action_id]
        except KeyError:
            raise FullGameProtocolError("pilot returned unknown stable mana action") from None

    @staticmethod
    def _unpaid_mana_amount(unpaid_mana: str) -> int | None:
        """Mana symbols an unpaid cost still prints, or None when it is not countable.

        Generic symbols count their number, colored, hybrid and Phyrexian
        symbols count one. An X or any other symbol is unknown and keeps the
        caller on its existing path.
        """
        total = 0
        for symbol in _MANA_SYMBOL.findall(unpaid_mana.casefold()):
            if symbol.isdigit():
                total += int(symbol)
            elif symbol and symbol != "x":
                total += 1
            else:
                return None
        return total

    def _pool_funded_mana_ability(
        self,
        options: list[dict[str, object]],
        pool_options: list[dict[str, object]],
        unpaid_mana: str,
    ) -> str | None:
        """A costed mana ability to fund from the pool, when nothing else can finish.

        Engine cost facts only: an offered mana ability with a known positive
        mana cost whose cost the pool covers (``pool_covers_mana_cost`` True).
        It is chosen only when the pool plus one payment per distinct free
        source (a mana ability with all-zero cost facts) falls short of the
        unpaid amount, so a spend that plain sources can finish is untouched.
        Ties are ordered by label, then option id, so twins stay identical.
        """
        unpaid = self._unpaid_mana_amount(unpaid_mana)
        if unpaid is None:
            return None
        pooled = 0
        for option in pool_options:
            metadata = option.get("metadata")
            meta = metadata if isinstance(metadata, dict) else {}
            available = meta.get("mana_available")
            pooled += available if isinstance(available, int) and available > 0 else 1
        free_sources: set[str] = set()
        funded: list[dict[str, object]] = []
        for option in options:
            if self._required_text(option, "option_type") != "mana_ability":
                continue
            metadata = option.get("metadata")
            meta = metadata if isinstance(metadata, dict) else {}
            amounts = [_cost_amount(meta, key) for key, _ in _MANA_COST_COLORS]
            amounts.append(_cost_amount(meta, "mana_cost_generic"))
            if any(amount is None for amount in amounts):
                continue
            if any(amount for amount in amounts if amount is not None):
                if meta.get("pool_covers_mana_cost") is True:
                    funded.append(option)
            else:
                free_sources.add(str(meta.get("source_object_id") or option.get("option_id")))
        if not funded or pooled + len(free_sources) >= unpaid:
            return None
        funded.sort(
            key=lambda option: (
                str(option.get("label", "")).casefold(),
                str(option.get("option_id", "")),
            )
        )
        return self._required_text(funded[0], "option_id")

    def _remember_failed_payment(self, seat: int, state: dict[str, Any]) -> None:
        """Note that this seat gave up paying for its last chosen action.

        A player who could not pay for a spell does not try the same spell
        again that turn unless more mana shows up; retrying the identical
        payment only replays the same cancel (up to the turn cap, three times
        per spell in real games).
        """
        label = self._last_priority_label.get(seat)
        if not label:
            return
        turn = state.get("turn_number")
        failed = self._failed_payments.get(seat)
        if failed is None or failed[0] != turn:
            failed = (turn, {})
            self._failed_payments[seat] = failed
        failed[1][label] = self._last_priority_visible_mana.get(
            seat, self._available_mana(self._actor(state))
        )

    def _mana_before_alternate_payments(
        self, options: list[dict[str, object]], unpaid_mana: str
    ) -> list[dict[str, object]]:
        """Leave convoke, delve and improvise out while a mana ability can still pay.

        The pinned engine pays those three after every mana ability: the first
        creature tapped for convoke (or card exiled for delve) shuts the
        lands off for the rest of the spell (``ActivationManaAbilityStep.AFTER``,
        Spell.setCurrentActivatingManaAbilitiesStep). The pilot used to pick the
        special action first on the tie with a generic payer, so a Bennie Bracks
        with four untapped lands lost them after one convoke and was cancelled
        short by one {1}. Taking the lands first costs nothing: the special
        action is back as soon as no ability can pay a part of what is left
        (a {W} owed with only Swamps untapped is a convoke by a white creature).
        Assist, which the engine wants before the mana abilities, stays offered.
        """
        specials = [
            option
            for option in options
            if self._required_text(option, "option_type") == "special_mana_action"
            and "assist" not in str(option.get("label", "")).casefold()
        ]
        if not specials:
            return options
        payable = any(
            self._required_text(option, "option_type") == "mana_ability"
            and mana_payment_fit(str(option.get("label", "")), unpaid_mana) > 0
            for option in options
        )
        if not payable:
            return options
        _LOG.info(
            "paying with mana abilities before %d alternate payment(s) (convoke, delve)",
            len(specials),
        )
        return [option for option in options if option not in specials]

    def _planned_mana_source(self, options: list[dict[str, Any]], unpaid_mana: str) -> str | None:
        """Pay the way a player taps lands: scarcest color first, flexible sources last.

        Paying mana is mechanics, not judgement, so when the offer holds only
        mana abilities (and the engine's cancel) the source is picked here
        instead of through the pilot's sampled choice, which let weaker
        profiles tap a Plains for {U} or spend a Prairie Stream's {W} while a
        Plains was untapped and then cancel the whole cast. Order:

        1. a source that pays a needed color, the color with the fewest
           sources on offer first (Prairie Stream's {U} before any {W});
        2. among those, the source able to make the fewest needed colors;
        3. then generic payers, the least flexible first;

        Ties fall back to the label, so twins stay identical. Anything else on
        offer (Delve, Convoke, pool spends) returns None and keeps the
        pilot-chosen path.
        """
        abilities: list[dict[str, Any]] = []
        for option in options:
            option_type = self._required_text(option, "option_type")
            if option_type == "mana_ability":
                abilities.append(option)
            elif option_type != "cancel_mana_payment":
                return None
        if not abilities:
            return None
        needed = mana_needed_letters(unpaid_mana)

        def source_key(option: dict[str, Any]) -> str:
            metadata = option.get("metadata")
            meta = metadata if isinstance(metadata, dict) else {}
            label = str(option.get("label", ""))
            return str(meta.get("source_object_id") or label.partition(" — ")[0])

        produced_by_source: dict[str, set[str]] = {}
        for option in abilities:
            letters = mana_produced_letters(str(option.get("label", ""))) or frozenset()
            produced_by_source.setdefault(source_key(option), set()).update(letters)
        supply = {
            color: sum(1 for letters in produced_by_source.values() if color in letters)
            for color in needed
        }

        def rank(option: dict[str, Any]) -> tuple[int, int, int, str]:
            label = str(option.get("label", ""))
            fit = mana_payment_fit(label, unpaid_mana)
            produced = mana_produced_letters(label) or frozenset()
            paying = produced & needed
            scarcity = min((supply[color] for color in paying), default=99)
            flexibility = len(produced_by_source.get(source_key(option), set()) & needed)
            return (-fit, scarcity, flexibility, label.casefold())

        # A source whose text fits nothing is still tapped rather than the
        # Lab inventing a cancel: "spend mana as though any color" effects
        # make the engine, not the label, the judge of what pays.
        return self._required_text(min(abilities, key=rank), "option_id")

    @staticmethod
    def _required_bound(mapping: dict[str, Any], key: str) -> int:
        """Authoritative integer bound from Core-supplied context (fail closed).

        Strict: missing, boolean, or non-integer bounds raise. No coercion,
        no default, no clamp — the Lab never invents domain content.
        """
        if not isinstance(mapping, dict) or key not in mapping:
            raise FullGameProtocolError(f"numeric decision missing explicit bound: {key}")
        raw = mapping[key]
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise FullGameProtocolError(f"numeric decision bound is not an integer: {key}")
        return int(raw)

    def _decide_numeric(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        context: dict[str, Any],
        rng: random.Random,
        *,
        decision_class: str,
        prompt: str = "",
        source_object: Any = None,
    ) -> int:
        """Range-native scalar decision (WS229 Design B).

        The Core-supplied [min, max] is projected losslessly into a domain
        descriptor; the pilot chooses strategy inside it; the Lab validates
        exact membership before submission. No enumeration, no sampling, no
        {min,mid,max} collapse, no clamp, no nearest-value mapping, no
        default, no fallback. Malformed, non-integer, and out-of-domain
        pilot returns fail closed.

        For a mana X the descriptor also carries an ``affordable_max``
        strategy hint (see ``_announce_x_affordable_max``). That hint narrows
        the band the pilot strategy picks inside; it never narrows, moves or
        re-derives the authoritative domain, which is still the only thing
        validated here and the only thing the bridge accepts. It is derived
        from the cost the engine itself reported on the priority option that
        started this action, or, failing that, from the budget alone; it never
        costs the Lab anything to compute and never leaves the domain.
        """
        minimum = self._required_bound(context, "numeric_min")
        maximum = self._required_bound(context, "numeric_max")
        if maximum < minimum:
            raise FullGameProtocolError("numeric decision has reversed bounds")
        outcome = str(context.get("outcome", "benefit")).casefold()
        domain: dict[str, Any] = {
            "kind": "contiguous_inclusive_int",
            "min": minimum,
            "max": maximum,
            "outcome": outcome,
            "prompt": prompt,
        }
        if decision_class == "announce_x":
            affordable_max = self._announce_x_affordable_max(
                runtime, state, context, source_object, prompt
            )
            if affordable_max is None:
                # #920: a tap-X cost is not a mana X; it is bounded by what is there to tap.
                affordable_max = x_tap_prompt_cap(
                    prompt, source_object, self._actor(state).get("battlefield")
                )
            if affordable_max is None and _PAY_ANY_AMOUNT_PROMPT.match(prompt):
                affordable_max = self._mana_budget(state)
            if affordable_max is not None:
                domain["affordable_max"] = affordable_max
        if self._declines_unsupported_energy_payment(decision_class, prompt, source_object):
            return minimum
        if (
            decision_class == "amount"
            and _COUNTER_COUNT_PROMPT.match(prompt)
            and self._paying_counters(int(state.get("seat", -1)) + 1) is not None
        ):
            # A "remove N counters" cost asks how many of one pile pays; the cost is only paid
            # once N are gone, so the seat takes as many as it may.
            return maximum
        chosen = runtime.pilot.choose_number(self._pilot_state(runtime, state), domain, rng)
        if isinstance(chosen, bool) or not isinstance(chosen, int):
            raise FullGameProtocolError(
                f"pilot returned non-integer numeric decision for {decision_class}"
            )
        if not minimum <= chosen <= maximum:
            raise FullGameProtocolError(
                f"pilot numeric decision {chosen} outside authoritative domain "
                f"{minimum}..{maximum} for {decision_class}"
            )
        if decision_class == "announce_x":
            # #815: remember the announced X per source. If the engine reverses
            # this cast (over-announced X), the next announce_x for the same
            # source sees the failed value and caps below it instead of
            # re-announcing the same unpayable X forever.
            self._remember_announced_x(runtime.binding.seat, source_object, chosen)
            self._reserve_counters(runtime.binding.seat, source_object, prompt, chosen)
        return chosen

    @staticmethod
    def _declines_unsupported_energy_payment(
        decision_class: str, prompt: str, source_object: object
    ) -> bool:
        """True for the one "pay any amount of {E}" question that leads into a closed path.

        Vault 112: Sadistic Simulation, chapter III, exiles that many cards and lets its
        controller play one for free through the engine's land-or-spell callback. That
        caller is outside the declared decision classes (architecture freeze ADR section 28:
        UNSUPPORTED_DECISION_CLASS), so paying any energy ended the game. Paying none is a
        legal answer ("Pay any amount") and skips the exile, so the game goes on without the
        chapter's benefit. The bridge still fails closed on the path itself.
        """
        if decision_class != "amount" or "{E}" not in prompt:
            return False
        if not isinstance(source_object, dict):
            return False
        name = str(source_object.get("source_name") or "").strip().casefold()
        return name in _UNSUPPORTED_ENERGY_PAYMENT_SOURCES

    def _remember_announced_x(self, seat: int, source_object: object, chosen: int) -> None:
        """Keep the X this seat announced for this source.

        Keyed by the announce frame's ``source_object_id`` like
        ``_priority_cost_facts``. A repeated ``announce_x`` for the same source
        before the seat's next priority decision means the previous cast was
        reversed (the X was unpayable), so the failed value is kept for the
        affordable_max cap. Cleared on the seat's next priority decision.
        """
        if not isinstance(source_object, dict):
            return
        source = str(source_object.get("source_object_id") or "")
        if not source:
            return
        self._failed_x_announcements.setdefault(seat, {})[source] = chosen

    def _remember_priority_cost_facts(
        self,
        seat: int,
        options: list[dict[str, Any]],
        selected: list[str],
        state: dict[str, object] | None = None,
    ) -> None:
        """Keep the cost the engine reported for the priority option just chosen.

        The engine answers a priority window with the full legal set, each
        option carrying the bridge's own ``enrichAbilityCostFacts`` summary of
        what activating or casting it costs. When the pilot then chooses one,
        the engine immediately asks for the X in that action's cost — and that
        ``announce_x`` frame carries no cost whatsoever, only the source it
        belongs to. Holding the chosen option's reported non-X mana value here,
        keyed by the engine's own ``source_object_id``, is what lets the later
        ``announce_x`` budget against a cost the engine stated rather than one
        the Lab inferred.

        Last selection only, per seat, and dropped again on that seat's next
        priority decision or by the announce that uses it, so a remembered cost
        can never be reused for a later or different action. The key is used
        for equality against the ``source_object`` of the announce frame and
        for nothing else: it never orders, ranks, counts or sorts anything, so
        it cannot make same-seed fresh-process twins diverge the way an ordering
        key could.
        """
        if len(selected) != 1:
            return
        chosen = selected[0]
        for option in options:
            if self._required_text(option, "option_id") != chosen:
                continue
            metadata = option.get("metadata")
            if not isinstance(metadata, dict):
                return
            label = str(option.get("label") or "")
            source = str(metadata.get("source_object_id") or "")
            if source and _option_spends_own_source(label, metadata):
                self._priority_spends_source[seat] = {source}
            non_x = _option_non_x_mana_value(metadata)
            if source and non_x is not None:
                self._priority_cost_facts[seat] = {source: non_x}
            if source and state is not None:
                # #920: an X paid by removing counters from the source can use
                # no more counters than the source has, and an X paid by
                # tapping untapped permanents no more than the seat has.
                battlefield = self._actor(state).get("battlefield")
                caps = [
                    cap
                    for cap in (
                        option_x_counter_cap(label, metadata, battlefield),
                        option_x_tap_cap(label, metadata, battlefield),
                        x_counter_pile_cap(label, battlefield),
                    )
                    if cap is not None
                ]
                if caps:
                    self._priority_x_counter_caps[seat] = {source: min(caps)}
            return

    def _take_remembered_priority_cost_facts(self, seat: int, source_object: Any) -> int | None:
        """Consume this seat's remembered non-X cost for this announce source.

        Taken, not copied: one cost is announced once, so a second
        ``announce_x`` naming the same source before the seat's next priority
        decision must not re-read the same cost and fall back to the budget
        alone instead. Nothing is ever reused to answer a later announcement.
        """
        if not isinstance(source_object, dict):
            return None
        source = str(source_object.get("source_object_id") or "")
        if not source:
            return None
        return self._priority_cost_facts.get(seat, {}).pop(source, None)

    @staticmethod
    def _x_cost_facts(
        context: dict[str, Any],
        source_object: Any,
        remembered: int | None = None,
    ) -> tuple[int, int | None] | None:
        """The announced X's non-X cost, and how many X symbols carry it.

        Read from the Core-supplied request context, or from the bridge's
        ``source_object`` metadata for the ability being announced. Both are
        engine-supplied facts; the Lab never derives a mana cost itself.

        When neither names a cost at all, ``remembered`` is used: the non-X
        value the engine reported on the priority option this seat chose, which
        is the same action's cost reached by the other half of the frame pair.
        It is consulted only when both direct reads are absent, so a cost
        stated on the frame itself always wins.

        Returns ``(non_x_mana_value, x_symbols)``, where ``x_symbols`` is None
        when the facts do not state a count at all, which is the case for every
        remembered cost and for a frame carrying neither field: the caller then
        reads the count off the engine's own prompt. The whole answer is None
        when the cost is not readable, and None is the conservative answer for
        every shape that is absent, non-integer, boolean, negative, or
        zero-symbol. A frame that names only half a cost stays as unusable as it
        was: no count is filled into a statement the engine left incomplete.
        """
        sources: list[dict[str, Any]] = [context]
        if isinstance(source_object, dict):
            sources.append(source_object)

        def read(key: str) -> int | None:
            for source in sources:
                raw = source.get(key)
                if isinstance(raw, bool) or not isinstance(raw, int):
                    continue
                return raw
            return None

        non_x = read("numeric_non_x_mana_value")
        symbols = read("numeric_x_symbols")
        if non_x is None and symbols is None:
            return None if remembered is None else (remembered, None)
        if non_x is None or symbols is None:
            return None
        if non_x < 0 or symbols < 1:
            return None
        return non_x, symbols

    def _take_remembered_x_counter_cap(self, seat: int, source_object: object) -> int | None:
        """Consume this seat's remembered counter cap for this announce source.

        Taken like ``_take_remembered_priority_cost_facts``: one cap belongs to
        one announcement of the action it was kept for.
        """
        if not isinstance(source_object, dict):
            return None
        source = str(source_object.get("source_object_id") or "")
        if not source:
            return None
        return self._priority_x_counter_caps.get(seat, {}).pop(source, None)

    def _take_remembered_spends_source(
        self, seat: int, context: Mapping[str, object], source_object: object
    ) -> str:
        """Consume this seat's remembered spends-own-source fact for this source (#1041).

        Taken like ``_take_remembered_priority_cost_facts``: belongs to the
        announcement of the action it was kept for.
        """
        source = (
            str(source_object.get("source_object_id") or "")
            if isinstance(source_object, dict)
            else ""
        )
        if not source:
            return ""
        remembered = self._priority_spends_source.get(seat, set())
        was_remembered = source in remembered
        remembered.discard(source)
        direct = (
            (
                isinstance(source_object, dict)
                and _option_spends_own_source(str(source_object.get("label") or ""), source_object)
            )
            or context.get("requires_tap_source") is True
            or context.get("requires_sacrifice_source") is True
        )
        if was_remembered or direct:
            return source
        return ""

    def _x_spell_without_x(self, option: dict[str, object], state: dict[str, object]) -> bool:
        """True for a cast of an X spell whose visible mana leaves nothing for X.

        The rest of the cost is paid out of the same mana as X, so a budget that
        covers only that rest announces X = 0: a Goblin Negotiation cast for
        {R}{R} deals no damage and makes no token, and the card is gone. The
        window withholds such a cast; a spell that does something at X = 0 is
        the exception, and a cost the engine did not break down is left to the
        engine.
        """
        metadata = option.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("ability_type") != "spell":
            return False
        name = str(metadata.get("source_name") or "").strip()
        facts = card_facts(name)
        if facts is None or name.casefold() in _ZERO_X_SPELLS:
            return False
        symbols = facts.mana_cost.upper().count("{X}")
        non_x = _option_non_x_mana_value(metadata)
        if symbols < 1 or non_x is None:
            return False
        return (self._mana_budget(state) - non_x) // symbols < 1

    def _mana_budget(self, state: dict[str, Any], *, excluded_source_id: str = "") -> int:
        """Mana the actor can see it could produce right now.

        Its own floating pool plus each untapped permanent on its own
        battlefield whose public ability text reads as a mana ability. One
        permanent counts once: a "tap for two" rock is budgeted as one, which
        under-states rather than over-states what the pilot believes it has.
        Only the acting principal's own zones are read, so this is
        pilot-visible by construction.

        When ``excluded_source_id`` is given (because the announced ability
        spends its own source via {T} or self-sacrifice, #1041), that permanent
        is not counted as an available mana source.
        """
        actor = self._actor(state)
        budget = int(self._actor_mana(actor))
        battlefield = actor.get("battlefield")
        if not isinstance(battlefield, list):
            return budget
        for item in battlefield:
            if not isinstance(item, dict):
                continue
            if excluded_source_id and str(item.get("object_id") or "") == excluded_source_id:
                continue
            if item.get("tapped") is not False:
                continue
            if item.get("face_down") is True:
                continue
            rules = item.get("abilities")
            if not isinstance(rules, list):
                continue
            if any(offers_mana_ability(str(rule)) for rule in rules):
                budget += 1
        return budget

    def _announce_x_affordable_max(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        context: dict[str, Any],
        source_object: Any,
        prompt: str,
    ) -> int | None:
        """Largest announced X the pilot's visible mana could pay (#700).

        ``(budget - non_x_mana_value) // x_symbols``, never below zero: the
        rest of the cost is paid out of the same visible mana, and a cost
        carrying several X symbols shares what is left between them.

        Only a mana X is budgeted at all. ``Player.announceX`` also serves the
        engine's non-mana ``announceXCost``, which prints its own "{X}" and
        then keeps going with the action's text ("... {X} (remove X
        counters)"), and a power/toughness or counter X is not paid in mana,
        so budgeting it against the pool would bound a value by a resource
        that never had anything to do with it. Only the engine's whole mana
        prompt, "Announce the value for " followed by nothing but its "{X}"
        symbols, is a mana X (``mana_x_prompt_symbols``); the count of symbols
        in that same prompt is the ``x_symbols`` this divides by whenever no
        frame states a count of its own.

        When the cost itself is unreadable, the bounded fallback is a non-X
        cost of 0 over the prompt's own symbol count: for the ordinary
        single-X cost that is the whole visible budget. That still keeps the
        choice inside the mana the pilot can see instead of the engine's
        ``Integer.MAX_VALUE`` ceiling, and it stays conservative in the safe
        direction — it can only announce a smaller X than the domain allows,
        never one the domain forbids. A budget that cannot even cover the rest
        of the cost clamps to 0, and the band never drops below the Core's own
        minimum.

        Residual, not repaired here: a source that spends itself via {T} or
        self-sacrifice (#1041) is excluded from ``_mana_budget`` via
        ``excluded_source_id``, leaving only the "one permanent is counted as
        one mana" understatement as a conservative residual. Both are
        documented on ``_mana_budget``.

        #815: if a previous X announced for this source was reversed by the
        engine (unpayable), the cap is lowered below that failed value. A
        repeated ``announce_x`` for the same source proves the previous value
        failed, so the band narrows instead of re-announcing the same X.
        """
        prompt_symbols = mana_x_prompt_symbols(prompt)
        if prompt_symbols is None:
            return None
        seat = runtime.binding.seat
        facts = self._x_cost_facts(
            context,
            source_object,
            self._take_remembered_priority_cost_facts(seat, source_object),
        )
        non_x, symbols = facts if facts is not None else (0, None)
        if symbols is None:
            symbols = prompt_symbols
        excluded_source = self._take_remembered_spends_source(seat, context, source_object)
        affordable = max(
            0,
            (self._mana_budget(state, excluded_source_id=excluded_source) - non_x) // symbols,
        )
        # #920: an X that is also paid by removing counters from its source,
        # or by tapping X untapped permanents.
        counter_cap = self._take_remembered_x_counter_cap(seat, source_object)
        if counter_cap is not None:
            affordable = min(affordable, counter_cap)
        # #815: if the last X announced for this source was reversed (the
        # engine refused the payment), cap below it. A repeated announce_x
        # for the same source means the previous value failed, so re-announcing
        # it would loop forever.
        if isinstance(source_object, dict):
            source = str(source_object.get("source_object_id") or "")
            failed = self._failed_x_announcements.get(seat, {}).get(source)
            if isinstance(failed, int) and failed > 0:
                affordable = min(affordable, failed - 1)
        return affordable

    def _decide_multi_amount(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        context: dict[str, Any],
        rng: random.Random,
        *,
        prompt: str = "",
    ) -> list[int]:
        """Joint bounded integer-vector decision (WS229 Design B).

        One pilot-facing decision with per-leg [min, max] plus the total
        band — the exact isGoodValues predicate projected, not invented.
        Per-leg frames are never separate pilot strategic choices.
        """
        raw_legs = context.get("numeric_legs")
        if not isinstance(raw_legs, list) or not raw_legs:
            raise FullGameProtocolError(
                "multi_amount requires a joint vector context (numeric_legs)"
            )
        legs: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_legs):
            if not isinstance(raw, dict):
                raise FullGameProtocolError(f"multi_amount leg {index} is not a bounds object")
            leg_min = self._required_bound(raw, "min")
            leg_max = self._required_bound(raw, "max")
            if leg_max < leg_min:
                raise FullGameProtocolError(f"multi_amount leg {index} has reversed bounds")
            legs.append({"min": leg_min, "max": leg_max, "prompt": str(raw.get("prompt", ""))})
        total_min = self._required_bound(context, "numeric_total_min")
        total_max = self._required_bound(context, "numeric_total_max")
        if total_max < total_min:
            raise FullGameProtocolError("multi_amount has a reversed total band")
        if (
            sum(leg["min"] for leg in legs) > total_max
            or sum(leg["max"] for leg in legs) < total_min
        ):
            raise FullGameProtocolError("multi_amount joint domain is empty")
        outcome = str(context.get("outcome", "benefit")).casefold()
        domain: dict[str, Any] = {
            "kind": "joint_bounded_int_vector",
            "legs": legs,
            "total_min": total_min,
            "total_max": total_max,
            "outcome": outcome,
            "prompt": prompt,
        }
        chosen = runtime.pilot.choose_numbers(self._pilot_state(runtime, state), domain, rng)
        if not isinstance(chosen, (list, tuple)) or len(chosen) != len(legs):
            raise FullGameProtocolError("pilot joint numeric decision has the wrong vector length")
        values: list[int] = []
        for element in chosen:
            if isinstance(element, bool) or not isinstance(element, int):
                raise FullGameProtocolError(
                    "pilot joint numeric decision has a non-integer element"
                )
            values.append(element)
        for index, (value, leg) in enumerate(zip(values, legs, strict=True)):
            if not leg["min"] <= value <= leg["max"]:
                raise FullGameProtocolError(
                    f"pilot joint numeric leg {index} value {value} outside "
                    f"authoritative domain {leg['min']}..{leg['max']}"
                )
        if not total_min <= sum(values) <= total_max:
            raise FullGameProtocolError(
                f"pilot joint numeric total {sum(values)} outside authoritative band "
                f"{total_min}..{total_max}"
            )
        if outcome == "putmanainpool":
            values = self._vector_that_completes(
                runtime.binding.seat,
                [(leg["min"], leg["max"], leg["prompt"]) for leg in legs],
                (total_min, total_max),
                values,
            )
        return values
