"""Full-game pilot judgment on standalone mana and engine-declined may-prompts.

Real-deck 4P games on the pinned engine showed two pilot defects:

* every priority window, the pilot tapped its lands for mana it could not
  spend (mana abilities scored as free card plays), so in its own main phase
  nothing was castable and games ran 90-240 turns with almost no spells cast;
* the pilot answered "Yes" to every repeated "Pay N times Multikicker" offer
  (outcome AIDontUseIt, whose engine affordability check covers one payment),
  looping until max_decisions aborted the game. #692 narrowed this: AIDontUseIt
  is the engine's own AI label rather than a player preference, so a single
  kicker/buyback prompt is answered Yes and only a run of Yes answers from the
  same source is capped. See tests/unit/test_full_game_pilot_option_reachability.py.

The engine stays the authority in both cases; these tests pin the pilot's own
choice among the offered options and the controls that prove nothing else
changed (payments still tap sources, real actions still beat passing).
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.agents import GenericCommanderPilot
from commander_lab.agents.pilots import STANDALONE_MANA_ABILITY_UTILITY
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
    mana_payment_fit,
)
from commander_lab.engine.rules.full_game_pilot_views import tap_creature_cost_unpayable
from commander_lab.models import (
    PilotActionView,
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
)


def _policy(
    mode: PilotDecisionMode = PilotDecisionMode.DETERMINISTIC,
) -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in range(1, 5):
        config = PilotConfig(
            pilot_name="auto", strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC, mode=mode
        )
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"fixture-{seat}",
            strategy="generic",
            commander_names=("Isamaru, Hound of Konda",),
            config=config,
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(_RuntimePilot(binding=binding, pilot=GenericCommanderPilot(config)))
    return ExternalPilotDecisionPolicy(tuple(runtimes), 20261010)  # type: ignore[arg-type]


def _state(*, step: str = "upkeep", pool_white: int = 0) -> dict[str, Any]:
    actor = {
        "player_id": "actor",
        "seat": 0,
        "life": 40,
        "hand_count": 2,
        "library_count": 90,
        "graveyard_count": 0,
        "battlefield": [
            {"object_id": f"land-{index}", "name": "Plains", "tapped": False} for index in range(3)
        ],
        "graveyard": [],
        "command": [{"object_id": "commander", "name": "Isamaru, Hound of Konda"}],
        "hand": [
            {"object_id": "hand-0", "name": "Savannah Lions"},
            {"object_id": "hand-1", "name": "Plains"},
        ],
        "mana_pool": {
            "white": pool_white,
            "blue": 0,
            "black": 0,
            "red": 0,
            "green": 0,
            "colorless": 0,
        },
    }
    opponents = [
        {
            "player_id": f"opponent-{seat}",
            "seat": seat,
            "life": 40,
            "hand_count": 7,
            "library_count": 92,
            "graveyard_count": 0,
            "battlefield": [],
            "graveyard": [],
            "command": [],
        }
        for seat in range(1, 4)
    ]
    return {
        "game_id": "engine-opaque",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 5,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "beginning" if step == "upkeep" else "precombat_main",
        "step": step,
        "players": [actor, *opponents],
        "stack": [],
    }


def _option(option_id: str, option_type: str, label: str, **metadata: Any) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "option_type": option_type,
        "label": label,
        "metadata": metadata,
    }


def _request(
    decision_class: str,
    options: list[dict[str, Any]],
    *,
    context: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    prompt: str = "",
    offset: int = 1,
) -> dict[str, Any]:
    return {
        "decision_id": f"opaque-{decision_class}-{offset}",
        "decision_offset": offset,
        "actor_id": "actor",
        "decision_class": decision_class,
        "pilot_state": state or _state(),
        "context": context or {},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": options,
        "prompt": prompt or decision_class,
    }


_TAPS = [
    _option("tap-a", "mana_ability", "Plains — {T}: Add {W}.", source_name="Plains"),
    _option("tap-b", "mana_ability", "Plains — {T}: Add {W}.", source_name="Plains"),
    _option("tap-c", "mana_ability", "Plains — {T}: Add {W}.", source_name="Plains"),
]
_PASS = _option("pass", "pass_priority", "Pass priority")


@pytest.mark.parametrize("mode", list(PilotDecisionMode))
def test_pilot_does_not_float_mana_it_cannot_spend(mode: PilotDecisionMode) -> None:
    # The upkeep window of the real-deck games: only taps and pass are offered.
    response = _policy(mode).decide(_request("priority", [_PASS, *_TAPS]))
    assert response["selected_option_ids"] == ["pass"]


def test_pilot_still_takes_a_real_action_over_passing() -> None:
    # Positive control: an engine-offered cast beats both passing and floating.
    cast = _option(
        "cast",
        "activated_ability",
        "Savannah Lions — Cast Savannah Lions",
        source_name="Savannah Lions",
        source_object_id="hand-0",
        ability_type="spell",
        mana_cost_white=1,
        mana_cost_generic=0,
        # The engine's verdict over the empty pool; untapped Plains pay it.
        pool_covers_mana_cost=False,
        requires_tap_source=False,
        requires_untap_source=False,
        requires_sacrifice_source=False,
    )
    response = _policy().decide(
        _request("priority", [_PASS, *_TAPS, cast], state=_state(step="precombat_main"))
    )
    assert response["selected_option_ids"] == ["cast"]


def test_pilot_still_plays_a_land() -> None:
    play = _option(
        "play",
        "activated_ability",
        "Plains — Play Plains",
        source_name="Plains",
        source_object_id="hand-1",
    )
    response = _policy().decide(
        _request("priority", [_PASS, *_TAPS, play], state=_state(step="precombat_main"))
    )
    assert response["selected_option_ids"] == ["play"]


def test_mana_payment_still_taps_a_source() -> None:
    # Control: the payment frame of a cast must still be paid from sources;
    # the float-only judgment never applies inside a payment.
    response = _policy().decide(
        _request(
            "mana_payment",
            [_option("cancel", "cancel_mana_payment", "Cancel"), *_TAPS],
            context={"unpaid_mana": "{W}"},
        )
    )
    assert response["selected_option_ids"][0].startswith("tap-")


def test_float_only_utility_ranks_below_pass() -> None:
    pilot = GenericCommanderPilot(
        PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
    )
    policy = _policy()
    state = policy._pilot_state(policy._pilots[1], _state())
    tap = PilotActionView(
        action_id="tap",
        action_kind="card",
        card_name="Plains",
        floor_value=0.5,
        immediate_impact=0.35,
        metadata={"is_mana_ability": True, "floats_mana_only": True},
    )
    unflagged = tap.model_copy(update={"metadata": {"is_mana_ability": True}})
    passing = PilotActionView(
        action_id="pass", action_kind="pass", card_name="Pass priority", floor_value=0.15
    )
    tap_value = pilot.evaluate_action(state, tap).total_utility
    pass_value = pilot.evaluate_action(state, passing).total_utility
    assert tap_value == STANDALONE_MANA_ABILITY_UTILITY
    assert tap_value < pass_value
    # Negative control: without the float-only flag the old scoring (a free
    # card play) still outranks passing, which is what wasted every land.
    assert pilot.evaluate_action(state, unflagged).total_utility > pass_value


def _multikicker_prompt(offer: int, cost: str = "{2}") -> str:
    """The offer exactly as ``KickerAbility.addOptionalAdditionalCosts`` writes it."""
    return f"Pay {offer} {'time' if offer == 1 else 'times'} Multikicker {cost} ?"


def _boolean(outcome: str, prompt: str, offset: int = 1) -> dict[str, Any]:
    return _request(
        "choose_use",
        [
            _option("yes", "boolean", "Yes", value=True),
            _option("no", "boolean", "No", value=False),
        ],
        context={"outcome": outcome},
        prompt=prompt,
        offset=offset,
        state=_state(step="precombat_main"),
    )


def test_repeated_multikicker_offer_is_declined() -> None:
    # Still bounded, now for the right reason: AIDontUseIt is the engine's own
    # AI label, not a player preference, so the pilot pays while its own
    # visible mana can fund another payment. #692 narrowed the guard to the
    # engine's real multikicker shape; before that this test asserted an
    # unconditional No on every offer, which refused every kicker too.
    #
    # KickerAbility phrases the offer "Pay (activatedCount + 1) time(s)
    # <cost> ?", so 1/2/3 are offer ordinals, not a declared total. Three
    # untapped Plains and a {2} cost fund exactly one payment.
    policy = _policy()
    answers = [
        policy.decide(_boolean("aidontuseit", _multikicker_prompt(count), offset=count))[
            "selected_option_ids"
        ][0]
        for count in (1, 2, 3)
    ]
    assert answers[:2] == ["yes", "no"]
    # The engine stops re-offering after a No; the third entry only pins that
    # the No reset the chain instead of leaving a spent count behind.
    assert answers[2] == "yes"


def test_repeated_may_trigger_prompt_is_answered_yes_every_time() -> None:
    # Mentor of the Meek asks "Pay {1}?" once per creature entering: same
    # source, same outcome, four times. Four separate discretionary questions,
    # not one repeating offer, so no liveness guard may answer the fourth.
    policy = _policy()
    answers = [
        policy.decide(_boolean("benefit", "Pay {1}?", offset=count))["selected_option_ids"][0]
        for count in (1, 2, 3, 4)
    ]
    assert answers == ["yes", "yes", "yes", "yes"]


def _phyrexian_ask(life: int, offset: int, *, step: str = "precombat_main") -> dict[str, Any]:
    """One ask of ``ManaCostsImpl.handlePhyrexianManaCosts`` at ``life``."""
    request = _boolean("loselife", "Pay 2 life instead of {B} (phyrexian cost)?", offset=offset)
    request["pilot_state"] = _state(step=step)
    request["pilot_state"]["players"][0]["life"] = life
    return request


def test_phyrexian_life_is_not_promised_twice_at_two_life() -> None:
    # Lashwrithe's Equip {B/P}{B/P} at 2 life (#920, pod 018): the engine tests
    # both asks against the 2 life the player still has, the pilot said Yes to
    # both, and the second PayLifeCost (CR 119.4) was unpayable, which failed
    # the whole activation. The second ask no longer offers Yes.
    policy = _policy()
    first = policy.decide(_phyrexian_ask(2, 1))
    second = policy.decide(_phyrexian_ask(2, 2))
    assert first["selected_option_ids"] == ["yes"]
    assert second["selected_option_ids"] == ["no"]


def test_phyrexian_life_is_paid_twice_when_the_life_total_covers_both() -> None:
    # Negative control: the guard only subtracts what was promised, it never
    # declines a payment the life total covers (4 life covers both asks).
    policy = _policy()
    answers = [
        policy.decide(_phyrexian_ask(life, offset))["selected_option_ids"][0]
        for offset, life in ((1, 4), (2, 4))
    ]
    assert answers == ["yes", "yes"]


def test_phyrexian_life_promise_ends_with_the_payment() -> None:
    # The asks of one payment are back to back; a decision of another class
    # (the targets of the equip, the mana payment) starts the count over, so
    # the next activation at 4 life is asked afresh.
    policy = _policy()
    assert policy.decide(_phyrexian_ask(4, 1))["selected_option_ids"] == ["yes"]
    assert policy.decide(_phyrexian_ask(4, 2))["selected_option_ids"] == ["yes"]
    policy.decide(
        _request(
            "priority",
            [_PASS],
            state=_state(step="precombat_main"),
            offset=3,
        )
    )
    assert policy.decide(_phyrexian_ask(4, 4))["selected_option_ids"] == ["yes"]
    assert policy.decide(_phyrexian_ask(4, 5))["selected_option_ids"] == ["yes"]


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [("benefit", "yes"), ("detriment", "no"), ("aidontuseit", "yes")],
)
def test_boolean_outcome_polarity(outcome: str, expected: str) -> None:
    # aidontuseit moved from "no" to "yes" in #692: it labels a prompt the
    # engine's AI declines, not a detriment, so it no longer aligns with No.
    response = _policy().decide(_boolean(outcome, "Use the ability?"))
    assert response["selected_option_ids"] == [expected]


@pytest.mark.parametrize(
    ("label", "unpaid", "fit"),
    [
        ("Glacial Fortress — {T}: Add {W}.", "{U/R}", 0),
        ("Island — {T}: Add {U}.", "{U/R}", 2),
        ("Mountain — {T}: Add {R}.", "{2}", 1),
        ("Mountain — {T}: Add {R}.", "{B}", 0),
        ("Sol Ring — {T}: Add {C}{C}.", "{1}{B}", 1),
        ("Swamp — {T}: Add {B}.", "{2/B}", 2),
        (
            "Command Tower — {T}: Add one mana of any color in your commander's color identity.",
            "{G}",
            2,
        ),
        ("Unreadable engine text", "{B}", 1),
    ],
)
def test_mana_payment_fit(label: str, unpaid: str, fit: int) -> None:
    assert mana_payment_fit(label, unpaid) == fit


def test_payment_taps_the_source_that_pays_the_unpaid_color() -> None:
    # Real-deck game: for Magma Opus's {U/R}{U/R} the pilot tapped Glacial
    # Fortress for {W} (label order), the payment stalled and was cancelled,
    # and the turn's mana was wasted on every later turn too.
    response = _policy().decide(
        _request(
            "mana_payment",
            [
                _option("cancel", "cancel_mana_payment", "Cancel mana payment"),
                _option("fortress-u", "mana_ability", "Glacial Fortress — {T}: Add {U}."),
                _option("fortress-w", "mana_ability", "Glacial Fortress — {T}: Add {W}."),
            ],
            context={"unpaid_mana": "{U/R}"},
        )
    )
    assert response["selected_option_ids"] == ["fortress-u"]


def test_payment_never_drops_an_unfitting_source() -> None:
    # Ordering only: with nothing that fits, a source is still tapped rather
    # than the pilot inventing a cancel; the engine judges the result.
    response = _policy().decide(
        _request(
            "mana_payment",
            [
                _option("cancel", "cancel_mana_payment", "Cancel mana payment"),
                _option("mountain", "mana_ability", "Mountain — {T}: Add {R}."),
            ],
            context={"unpaid_mana": "{B}"},
        )
    )
    assert response["selected_option_ids"] == ["mountain"]


def test_payment_spends_the_scarce_color_from_the_dual_land() -> None:
    # {W}{U} with Prairie Stream and two Plains: a player taps the dual for {U}
    # and a Plains for {W}. Spending the dual on {W} strands the {U} and the
    # whole cast was cancelled (three times per turn in real games).
    options = [
        _option("cancel", "cancel_mana_payment", "Cancel mana payment"),
        _option(
            "stream-w", "mana_ability", "Prairie Stream — {T}: Add {W}.", source_object_id="ps"
        ),
        _option(
            "stream-u", "mana_ability", "Prairie Stream — {T}: Add {U}.", source_object_id="ps"
        ),
        _option("plains-1", "mana_ability", "Plains — {T}: Add {W}.", source_object_id="p1"),
        _option("plains-2", "mana_ability", "Plains — {T}: Add {W}.", source_object_id="p2"),
    ]
    for mode in (PilotDecisionMode.DETERMINISTIC, PilotDecisionMode.STOCHASTIC):
        response = _policy(mode).decide(
            _request("mana_payment", options, context={"unpaid_mana": "{W}{U}"})
        )
        assert response["selected_option_ids"] == ["stream-u"]


def test_payment_keeps_flexible_sources_for_later_colors() -> None:
    response = _policy().decide(
        _request(
            "mana_payment",
            [
                _option(
                    "stream-w",
                    "mana_ability",
                    "Prairie Stream — {T}: Add {W}.",
                    source_object_id="ps",
                ),
                _option(
                    "stream-u",
                    "mana_ability",
                    "Prairie Stream — {T}: Add {U}.",
                    source_object_id="ps",
                ),
                _option("plains", "mana_ability", "Plains — {T}: Add {W}.", source_object_id="p1"),
                _option("island", "mana_ability", "Island — {T}: Add {U}.", source_object_id="i1"),
            ],
            context={"unpaid_mana": "{2}{W}"},
        )
    )
    assert response["selected_option_ids"] == ["plains"]


def test_cancelled_payment_is_not_retried_without_more_mana() -> None:
    policy = _policy()
    cast = _option(
        "cast-veto", "activated_ability", "Dovin's Veto — Cast Dovin's Veto", ability_type="spell"
    )
    window = [_option("pass", "pass_priority", "Pass priority"), cast]
    first = policy.decide(_request("priority", window, state=_state(step="precombat_main")))
    assert first["selected_option_ids"] == ["cast-veto"]
    policy.decide(
        _request(
            "mana_payment",
            [_option("cancel", "cancel_mana_payment", "Cancel mana payment")],
            context={"unpaid_mana": "{U}"},
            offset=2,
        )
    )
    again = policy.decide(
        _request("priority", window, state=_state(step="precombat_main"), offset=3)
    )
    assert again["selected_option_ids"] == ["pass"]
    richer = _state(step="precombat_main")
    richer["players"][0]["battlefield"].append(
        {"object_id": "land-new", "name": "Island", "tapped": False}
    )
    retried = policy.decide(_request("priority", window, state=richer, offset=4))
    assert retried["selected_option_ids"] == ["cast-veto"]


def test_one_or_more_sweep_takes_only_the_modes_that_hurt_the_table() -> None:
    state = _state(step="precombat_main")
    state["players"][0]["battlefield"].append(
        {"object_id": "mine-art", "name": "Sol Ring", "tapped": False}
    )
    for index, opponent in enumerate(state["players"][1:]):
        opponent["battlefield"] = [
            {
                "object_id": f"opp-{index}",
                "name": "Serra Angel",
                "tapped": False,
                "power": 4,
                "toughness": 4,
            }
        ]
    modes = [
        _option("gy", "mode", "exile all graveyards."),
        _option("ench", "mode", "exile all enchantments."),
        _option("crea", "mode", "exile all creatures."),
        _option("art", "mode", "exile all artifacts."),
    ]
    policy = _policy()
    first = policy.decide(_request("mode", modes, state=state))
    assert first["selected_option_ids"] == ["crea"]
    rest = [m for m in modes if m["option_id"] != "crea"]
    request = _request("mode", rest, state=state, offset=2)
    request["minimum_selections"] = 0
    assert policy.decide(request)["selected_option_ids"] == []


def test_reversed_free_cast_is_not_retried_forever() -> None:
    # #816/#817: XMage keeps a free-cast card whose cast was reversed (Shatter
    # with no artifact) and re-asks "Continue casting?" for a non-computer
    # player, so answering Yes to the identical cast prompt again loops the
    # engine without end. After "Continue casting?" follows a Yes, the same
    # cast prompt is not accepted again that turn; a different card still is.
    policy = _policy()
    cast = "Cast spell without paying its mana cost (Shatter [d67])?"
    other = "Cast spell without paying its mana cost (Shock [e12])?"
    cont = "You can cast 1 more spells for free. Continue casting?"

    def answer(prompt: str, offset: int) -> str:
        return policy.decide(_boolean("playforfree", prompt, offset=offset))["selected_option_ids"][
            0
        ]

    assert answer(cast, 1) == "yes"
    assert answer(cont, 2) == "yes"
    assert answer(cast, 3) == "no"
    # Continuing would only re-offer the refused card: the chain ends here.
    assert answer(cont, 4) == "no"
    assert answer(other, 5) == "yes"


def test_declined_copy_cast_ends_the_continue_chain() -> None:
    # Mizzix's Mastery (overload) removes a copied card only when one was
    # chosen and then asks "Continue to choose copies and cast?" while cards
    # remain. A seat that chose none and answers Yes is asked the same thing
    # again, so one pod ran into max_decisions=50000. After a choice of nothing
    # the chain ends; the question is answered normally otherwise.
    policy = _policy()
    ask = "Select up to one copied card to cast without paying its mana cost?"
    cont = "Continue to choose copies and cast?"

    def pick_nothing(offset: int) -> list[str]:
        request = _request("target", [], prompt=ask, offset=offset)
        request["minimum_selections"] = 0
        selected: list[str] = policy.decide(request)["selected_option_ids"]
        return selected

    def answer(prompt: str, offset: int) -> str:
        return policy.decide(_boolean("benefit", prompt, offset=offset))["selected_option_ids"][0]

    assert answer(cont, 1) == "yes"  # control: nothing declined yet, the chain is not ended
    assert pick_nothing(2) == []
    assert answer(cont, 3) == "no"
    assert answer(cont, 4) == "yes"  # the refusal is spent: a later chain is not capped


def _copy_spell_target(source_name: str, *stack: tuple[str, str]) -> dict[str, Any]:
    """Target choice of a copy-a-spell spell; ``stack`` is (object id, name), top of stack first."""
    options = [
        _option(
            object_id,
            "target",
            name,
            object_id=object_id,
            name=name,
            zone="stack",
            zone_index=index,
            source_card_id=f"card-{object_id}",
        )
        for index, (object_id, name) in enumerate(stack)
    ]
    request = _request(
        "target",
        options,
        context={"targeted": True, "outcome": "benefit", "required": True},
        prompt="Select an instant or sorcery spell",
        state=_state(step="precombat_main"),
    )
    request["source_object"] = {
        "source_object_id": "card-own",
        "ability_original_id": "own",
        "ability_type": "spell",
        "source_name": source_name,
    }
    return request


def test_a_spell_never_targets_itself() -> None:
    # CR 115.5. XMage lists the Wild Ricochet being cast among its own "target instant or sorcery
    # spell" options; the pilot took it and the copies copied one another for ever (precon pod
    # 031, plan seed 1, game seed 1: 6000 decisions at turn 21, one priority window slower than
    # the one before).
    own_first = _copy_spell_target(
        "Wild Ricochet", ("own", "Wild Ricochet"), ("swords", "Swords to Plowshares")
    )
    assert _policy().decide(own_first)["selected_option_ids"] == ["swords"]
    # Control: the same spell is a legal choice for another spell that stands on the stack.
    other = _copy_spell_target("Expansion", ("own", "Wild Ricochet"))
    other["source_object"]["ability_original_id"] = "expansion"
    other["source_object"]["source_object_id"] = "card-expansion"
    assert _policy().decide(other)["selected_option_ids"] == ["own"]


def test_a_seat_re_aims_only_a_few_copies_a_turn() -> None:
    # Wild Ricochet copies: the engine asks "Change this 1 of 1 target: X?" for every copy and the
    # pilot aimed each at another Wild Ricochet, so the stack grew without end (precon pod 031,
    # 6000 decisions at turn 21). Four re-aims a turn are allowed, the next ones keep the targets.
    policy = _policy()
    ask = "Change this 1 of 1 target: Wild Ricochet [1cc]?"

    def answer(prompt: str, offset: int) -> str:
        return policy.decide(_boolean("neutral", prompt, offset=offset))["selected_option_ids"][0]

    first = [answer(ask, offset) for offset in range(1, 5)]
    assert first == ["yes"] * 4  # control: the guard does not touch the first re-aims
    assert answer(ask, 5) == "no"
    assert answer(ask, 6) == "no"
    # Other may-prompts of the same seat are not affected by the spent count.
    assert answer("Pay {1}?", 7) == "yes"


def test_the_re_aim_count_starts_over_with_the_turn() -> None:
    policy = _policy()
    ask = "Change this 1 of 1 target: Wild Ricochet [1cc]?"
    for offset in range(1, 6):
        policy.decide(_boolean("neutral", ask, offset=offset))
    request = _boolean("neutral", ask, offset=6)
    request["pilot_state"]["turn_number"] = request["pilot_state"]["turn_number"] + 1
    assert policy.decide(request)["selected_option_ids"][0] == "yes"


_FILTER_FACTS: dict[str, Any] = {
    "mana_cost_white": 0,
    "mana_cost_blue": 0,
    "mana_cost_black": 0,
    "mana_cost_red": 0,
    "mana_cost_green": 0,
    "mana_cost_colorless": 0,
}


def _filter_land(pool_covers: bool) -> dict[str, Any]:
    # Sunscorched Divide, as the bridge reported it in a real game (r4_v5).
    return _option(
        "divide",
        "mana_ability",
        "Sunscorched Divide — {1}, {T}: Add {R}{W}.",
        **_FILTER_FACTS,
        mana_cost_generic=1,
        pool_covers_mana_cost=pool_covers,
        requires_tap_source=True,
        source_object_id="divide-object",
        source_tapped=False,
    )


def _pool_white() -> dict[str, Any]:
    return _option(
        "pool-white",
        "mana_pool",
        "Spend white mana from pool",
        mana_type="white",
        mana_available=1,
        advances_payment=True,
    )


def test_payment_feeds_the_pool_into_a_filter_land_when_plain_sources_cannot_finish() -> None:
    # Real game: Millikin ({2}) with Command Tower and Sunscorched Divide. The
    # pilot tapped Tower, spent its {W} on the spell, and the Divide it could
    # no longer fund left a payment only cancel could end, three times a turn.
    response = _policy().decide(
        _request(
            "mana_payment",
            [
                _option("cancel", "cancel_mana_payment", "Cancel mana payment"),
                _pool_white(),
                _filter_land(True),
            ],
            context={"unpaid_mana": "{2}"},
        )
    )
    assert response["selected_option_ids"] == ["divide"]


def test_payment_still_spends_a_lone_pool_candidate_when_plain_sources_suffice() -> None:
    plain = _option(
        "plains",
        "mana_ability",
        "Plains — {T}: Add {W}.",
        **_FILTER_FACTS,
        mana_cost_generic=0,
        source_object_id="plains-object",
    )
    response = _policy().decide(
        _request(
            "mana_payment",
            [
                _option("cancel", "cancel_mana_payment", "Cancel mana payment"),
                _pool_white(),
                plain,
                _filter_land(True),
            ],
            context={"unpaid_mana": "{2}"},
        )
    )
    assert response["selected_option_ids"] == ["pool-white"]
    # A filter land the pool cannot fund is never chosen either.
    response = _policy().decide(
        _request(
            "mana_payment",
            [
                _option("cancel", "cancel_mana_payment", "Cancel mana payment"),
                _pool_white(),
                _filter_land(False),
            ],
            context={"unpaid_mana": "{2}"},
        )
    )
    assert response["selected_option_ids"] == ["pool-white"]


_FREE_CAST_CARDS = ("Hellish Rebuke", "Light Up the Stage", "Rakdos Charm")


def _free_cast_pick() -> dict[str, Any]:
    request = _request(
        "choose_object",
        [
            _option(
                f"exiled-{index}",
                "choice",
                name,
                object_id=f"exiled-{index}",
                name=name,
                zone="exiled",
            )
            for index, name in enumerate(_FREE_CAST_CARDS)
        ],
        context={
            "targeted": False,
            "outcome": "playforfree",
            "target_description": "up to one card to cast",
            "target_name": "card to cast",
            "required": True,
        },
        prompt="Select up to one card to cast",
        state=_state(step="upkeep"),
    )
    request["minimum_selections"] = 0
    request["maximum_selections"] = 1
    return request


def _policy_that_cast(*names: str) -> ExternalPilotDecisionPolicy:
    """A policy whose seat 1 has cast the named spells earlier in the game.

    The pilot remembers the names of its own casts so it never targets its own spell on the
    stack; Izzet Chemister later exiles those very cards, so the free-cast choice offers
    cards whose names the pilot still holds as its own.
    """
    policy = _policy()
    casts = [
        _option(f"cast-{index}", "activated_ability", name, ability_type="spell", source_name=name)
        for index, name in enumerate(names)
    ]
    policy._remember_own_cast(1, casts, [str(cast["option_id"]) for cast in casts], turn=3)
    return policy


def test_free_cast_choice_picks_a_card() -> None:
    # Izzet Chemister ("Cast any number of cards exiled with this without paying their mana
    # costs") asks "Select up to one card to cast" with the engine's playforfree outcome.
    # Scored as a neutral target, each card carried the own-spell penalty, so every score was
    # negative, the pilot picked none and answered Yes to "Continue casting?" for 50000
    # decisions (precon pod, plan seed 4).
    response = _policy_that_cast(*_FREE_CAST_CARDS).decide(_free_cast_pick())
    assert len(response["selected_option_ids"]) == 1
    assert response["selected_option_ids"][0] in {f"exiled-{index}" for index in range(3)}


def test_free_cast_choice_is_not_widened_to_other_outcomes() -> None:
    # Control: the same frame under the neutral outcome keeps the old rule (min 0, every score
    # negative, nothing selected), so only the engine's playforfree outcome changed.
    request = _free_cast_pick()
    request["context"]["outcome"] = "neutral"
    response = _policy_that_cast(*_FREE_CAST_CARDS).decide(request)
    assert response["selected_option_ids"] == []


_VAULT_112 = {
    "source_object_id": "saga",
    "ability_original_id": "chapter-three",
    "ability_type": "triggered",
    "source_name": "Vault 112: Sadistic Simulation",
}


def _energy_amount(source: dict[str, Any], maximum: int = 4) -> dict[str, Any]:
    request = _request(
        "amount",
        [],
        context={"numeric_min": 0, "numeric_max": maximum, "outcome": "benefit"},
        prompt="How many {E} do you like to pay?",
        state=_state(step="precombat_main"),
    )
    request["minimum_selections"] = 0
    request["maximum_selections"] = 0
    request["source_object"] = source
    return request


def test_vault_112_chapter_three_pays_no_energy() -> None:
    # The chapter's free play reaches the land-or-spell callback from a caller outside the
    # declared decision classes (ADR section 28), which ends the game. Paying zero is legal.
    response = _policy().decide(_energy_amount(_VAULT_112))
    assert response["numeric_choice"] == 0


def test_other_energy_payments_are_not_declined() -> None:
    # Control: the same question from another source still goes to the pilot's own scoring,
    # which spends the energy it is asked for.
    other = dict(_VAULT_112, source_name="Aetherworks Marvel")
    response = _policy().decide(_energy_amount(other))
    assert response["numeric_choice"] > 0


_SLAUGHTER_CREATURES = ("Sun Titan", "Kor Spiritdancer", "Paradise Druid")
_SLAUGHTER_PROMPT = (
    "Select up to one any number of creatures you control with total power 4 or less "
    "(already selected total power {total})"
)


def _slaughter_state() -> dict[str, Any]:
    state = _state(step="precombat_main")
    state["players"][0]["battlefield"] += [
        {
            "object_id": f"creature-{index}",
            "name": name,
            "card_types": ["Creature"],
            "power": 1,
            "toughness": 2,
            "tapped": False,
        }
        for index, name in enumerate(_SLAUGHTER_CREATURES)
    ]
    return state


def _slaughter_pick(offered: tuple[int, ...], *, total: int = 0, offset: int = 1) -> dict[str, Any]:
    request = _request(
        "target",
        [
            _option(
                f"creature-{index}",
                "target",
                _SLAUGHTER_CREATURES[index],
                object_id=f"creature-{index}",
                name=_SLAUGHTER_CREATURES[index],
                zone="battlefield",
                zone_index=index,
            )
            for index in offered
        ],
        context={
            "targeted": True,
            "outcome": "boostcreature",
            "target_description": "any number of creatures you control with total power 4 or less",
            "target_name": "any number of creatures you control with total power 4 or less",
            "required": False,
        },
        prompt=_SLAUGHTER_PROMPT.format(total=total),
        state=_slaughter_state(),
        offset=offset,
    )
    request["minimum_selections"] = 0
    request["maximum_selections"] = 1
    request["source_object"] = {
        "source_object_id": "spell",
        "ability_original_id": "slaughter-the-strong",
        "ability_type": "spell",
        "source_name": "Slaughter the Strong",
    }
    return request


def test_running_selection_picks_each_creature_once_and_ends() -> None:
    # Slaughter the Strong asks for one creature at a time and takes a creature back out when
    # it is picked again, until a pick of nothing, then asks "End the selection" or
    # "Continue the selection". The pilot picked the one creature it could see every time, so
    # the selection toggled for 50000 decisions (precon pod, plan seed 5). It now picks each
    # creature once, picks nothing when none is left, and ends the selection.
    policy = _policy()

    def pick(offered: tuple[int, ...], offset: int) -> list[str]:
        selected: list[str] = policy.decide(_slaughter_pick(offered, offset=offset))[
            "selected_option_ids"
        ]
        return selected

    first = pick((0, 1, 2), 1)
    assert len(first) == 1
    second = pick((0, 1, 2), 2)
    assert len(second) == 1 and second != first
    third = pick((0, 1, 2), 3)
    assert len(third) == 1 and third not in (first, second)
    assert pick((0, 1, 2), 4) == []
    end = _boolean("detriment", "Creature selection", offset=5)
    assert policy.decide(end)["selected_option_ids"] == ["yes"]


def test_running_selection_with_a_single_creature_ends_after_one_pick() -> None:
    # The pod's frame: one creature on the table, offered again after it was picked.
    policy = _policy()
    first = policy.decide(_slaughter_pick((0,), offset=1))["selected_option_ids"]
    assert first == ["creature-0"]
    assert policy.decide(_slaughter_pick((0,), offset=2))["selected_option_ids"] == []


def test_selection_end_is_not_forced_on_other_may_prompts() -> None:
    # Control: with no selection just ended, the same may-prompt keeps the pilot's own answer
    # (a detriment question is declined), so only the answer straight after a selection changed.
    answer = _policy().decide(_boolean("detriment", "Creature selection", offset=1))
    assert answer["selected_option_ids"] == ["no"]


def test_a_target_prompt_without_a_running_total_is_not_a_selection() -> None:
    # Control: a plain optional target asked twice in a row keeps picking the best target.
    policy = _policy()
    request = _slaughter_pick((0,), offset=1)
    request["prompt"] = "Select up to one creature you control"
    assert policy.decide(request)["selected_option_ids"] == ["creature-0"]
    request["decision_offset"] = 2
    assert policy.decide(request)["selected_option_ids"] == ["creature-0"]


_COMMANDER = "Isamaru, Hound of Konda"


def _ward_state(
    *, stack: tuple[str, ...], commander_on_table: bool = True, lookalike: bool = False
) -> dict[str, Any]:
    state = _state(step="precombat_main")
    if lookalike:
        # Another player's card of the commander's name; it is no commander.
        state["players"][1]["battlefield"].append(
            {
                "object_id": "lookalike",
                "name": _COMMANDER,
                "power": 2,
                "toughness": 2,
                "tapped": False,
            }
        )
    battlefield: list[dict[str, Any]] = state["players"][0]["battlefield"]
    battlefield.append(
        {
            "object_id": "token",
            "name": "Saproling Token",
            "power": 1,
            "toughness": 1,
            "tapped": False,
        }
    )
    if commander_on_table:
        battlefield.append(
            {
                "object_id": "commander",
                "name": _COMMANDER,
                "power": 2,
                "toughness": 2,
                "tapped": False,
            }
        )
    state["commander_status"] = [{"owner_id": "actor", "name": _COMMANDER}]
    state["stack"] = [
        {"object_id": f"stack-{index}", "name": name, "controller_id": "actor"}
        for index, name in enumerate(stack)
    ]
    return state


def _ward_cast(name: str = "Timely Ward") -> dict[str, Any]:
    return _option(
        "cast",
        "activated_ability",
        f"{name} — Cast {name}",
        source_name=name,
        source_object_id="hand-0",
        ability_type="spell",
        mana_cost_white=1,
        mana_cost_generic=2,
        pool_covers_mana_cost=False,
        requires_tap_source=False,
        requires_untap_source=False,
        requires_sacrifice_source=False,
    )


def _ward_target(name: str, stack: tuple[str, ...], *, lookalike: bool = False) -> dict[str, Any]:
    options = [
        _option("token", "target", "Saproling Token", object_id="token", zone="battlefield"),
        _option("commander", "target", _COMMANDER, object_id="commander", zone="battlefield"),
    ]
    if lookalike:
        options.insert(
            0, _option("lookalike", "target", _COMMANDER, object_id="lookalike", zone="battlefield")
        )
    request = _request(
        "target",
        options,
        context={"targeted": True, "outcome": "boostcreature", "required": False},
        prompt="Select a creature",
        state=_ward_state(stack=stack, lookalike=lookalike),
    )
    request["source_object"] = {
        "source_object_id": "spell",
        "ability_original_id": "ward",
        "ability_type": "spell",
        "source_name": name,
    }
    return request


def test_commander_only_cast_is_not_offered_without_a_commander_outside_a_sorcery_window() -> None:
    # Timely Ward may be cast at instant speed only if it targets a commander. XMage offers
    # the cast anyway and fails it after the targets are chosen, which ended a precon game
    # (plan seed 5). With something on the stack and no commander on the table the pilot passes.
    state = _ward_state(stack=("Unfinished Business",), commander_on_table=False)
    response = _policy().decide(_request("priority", [_PASS, *_TAPS, _ward_cast()], state=state))
    assert response["selected_option_ids"] == ["pass"]


def test_commander_only_cast_is_offered_in_a_sorcery_window_and_with_a_commander() -> None:
    # Controls: the same cast with an empty stack in the actor's main phase, and the cast at
    # instant speed with a commander to aim at, are chosen as before.
    sorcery = _ward_state(stack=(), commander_on_table=False)
    response = _policy().decide(_request("priority", [_PASS, *_TAPS, _ward_cast()], state=sorcery))
    assert response["selected_option_ids"] == ["cast"]
    instant = _ward_state(stack=("Unfinished Business",))
    response = _policy().decide(_request("priority", [_PASS, *_TAPS, _ward_cast()], state=instant))
    assert response["selected_option_ids"] == ["cast"]


def test_commander_only_cast_targets_the_commander_outside_a_sorcery_window() -> None:
    # The pilot ranked the token first and the cast failed. Outside a sorcery window the
    # spell is on the stack with others, and only the commander is a legal way to cast it.
    stack = ("Timely Ward", "Unfinished Business")
    response = _policy().decide(_ward_target("Timely Ward", stack))
    assert response["selected_option_ids"] == ["commander"]


def test_commander_only_cast_does_not_target_another_card_of_the_commanders_name() -> None:
    # Two cards named like the commander were on one table (plan seed 9): the cast was aimed at
    # the other player's card, which is no commander, and failed. The target must be the commander.
    stack = ("Timely Ward", "Unfinished Business")
    response = _policy().decide(_ward_target("Timely Ward", stack, lookalike=True))
    assert response["selected_option_ids"] == ["commander"]


def test_commander_only_cast_is_not_offered_when_only_a_lookalike_stands_on_the_table() -> None:
    # The commander is not on the table, only another player's card with its name.
    state = _ward_state(stack=("Unfinished Business",), commander_on_table=False, lookalike=True)
    response = _policy().decide(_request("priority", [_PASS, *_TAPS, _ward_cast()], state=state))
    assert response["selected_option_ids"] == ["pass"]


def test_commander_only_target_rule_is_limited_to_that_card_and_timing() -> None:
    # Controls: the identical frame from another spell, or from Timely Ward in a sorcery
    # window (the spell alone on the stack), keeps the pilot's own ranking.
    stack = ("Timely Ward", "Unfinished Business")
    other = _policy().decide(_ward_target("Savannah Lions", stack))
    assert other["selected_option_ids"] == ["token"]
    sorcery = _policy().decide(_ward_target("Timely Ward", ("Timely Ward",)))
    assert sorcery["selected_option_ids"] == ["token"]


def _concierge_target(source_name: str, *names: str) -> dict[str, Any]:
    options = [
        _option(f"target-{index}", "target", name, object_id=f"obj-{index}", name=name)
        for index, name in enumerate(names)
    ]
    request = _request(
        "target",
        options,
        context={"targeted": True, "outcome": "removal", "required": True},
        prompt="Select up to one creature",
        state=_state(step="precombat_main"),
    )
    request["minimum_selections"] = 0
    request["source_object"] = {
        "source_object_id": "spell",
        "ability_original_id": "trigger",
        "ability_type": "triggered_nonmana",
        "source_name": source_name,
    }
    return request


def test_exile_and_suspend_is_never_aimed_at_a_token() -> None:
    # Sinister Concierge exiled a Vampire Token, the engine threw "Card must be in exile zone"
    # while giving it suspend, and the precon game ended (plan seed 3, game seed 103).
    only_token = _policy().decide(_concierge_target("Sinister Concierge", "Vampire Token"))
    assert only_token["selected_option_ids"] == []
    mixed = _policy().decide(
        _concierge_target("Sinister Concierge", "Vampire Token", "Archmage Emeritus")
    )
    assert mixed["selected_option_ids"] in ([], ["target-1"])


def test_the_token_rule_is_limited_to_the_exile_and_suspend_card() -> None:
    # Controls: another source keeps the pilot's own ranking and may aim at a token.
    other = _policy().decide(_concierge_target("Swords to Plowshares", "Vampire Token"))
    assert other["selected_option_ids"] == ["target-0"]
    # The card's own non-token targets are still reachable.
    card = _policy().decide(_concierge_target("Sinister Concierge", "Archmage Emeritus"))
    assert card["selected_option_ids"] == ["target-0"]


def _sacrifice_during_payment(
    payer_id: str, *names: str, asking: str = "szeras", minimum: int = 1
) -> list[str]:
    """The payment frame of an activation, then a sacrifice choice (a mana ability's or its own)."""
    policy = _policy()
    payment = _request(
        "mana_payment",
        [_option("cancel", "cancel_mana_payment", "Cancel"), *_TAPS],
        context={"unpaid_mana": "{1}"},
    )
    payment["source_object"] = {
        "source_object_id": payer_id,
        "ability_type": "activated_nonmana",
        "source_name": "Necron Overlord",
    }
    policy.decide(payment)
    options = [
        _option(f"sacrifice-{name}", "target", name, object_id=name, name=name) for name in names
    ]
    request = _request(
        "choose_object",
        options,
        context={"targeted": False, "outcome": "sacrifice", "required": False},
        prompt="Select another creature (to sacrifice)",
        offset=2,
    )
    request["minimum_selections"] = request["maximum_selections"] = minimum
    request["source_object"] = {
        "source_object_id": asking,
        "ability_type": "activated_mana" if asking == "szeras" else "activated_nonmana",
        "source_name": "Illuminor Szeras" if asking == "szeras" else "Necron Overlord",
    }
    return list(policy.decide(request)["selected_option_ids"])


def test_the_payment_of_an_activation_never_sacrifices_its_own_source() -> None:
    # Illuminor Szeras' mana ability sacrifices another creature. Paying Necron Overlord's
    # {X}, {T} ability with it, the pilot sacrificed the Overlord, the {T} cost found nothing
    # to tap and the game stopped (plan seed 1, game seed 101, pod 024).
    for names in (("Zeta Overlord", "Tomb Blade"), ("Tomb Blade", "Zeta Overlord")):
        assert _sacrifice_during_payment("Zeta Overlord", *names) == ["sacrifice-Tomb Blade"]


def test_the_payment_source_is_sacrificed_when_nothing_else_is_on_offer() -> None:
    # The pilot cannot avoid it, so the engine's single option stays.
    assert _sacrifice_during_payment("Zeta Overlord", "Zeta Overlord") == [
        "sacrifice-Zeta Overlord"
    ]


def test_the_payment_source_stays_on_offer_when_the_cost_needs_more_than_the_rest() -> None:
    # Breya, Etherium Shaper's "Sacrifice two artifacts" with Breya and one Thopter: dropping
    # Breya left one option for two picks and the game stopped (plan seed 4, game seed 104,
    # pod 014). A choice the payment's source cannot be spared from keeps it.
    chosen = _sacrifice_during_payment("breya", "breya", "thopter", asking="szeras", minimum=2)
    assert sorted(chosen) == ["sacrifice-breya", "sacrifice-thopter"]


def test_the_activations_own_sacrifice_cost_may_take_its_source() -> None:
    # The same cost asked by the activation itself (not by another permanent's mana ability):
    # nothing is being paid for with the source, so it is a plain option.
    chosen = _sacrifice_during_payment("breya", "breya", "thopter", asking="breya", minimum=2)
    assert sorted(chosen) == ["sacrifice-breya", "sacrifice-thopter"]


def test_another_sacrifice_choice_keeps_the_pilots_own_ranking() -> None:
    # Control: with no payment in progress (a fresh policy) the pilot ranks the options itself.
    request = _request(
        "choose_object",
        [
            _option("sacrifice-a", "target", "Zeta Overlord", object_id="Zeta Overlord"),
            _option("sacrifice-b", "target", "Tomb Blade", object_id="Tomb Blade"),
        ],
        context={"targeted": False, "outcome": "sacrifice", "required": False},
        prompt="Select another creature (to sacrifice)",
    )
    request["source_object"] = {"source_object_id": "szeras", "source_name": "Illuminor Szeras"}
    assert len(_policy().decide(request)["selected_option_ids"]) == 1


def _morph_cast(name: str) -> dict[str, Any]:
    return _option(
        "morph",
        "activated_ability",
        f"{name} — Cast {name} using Morph",
        source_name=name,
        source_object_id="hand-0",
        ability_type="spell",
        mana_cost_generic=3,
        pool_covers_mana_cost=False,
        requires_tap_source=False,
        requires_untap_source=False,
        requires_sacrifice_source=False,
    )


def test_an_aura_is_not_cast_face_down() -> None:
    # XMage offers "Cast Gift of Doom using Morph" and then throws at the Aura check when the
    # face-down permanent enters, which ended a precon game (plan seed 7). The pilot passes.
    response = _policy().decide(
        _request(
            "priority", [_PASS, *_TAPS, _morph_cast("Gift of Doom")], state=_ward_state(stack=())
        )
    )
    assert response["selected_option_ids"] == ["pass"]


def test_the_face_down_rule_is_limited_to_auras() -> None:
    # Controls: the same morph cast of a creature, and the ordinary cast of the Aura, are chosen
    # as before.
    state = _ward_state(stack=())
    creature = _policy().decide(
        _request("priority", [_PASS, *_TAPS, _morph_cast("Exalted Angel")], state=state)
    )
    assert creature["selected_option_ids"] == ["morph"]
    aura = _policy().decide(
        _request("priority", [_PASS, *_TAPS, _ward_cast("Gift of Doom")], state=state)
    )
    assert aura["selected_option_ids"] == ["cast"]


_NINJUTSU_LABEL = (
    "Yuriko, the Tiger's Shadow — Commander ninjutsu {U}{B} <i>({U}{B} Return an unblocked "
    "attacker you control to hand: Put this card onto the battlefield from your hand or the "
    "command zone tapped and attacking.)</i>"
)


def _ninjutsu(source_object_id: str) -> dict[str, Any]:
    return _option(
        "ninjutsu",
        "activated_ability",
        _NINJUTSU_LABEL,
        source_name="Yuriko, the Tiger's Shadow",
        source_object_id=source_object_id,
        ability_type="activated_nonmana",
        mana_cost_blue=1,
        mana_cost_black=1,
        pool_covers_mana_cost=False,
        requires_tap_source=False,
        requires_untap_source=False,
        requires_sacrifice_source=False,
    )


def _ninjutsu_state(*, ninja_in: str) -> dict[str, Any]:
    state = _state(step="declare_blockers")
    ninja = {"object_id": "ninja", "name": "Yuriko, the Tiger's Shadow", "tapped": False}
    state["players"][0].setdefault(ninja_in, []).append(ninja)
    return state


@pytest.mark.parametrize("zone", ["battlefield", "graveyard", "exile"])
def test_ninjutsu_is_not_activated_for_a_card_that_is_not_in_hand_or_command_zone(
    zone: str,
) -> None:
    # Commander ninjutsu is a Zone.ALL ability, so XMage offers it for the ninja wherever it
    # lies. The reveal cost only pays from the hand or the command zone: the activation failed
    # after the mana was spent and ended a precon game (plan seeds 7 and 9, Yuriko in play and in
    # the graveyard).
    state = _ninjutsu_state(ninja_in=zone)
    response = _policy().decide(
        _request("priority", [_PASS, *_TAPS, _ninjutsu("ninja")], state=state)
    )
    assert response["selected_option_ids"] == ["pass"]


def test_ninjutsu_is_not_activated_for_a_card_that_is_in_no_visible_zone() -> None:
    # The ninja lies in the library (or anywhere else the state does not list), XMage still
    # offers its Zone.ALL ability and the reveal cost fails after the mana is spent (precon pod
    # 010, game seed 501, Yuriko was neither in hand nor in the command zone).
    state = _state(step="declare_blockers")
    response = _policy().decide(
        _request("priority", [_PASS, *_TAPS, _ninjutsu("ninja")], state=state)
    )
    assert response["selected_option_ids"] == ["pass"]


def test_ninjutsu_from_the_command_zone_is_still_activated() -> None:
    state = _ninjutsu_state(ninja_in="command")
    response = _policy().decide(
        _request("priority", [_PASS, *_TAPS, _ninjutsu("ninja")], state=state)
    )
    assert response["selected_option_ids"] == ["ninjutsu"]


def test_ninjutsu_from_the_hand_is_still_activated() -> None:
    # Control: the same offer with the ninja in hand is chosen as before.
    state = _ninjutsu_state(ninja_in="hand")
    response = _policy().decide(
        _request("priority", [_PASS, *_TAPS, _ninjutsu("ninja")], state=state)
    )
    assert response["selected_option_ids"] == ["ninjutsu"]


_SENTINEL_LABEL = (
    "Jaspera Sentinel — {T}, Tap an untapped creature you control: Add one mana of any color."
)


def _sentinel_payment(*, other_creature: bool) -> dict[str, Any]:
    state = _state(step="precombat_main")
    battlefield: list[dict[str, Any]] = state["players"][0]["battlefield"]
    battlefield.append(
        {
            "object_id": "sentinel",
            "name": "Jaspera Sentinel",
            "power": 1,
            "toughness": 2,
            "tapped": False,
        }
    )
    if other_creature:
        battlefield.append(
            {
                "object_id": "bear",
                "name": "Grizzly Bears",
                "power": 2,
                "toughness": 2,
                "tapped": False,
            }
        )
    sentinel = _option(
        "sentinel",
        "mana_ability",
        _SENTINEL_LABEL,
        source_name="Jaspera Sentinel",
        source_object_id="sentinel",
        ability_type="activated_mana",
        mana_ability=True,
        pool_covers_mana_cost=True,
        requires_tap_source=True,
        requires_untap_source=False,
        requires_sacrifice_source=False,
        source_tapped=False,
    )
    forest = _option("forest", "mana_ability", "Forest — {T}: Add {G}.", source_name="Forest")
    cancel = _option("cancel", "cancel_mana_payment", "Cancel mana payment")
    request = _request(
        "mana_payment",
        [cancel, sentinel, forest],
        context={"unpaid_mana": "{1}"},
        prompt="{1}",
        state=state,
    )
    request["source_object"] = {"source_name": "Sol Ring", "ability_type": "spell"}
    return request


def test_a_tap_creature_mana_cost_is_not_paid_with_the_source_as_the_only_creature() -> None:
    # Jaspera Sentinel taps itself for {T}, so "Tap an untapped creature you control" needs a
    # second creature. XMage offered it alone on the table and failed the payment (plan seed 9).
    response = _policy().decide(_sentinel_payment(other_creature=False))
    assert response["selected_option_ids"] == ["forest"]


def test_a_tap_creature_mana_cost_is_still_offered_with_a_creature_to_tap() -> None:
    # Control: with another untapped creature the ability is selectable as before (the choice
    # between it and a Forest is the pilot's own).
    request = _sentinel_payment(other_creature=True)
    assert _policy().decide(request)["selected_option_ids"] in (["forest"], ["sentinel"])
    assert not tap_creature_cost_unpayable(_SENTINEL_LABEL, "sentinel", request["pilot_state"])
    alone = _sentinel_payment(other_creature=False)
    assert tap_creature_cost_unpayable(_SENTINEL_LABEL, "sentinel", alone["pilot_state"])


_TEKUTHAL_LABEL = (
    "Tekuthal, Inquiry Dominus — {1}{U/P}{U/P}, Remove three counters from among other "
    "artifacts, creatures, and planeswalkers you control: Put an indestructible counter on {this}."
)


def _tekuthal_state(*charge: int) -> dict[str, Any]:
    """A table where Tekuthal sits beside one permanent per entry of ``charge`` counters."""
    state = _state(step="precombat_main")
    battlefield: list[dict[str, Any]] = state["players"][0]["battlefield"]
    battlefield.append(
        {
            "object_id": "tekuthal",
            "name": "Tekuthal, Inquiry Dominus",
            "counters": [],
            "tapped": False,
        }
    )
    battlefield.extend(
        {
            "object_id": f"vessel-{index}",
            "name": "Inspirit, Flagship Vessel",
            "counters": [{"type": "charge", "count": count}],
            "tapped": False,
        }
        for index, count in enumerate(charge)
    )
    return state


def _tekuthal_activation() -> dict[str, Any]:
    return _option(
        "tekuthal",
        "activated_ability",
        _TEKUTHAL_LABEL,
        source_name="Tekuthal, Inquiry Dominus",
        source_object_id="tekuthal",
        ability_type="activated_nonmana",
        mana_cost_generic=1,
        pool_covers_mana_cost=False,
        requires_tap_source=False,
        requires_untap_source=False,
        requires_sacrifice_source=False,
    )


def test_counter_cost_the_table_cannot_fund_is_not_activated() -> None:
    # XMage offers "Remove three counters from among other ..." while any such permanent
    # exists and fails the activation when the counters on all of them fall short, which
    # ended a precon game (plan seed 5, Inspirit's two charge counters). The pilot passes.
    for charge in ((), (2,), (1, 1)):
        state = _tekuthal_state(*charge)
        response = _policy().decide(
            _request("priority", [_PASS, *_TAPS, _tekuthal_activation()], state=state)
        )
        assert response["selected_option_ids"] == ["pass"], charge


def test_counter_cost_the_table_can_fund_is_still_offered() -> None:
    # Controls: three counters among the other permanents (in one pile or several), and the
    # source's own counters not counting for an "other" cost.
    for charge in ((3,), (2, 1), (1, 1, 1)):
        state = _tekuthal_state(*charge)
        response = _policy().decide(
            _request("priority", [_PASS, *_TAPS, _tekuthal_activation()], state=state)
        )
        assert response["selected_option_ids"] == ["tekuthal"], charge
    own = _tekuthal_state(2)
    own["players"][0]["battlefield"][-2]["counters"] = [{"type": "indestructible", "count": 5}]
    response = _policy().decide(
        _request("priority", [_PASS, *_TAPS, _tekuthal_activation()], state=own)
    )
    assert response["selected_option_ids"] == ["pass"]


_TAYAM_LABEL = (
    "Tayam, Luminous Enigma — {3}, Remove three counters from creatures you control: Mill three "
    "cards, then return a permanent card with mana value 3 or less from your graveyard to the "
    "battlefield."
)


def _tayam_activation() -> dict[str, Any]:
    option = _tekuthal_activation()
    option["option_id"] = "tayam"
    option["label"] = _TAYAM_LABEL
    option["metadata"].update(source_name="Tayam, Luminous Enigma", source_object_id="tayam")
    return option


def test_counter_cost_without_among_is_read_too() -> None:
    # Tayam words the same cost "from creatures you control" (plan seed 12: two counters on one
    # creature, the activation failed). Two counters are short of three, three are enough.
    short = _policy().decide(
        _request("priority", [_PASS, *_TAPS, _tayam_activation()], state=_tekuthal_state(2))
    )
    assert short["selected_option_ids"] == ["pass"]
    enough = _policy().decide(
        _request("priority", [_PASS, *_TAPS, _tayam_activation()], state=_tekuthal_state(3))
    )
    assert enough["selected_option_ids"] == ["tayam"]


def test_counter_cost_takes_one_type_from_each_permanent() -> None:
    # XMage removes counters of one type from each chosen permanent, so two creatures holding
    # three counters of two types between them (a +1/+1 and a vigilance counter on one, a
    # vigilance counter on the other) cannot pay three (plan seed 12: Tayam failed after the
    # counter choice). A third creature with a counter, or a stack of three, can.
    state = _tekuthal_state(1)
    state["players"][0]["battlefield"][-1]["counters"] = [
        {"type": "+1/+1", "count": 1},
        {"type": "vigilance", "count": 1},
    ]
    state["players"][0]["battlefield"].append(
        {
            "object_id": "second",
            "name": "Kathril, Aspect Warper",
            "counters": [{"type": "vigilance", "count": 1}],
            "tapped": False,
        }
    )
    short = _policy().decide(
        _request("priority", [_PASS, *_TAPS, _tayam_activation()], state=state)
    )
    assert short["selected_option_ids"] == ["pass"]
    state["players"][0]["battlefield"].append(
        {
            "object_id": "third",
            "name": "Sol Ring",
            "counters": [{"type": "charge", "count": 1}],
            "tapped": False,
        }
    )
    enough = _policy().decide(
        _request("priority", [_PASS, *_TAPS, _tayam_activation()], state=state)
    )
    assert enough["selected_option_ids"] == ["tayam"]


def _paying_tayam(*piles: int) -> tuple[ExternalPilotDecisionPolicy, dict[str, Any]]:
    """A policy that just chose Tayam's activation, on a table with one creature per pile."""
    state = _tekuthal_state(*piles)
    policy = _policy()
    chosen = policy.decide(
        _request("priority", [_PASS, *_TAPS, _tayam_activation()], state=state, offset=1)
    )
    assert chosen["selected_option_ids"] == ["tayam"]
    return policy, state


def _pick_creatures(
    state: dict[str, Any], offset: int, *, minimum: int, maximum: int = 3
) -> dict[str, Any]:
    options = [
        _option(f"vessel-{index}", "choose_object_option", "Inspirit, Flagship Vessel")
        for index in range(len(state["players"][0]["battlefield"]) - 4)
    ]
    request = _request("choose_object", options, state=state, offset=offset)
    request["minimum_selections"] = minimum
    request["maximum_selections"] = maximum
    return request


def test_counter_cost_is_paid_from_the_biggest_piles_first_and_stops_at_the_number() -> None:
    # Tayam asks for creatures one pick after the other. The seat takes the biggest pile, and once
    # the piles cover the three counters it declines the optional pick (plan seed 12 chose
    # creatures with one counter each and came up short).
    policy, state = _paying_tayam(1, 5, 2)
    first = policy.decide(_pick_creatures(state, 2, minimum=1))
    assert first["selected_option_ids"] == ["vessel-1"]
    done = policy.decide(_pick_creatures(state, 3, minimum=0, maximum=2))
    assert done["selected_option_ids"] == []


def test_counter_cost_takes_further_piles_until_the_number_is_covered() -> None:
    policy, state = _paying_tayam(1, 2, 1)
    first = policy.decide(_pick_creatures(state, 2, minimum=1))
    assert first["selected_option_ids"] == ["vessel-1"]
    second = policy.decide(_pick_creatures(state, 3, minimum=0, maximum=2))
    assert second["selected_option_ids"] == ["vessel-0"]
    done = policy.decide(_pick_creatures(state, 4, minimum=0, maximum=1))
    assert done["selected_option_ids"] == []


_KATHRIL_PROMPT = (
    "Choose a counter to remove from <font color='#DAA520' object_id='#a1b2'>Kathril, Aspect "
    "Warper</font> [#a1b2]"
)


def _kathril_choice(state: dict[str, Any], offset: int) -> dict[str, Any]:
    state["players"][0]["battlefield"].append(
        {
            "object_id": "kathril",
            "name": "Kathril, Aspect Warper",
            "counters": [
                {"type": "trample", "count": 1},
                {"type": "+1/+1", "count": 5},
                {"type": "vigilance", "count": 1},
            ],
            "tapped": False,
        }
    )
    options = [
        {**_option(f"counter-{label}", "choice_option", label), "metadata": {"choice": label}}
        for label in ("trample", "+1/+1", "vigilance")
    ]
    return _request("choice", options, state=state, prompt=_KATHRIL_PROMPT, offset=offset)


def test_counter_cost_removes_the_biggest_counter_pile_of_the_permanent() -> None:
    policy, state = _paying_tayam(3)
    response = policy.decide(_kathril_choice(state, 2))
    assert response["selected_option_ids"] == ["counter-+1/+1"]


def test_counter_choice_outside_a_counter_cost_keeps_the_default_pick() -> None:
    # Control: the same question while the seat is not paying such a cost is not answered by the
    # pile rule.
    policy = _policy()
    state = _tekuthal_state(1)
    request = _kathril_choice(state, 1)
    assert (
        policy._counter_type_for_cost(1, state, request["legal_options"], _KATHRIL_PROMPT) is None
    )


def test_counter_cost_takes_as_many_counters_of_a_pile_as_it_may() -> None:
    policy, state = _paying_tayam(3)
    prompt = "Choose how many counters (+1/+1) to remove from Kathril, Aspect Warper as payment"
    context = {"numeric_min": 1, "numeric_max": 3, "outcome": "unboostcreature"}
    request = _request("amount", [], state=state, prompt=prompt, context=context, offset=2)
    request["minimum_selections"] = 0
    request["maximum_selections"] = 0
    assert policy.decide(request)["numeric_choice"] == 3


_ION_STORM_LABEL = (
    "Ion Storm — {1}{R}, Remove a +1/+1 counter or a charge counter from a permanent you control: "
    "Ion Storm deals 2 damage to any target."
)
_MOUNTAIN = _option("tap-r", "mana_ability", "Mountain — {T}: Add {R}.", source_name="Mountain")


def _ion_storm_activation() -> dict[str, Any]:
    option = _tekuthal_activation()
    option["option_id"] = "ion-storm"
    option["label"] = _ION_STORM_LABEL
    option["metadata"].update(
        source_name="Ion Storm", source_object_id="ion-storm", mana_cost_red=1, mana_cost_generic=1
    )
    return option


def _ion_storm_choice(state: dict[str, Any]) -> dict[str, Any]:
    return _request(
        "priority", [_PASS, *_TAPS, _MOUNTAIN, _ion_storm_activation()], state=state, offset=1
    )


def test_counter_cost_on_a_permanent_without_the_counter_is_not_activated() -> None:
    # XMage lets Ion Storm's cost pick any permanent the player controls and fails the whole
    # activation when that one holds neither counter (plan seed 15). With no +1/+1 or charge
    # counter on the table the pilot passes; with one of them it activates.
    nothing = _policy().decide(_ion_storm_choice(_tekuthal_state()))
    assert nothing["selected_option_ids"] == ["pass"]
    other_kind = _tekuthal_state(1)
    other_kind["players"][0]["battlefield"][-1]["counters"] = [{"type": "vigilance", "count": 4}]
    assert _policy().decide(_ion_storm_choice(other_kind))["selected_option_ids"] == ["pass"]
    charged = _policy().decide(_ion_storm_choice(_tekuthal_state(1)))
    assert charged["selected_option_ids"] == ["ion-storm"]


def _paying_ion_storm(
    state: dict[str, Any],
) -> ExternalPilotDecisionPolicy:
    policy = _policy()
    assert policy.decide(_ion_storm_choice(state))["selected_option_ids"] == ["ion-storm"]
    return policy


def _kind_choice(state: dict[str, Any]) -> dict[str, Any]:
    options = [
        {
            **_option(
                "p1p1", "choose_use_option", "Remove a +1/+1 counter from a permanent you control"
            ),
            "metadata": {"value": True},
        },
        {
            **_option(
                "charge",
                "choose_use_option",
                "Remove a charge counter from a permanent you control",
            ),
            "metadata": {"value": False},
        },
    ]
    prompt = (
        "Remove a +1/+1 counter from a permanent you control or "
        "remove a charge counter from a permanent you control?"
    )
    return _request("choose_use", options, state=state, prompt=prompt, offset=2)


def test_counter_cost_pays_with_the_kind_the_table_holds() -> None:
    # "Remove a +1/+1 counter or remove a charge counter" asks for the kind first. The seat
    # answers the kind that sits on a permanent it controls (the first listed would fail here).
    state = _tekuthal_state(2)
    policy = _paying_ion_storm(state)
    assert policy.decide(_kind_choice(state))["selected_option_ids"] == ["charge"]
    both = _tekuthal_state(1)
    both["players"][0]["battlefield"][-1]["counters"] = [
        {"type": "charge", "count": 1},
        {"type": "+1/+1", "count": 3},
    ]
    policy = _paying_ion_storm(both)
    assert policy.decide(_kind_choice(both))["selected_option_ids"] == ["p1p1"]


def test_counter_cost_picks_the_permanent_that_holds_the_counter() -> None:
    state = _tekuthal_state(0, 2, 1)
    policy = _paying_ion_storm(state)
    options = [
        _option(object_id, "choose_object_option", name)
        for object_id, name in (
            ("land-0", "Plains"),
            ("tekuthal", "Tekuthal, Inquiry Dominus"),
            ("vessel-0", "Inspirit, Flagship Vessel"),
            ("vessel-1", "Inspirit, Flagship Vessel"),
            ("vessel-2", "Inspirit, Flagship Vessel"),
        )
    ]
    request = _request("choose_object", options, state=state, offset=3)
    assert policy.decide(request)["selected_option_ids"] == ["vessel-1"]
    # Control: a seat that is not paying such a cost is left to the ordinary pick.
    fresh = _policy()
    assert fresh._decide_kind_cost_object(1, state, options, 1) is None


_ENCORE_LABEL = (
    "Striking Sliver — Encore {1} <i>({1}, Exile this card from your graveyard: For each opponent, "
    "create a token copy that attacks that opponent this turn if able. They gain haste. Sacrifice "
    "them at the beginning of the next end step. Activate only as a sorcery.)</i>"
)


def _encore_activation() -> dict[str, Any]:
    option = _tekuthal_activation()
    option["option_id"] = "encore"
    option["label"] = _ENCORE_LABEL
    option["metadata"].update(source_name="Striking Sliver", source_object_id="striking-sliver")
    return option


def test_encore_waits_until_no_opponent_is_out_of_the_game() -> None:
    # XMage makes one Encore token per opponent still in the game but then walks the turn-start
    # opponents, which still include a player who left this turn, and runs out of tokens (plan
    # seed 16, NoSuchElementException). The pilot holds Encore back once an opponent is out.
    state = _state(step="precombat_main")
    request = _request("priority", [_PASS, *_TAPS, _encore_activation()], state=state)
    assert _policy().decide(request)["selected_option_ids"] == ["encore"]
    state["players"][2]["has_lost"] = True
    state["players"][2]["life"] = -3
    request = _request("priority", [_PASS, *_TAPS, _encore_activation()], state=state)
    assert _policy().decide(request)["selected_option_ids"] == ["pass"]


def _locked_state(
    lock: str | None, *, holder: str = "opponent-1", lost: bool = False
) -> dict[str, Any]:
    state = _ward_state(stack=())
    if lock is not None:
        player = next(p for p in state["players"] if p["player_id"] == holder)
        player["has_lost"] = lost
        player["battlefield"].append(
            {"object_id": "lock", "name": lock, "power": 9, "toughness": 10, "tapped": False}
        )
    return state


def _lock_cast(name: str, *, red: int, generic: int) -> dict[str, Any]:
    return _option(
        "cast",
        "activated_ability",
        f"{name} — Cast {name}",
        source_name=name,
        source_object_id="hand-0",
        ability_type="spell",
        mana_cost_red=red,
        mana_cost_generic=generic,
        pool_covers_mana_cost=False,
        requires_tap_source=False,
        requires_untap_source=False,
        requires_sacrifice_source=False,
    )


def _lock_choice(state: dict[str, Any], option: dict[str, Any]) -> str:
    response = _policy().decide(_request("priority", [_PASS, *_TAPS, option], state=state))
    return str(response["selected_option_ids"][0])


_BRISELA = "Brisela, Voice of Nightmares"


def test_brisela_holds_back_the_spells_it_forbids() -> None:
    # Brisela forbids opponents' spells with mana value 3 or less, but only once the spell is on
    # the stack, so the engine still offers the cast and then refuses it after the first
    # question (plan seed 19, Prosperous Bandit, "priority cast failed"). The pilot passes.
    bandit = _lock_cast("Prosperous Bandit", red=1, generic=2)
    assert _lock_choice(_locked_state(None), bandit) == "cast"
    assert _lock_choice(_locked_state(_BRISELA), bandit) == "pass"


def test_brisela_leaves_other_casts_alone() -> None:
    # Controls: Brisela on the actor's own side, with its holder out of the game, or a spell
    # of mana value 4 or more (a four-mana cast with a fourth land to pay for it).
    bandit = _lock_cast("Prosperous Bandit", red=1, generic=2)
    assert _lock_choice(_locked_state(_BRISELA, holder="actor"), bandit) == "cast"
    assert _lock_choice(_locked_state(_BRISELA, lost=True), bandit) == "cast"
    state = _locked_state(_BRISELA)
    state["players"][0]["battlefield"].append(
        {"object_id": "land-3", "name": "Plains", "tapped": False}
    )
    four = _lock_cast("Prosperous Bandit", red=1, generic=3)
    request = _request("priority", [_PASS, *_TAPS, four], state=state)
    assert _policy().decide(request)["selected_option_ids"] == ["cast"]


def test_void_winnower_holds_back_even_and_x_spells() -> None:
    # Void Winnower forbids even mana values through the same late check. Odd values stay
    # castable; a spell with {X} is held back because its value depends on the X chosen.
    winnower = "Void Winnower"
    two = _lock_cast("Prosperous Bandit", red=1, generic=1)
    three = _lock_cast("Prosperous Bandit", red=1, generic=2)
    assert _lock_choice(_locked_state(winnower), two) == "pass"
    assert _lock_choice(_locked_state(winnower), three) == "cast"
    fireball = _lock_cast("Fireball", red=1, generic=0)
    assert _lock_choice(_locked_state(None), fireball) == "cast"
    assert _lock_choice(_locked_state(winnower), fireball) == "pass"


_DIG_PROMPT = "Pay 1 life and look at the next 5 cards?"
_LIM_DUL = {
    "source_object_id": "vault",
    "ability_original_id": "lim-duls-vault",
    "ability_type": "spell",
    "source_name": "Lim-Dûl's Vault",
}


def _dig(offset: int, source: dict[str, Any] | None = None) -> dict[str, Any]:
    request = _boolean("benefit", _DIG_PROMPT, offset=offset)
    request["source_object"] = source or _LIM_DUL
    return request


def test_life_dig_stops_after_a_few_digs() -> None:
    # Lim-Dul's Vault lets a player pay 1 life and look at five more cards "as many times as
    # you choose". The pilot cannot judge the cards, so it paid every time: one precon game
    # (plan seed 5) ran for nearly an hour. After three digs in a row the answer is No.
    policy = _policy()
    answers = [policy.decide(_dig(offset))["selected_option_ids"][0] for offset in range(1, 6)]
    assert answers == ["yes", "yes", "yes", "no", "no"]


def test_life_dig_count_ends_with_the_effect() -> None:
    # Controls: a priority window means the effect resolved, so a later cast starts afresh; and
    # the same question from another ability is counted on its own.
    policy = _policy()
    for offset in range(1, 4):
        assert policy.decide(_dig(offset))["selected_option_ids"] == ["yes"]
    assert policy.decide(_dig(4))["selected_option_ids"] == ["no"]
    policy.decide(_request("priority", [_PASS], state=_state(step="precombat_main"), offset=5))
    assert policy.decide(_dig(6))["selected_option_ids"] == ["yes"]
    other = dict(_LIM_DUL, ability_original_id="another-vault")
    for offset in range(7, 10):
        assert policy.decide(_dig(offset, other))["selected_option_ids"] == ["yes"]
