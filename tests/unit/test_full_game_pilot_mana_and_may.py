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
