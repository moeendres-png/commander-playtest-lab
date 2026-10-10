"""Full-game pilot: announce a mana X its own visible mana can pay (#700).

Real-deck 4P seed 4 aborts on turn 31: seat 2 activates Shelob, Dread
Weaver's ``{X}{1}{B}`` ability, XMage offers ``announce_x`` over the whole
0..Integer.MAX_VALUE domain, the benefit-biased deterministic pilot takes the
ceiling, the activation cannot be paid, ``activateAbility`` returns false with
no cancellation flag, and the bridge fails the game.

The engine keeps the domain. The repair is pilot judgement: the Lab adds an
``affordable_max`` strategy hint derived from the acting principal's own
visible mana and the announced cost, and the pilot strategy picks inside
[min, min(max, affordable_max)]. Membership is still validated against the
authoritative domain, which is never clamped, narrowed or rewritten here.

Where the cost comes from: the pinned bridge sends neither the non-X mana
value nor the X count on an ``announce_x`` frame, so the Lab takes the non-X
value off the priority option that started the same cast or activation, where
the bridge's own ``enrichAbilityCostFacts`` summary already reported it, and
takes the X count from the engine's own prompt. Which prompts are a mana X at
all, and the count, both come from that same prompt; the Lab never invents a
cost. The controls below pin the unreadable and non-mana cases explicitly.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from commander_lab.agents import GenericCommanderPilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    FullGameProtocolError,
    _RuntimePilot,
)
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
)

INT_MAX = 2147483647
SHELOB_PROMPT = "Announce the value for {X}"
SHELOB_COST = "{X}{1}{B}"
STOCHASTIC_SEEDS = 200


def _policy(
    mode: PilotDecisionMode = PilotDecisionMode.DETERMINISTIC,
    scenario_seed: int = 20261010,
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
    return ExternalPilotDecisionPolicy(tuple(runtimes), scenario_seed)  # type: ignore[arg-type]


def _state(
    *, untapped_lands: int = 5, tapped_lands: int = 0, pool_black: int = 0
) -> dict[str, Any]:
    """Seat 2's own board as the pilot sees it: nothing but its own zones."""
    lands = [
        {
            "object_id": f"land-{index}",
            "name": "Swamp",
            "tapped": index >= untapped_lands,
            "face_down": False,
            "abilities": ["{T}: Add {B}."],
        }
        for index in range(untapped_lands + tapped_lands)
    ]
    actor = {
        "player_id": "actor",
        "seat": 0,
        "life": 34,
        "hand_count": 4,
        "library_count": 71,
        "graveyard_count": 6,
        "battlefield": lands,
        "graveyard": [],
        "command": [{"object_id": "commander", "name": "Shelob, Dread Weaver"}],
        "hand": [{"object_id": "hand-0", "name": "Consider"}],
        "mana_pool": {
            "white": 0,
            "blue": 0,
            "black": pool_black,
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
        for seat in (1, 3, 4)
    ]
    return {
        "game_id": "engine-opaque",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 31,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "precombat_main",
        "step": None,
        "players": [actor, *opponents],
        "stack": [],
    }


def _announce_x_request(
    *,
    decision_class: str = "announce_x",
    context: dict[str, Any] | None = None,
    source_object: dict[str, Any] | None = None,
    prompt: str = SHELOB_PROMPT,
    state: dict[str, Any] | None = None,
    offset: int = 1,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "decision_id": f"opaque-{decision_class}",
        "decision_offset": offset,
        "actor_id": "actor",
        "decision_class": decision_class,
        "pilot_state": state if state is not None else _state(),
        "context": context
        if context is not None
        else {
            "numeric_min": 0,
            "numeric_max": INT_MAX,
            "outcome": "benefit",
            "numeric_non_x_mana_value": 2,
            "numeric_x_symbols": 1,
        },
        "minimum_selections": 0,
        "maximum_selections": 0,
        "legal_options": [],
        "prompt": prompt,
    }
    if source_object is not None:
        request["source_object"] = source_object
    return request


def _announced(policy: ExternalPilotDecisionPolicy, request: dict[str, Any]) -> int:
    choice = policy.decide(request)["numeric_choice"]
    assert isinstance(choice, int) and not isinstance(choice, bool)
    return choice


# --- The defect: a mana X the pilot cannot pay --------------------------------


def test_deterministic_mana_x_stays_within_its_visible_mana() -> None:
    # Fails at the base: the benefit bias returns 2147483647 and the {X}{1}{B}
    # activation can never be paid. 5 untapped sources - {1}{B} leaves X <= 3.
    response = _policy().decide(_announce_x_request())
    assert response["numeric_choice"] == 3


def test_stochastic_mana_x_stays_within_its_visible_mana() -> None:
    for seed in range(STOCHASTIC_SEEDS):
        policy = _policy(PilotDecisionMode.STOCHASTIC, scenario_seed=seed)
        for offset in (1, 2):
            choice = _announced(policy, _announce_x_request(offset=offset))
            assert 0 <= choice <= 3, f"seed {seed} offset {offset} announced {choice}"


def test_pooled_mana_counts_toward_the_budget() -> None:
    # One Swamp already tapped: 1 floated black + 3 untapped Swamps, less the
    # {1}{B} rest of the cost, leaves X <= 2.
    state = _state(untapped_lands=3, tapped_lands=1, pool_black=1)
    assert _announced(_policy(), _announce_x_request(state=state)) == 2


def test_multi_x_cost_shares_the_budget_between_its_symbols() -> None:
    # {X}{X}: five untapped sources are two X at most, before any other cost.
    response = _policy().decide(
        _announce_x_request(
            context={
                "numeric_min": 0,
                "numeric_max": INT_MAX,
                "outcome": "benefit",
                "numeric_non_x_mana_value": 0,
                "numeric_x_symbols": 2,
            },
            prompt="Announce the value for {X}{X}",
        )
    )
    assert response["numeric_choice"] == 2


def test_source_metadata_can_supply_the_cost_facts() -> None:
    # The bridge may attach the announced ability's cost as source metadata;
    # the Lab reads either the request context or source metadata.
    response = _policy().decide(
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={
                "source_object_id": "shelob",
                "source_name": "Shelob, Dread Weaver",
                "ability_type": "activated",
                "numeric_non_x_mana_value": 2,
                "numeric_x_symbols": 1,
            },
        )
    )
    assert response["numeric_choice"] == 3


def test_hint_never_narrows_the_authoritative_domain() -> None:
    # An authoritative domain narrower than the budget is used verbatim.
    response = _policy().decide(
        _announce_x_request(
            context={
                "numeric_min": 0,
                "numeric_max": 2,
                "outcome": "benefit",
                "numeric_non_x_mana_value": 2,
                "numeric_x_symbols": 1,
            }
        )
    )
    assert response["numeric_choice"] == 2


def test_hint_never_falls_below_the_authoritative_minimum() -> None:
    # Nothing affordable: the only in-domain choice is the Core's own minimum,
    # so the pilot picks it instead of returning an out-of-domain value.
    response = _policy().decide(
        _announce_x_request(
            context={
                "numeric_min": 7,
                "numeric_max": INT_MAX,
                "outcome": "benefit",
                "numeric_non_x_mana_value": 9,
                "numeric_x_symbols": 1,
            },
            state=_state(untapped_lands=1),
        )
    )
    assert response["numeric_choice"] == 7


# --- Controls: the same huge domain elsewhere keeps its behaviour ------------


def test_non_x_amount_decision_with_the_same_domain_keeps_current_behaviour() -> None:
    # getAmount is not a mana X, so it gets no affordability hint at all.
    response = _policy().decide(_announce_x_request(decision_class="amount"))
    assert response["numeric_choice"] == INT_MAX


def test_target_amount_keeps_current_behaviour() -> None:
    response = _policy().decide(_announce_x_request(decision_class="target_amount"))
    assert response["numeric_choice"] == INT_MAX


def test_detriment_and_neutral_announce_x_stay_inside_the_band() -> None:
    for outcome, expected in (("detriment", 0), ("neutral", 1)):
        response = _policy().decide(
            _announce_x_request(
                context={
                    "numeric_min": 0,
                    "numeric_max": INT_MAX,
                    "outcome": outcome,
                    "numeric_non_x_mana_value": 2,
                    "numeric_x_symbols": 1,
                }
            )
        )
        assert response["numeric_choice"] == expected


def _priority_request(
    *,
    source_id: str,
    mana_cost: dict[str, int],
    source_name: str = "Shelob, Dread Weaver",
    option_type: str = "activated_ability",
    label: str = "{X}{1}{B}",
    offset: int = 1,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A priority window whose option carries the bridge's own cost facts.

    Exactly what ``XmageFullGamePlayer.priority`` builds for one playable
    ability: ``abilityMetadata`` -> ``enrichAbilityCostFacts``, so the seven
    ``mana_cost_*`` integers are the engine's translation of
    ``ManaCostsImpl.getMana()``.
    """
    return {
        "decision_id": "opaque-priority",
        "decision_offset": offset,
        "actor_id": "actor",
        "decision_class": "priority",
        "pilot_state": state if state is not None else _state(),
        "context": {},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": [
            {
                "option_id": "priority-pass",
                "option_type": "pass_priority",
                "label": "Pass priority",
                "metadata": {},
            },
            {
                "option_id": "priority:activated",
                "option_type": option_type,
                "label": label,
                "metadata": {
                    "source_object_id": source_id,
                    "source_name": source_name,
                    "ability_type": "activated",
                    "mana_ability": False,
                    "requires_tap_source": True,
                    "requires_untap_source": False,
                    "requires_sacrifice_source": False,
                    **mana_cost,
                },
            },
        ],
        "prompt": "Choose priority action",
    }


SHELOB_COST_FACTS: dict[str, int] = {
    "mana_cost_white": 0,
    "mana_cost_blue": 0,
    "mana_cost_black": 1,
    "mana_cost_red": 0,
    "mana_cost_green": 0,
    "mana_cost_generic": 1,
    "mana_cost_colorless": 0,
}

ZERO_COST_FACTS: dict[str, int] = {key: 0 for key in SHELOB_COST_FACTS}


def _activated_ability_x() -> int:
    """Seat 2 announces the X of the {X}{1}{B} ability it just activated.

    Two consecutive frames on one policy: the priority window that started the
    activation, then the ``announce_x`` the engine raises inside it. Five
    untapped Swamps less the {1}{B} leaves X <= 3.
    """
    policy = _policy()
    chosen = policy.decide(_priority_request(source_id="obj-shelob", mana_cost=SHELOB_COST_FACTS))
    assert chosen["selected_option_ids"] != ["priority-pass"], "the ability must be selected"
    return _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": "obj-shelob", "source_name": "Shelob, Dread Weaver"},
        ),
    )


def test_activated_ability_x_is_budgeted_from_the_chosen_priority_cost() -> None:
    # Fails at 00c81d51: nothing remembers the chosen option, the announce_x
    # frame carries no cost, and the benefit bias returns 2147483647.
    assert _activated_ability_x() == 3


def test_spell_x_is_budgeted_from_the_chosen_priority_cost() -> None:
    # Same two frames for a spell cast at priority; the engine offers a
    # SpellAbility through the same priority option list, so it carries the
    # same cost facts under the same key.
    policy = _policy()
    state = _state()
    chosen = policy.decide(
        _priority_request(
            source_id="obj-spell",
            source_name="Shelob, Dread Weaver",
            option_type="activated_ability",
            label="Cast Shelob, Dread Weaver",
            mana_cost=SHELOB_COST_FACTS,
            state=state,
        )
    )
    assert chosen["selected_option_ids"] != ["priority-pass"]
    choice = _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": "obj-spell"},
            state=state,
        ),
    )
    assert choice == 3


def test_announced_x_from_another_source_gets_the_budget_alone() -> None:
    # The remembered cost is keyed by the engine's own source id: an announce
    # for a different source cannot borrow it, so the bounded fallback applies.
    policy = _policy()
    policy.decide(_priority_request(source_id="obj-shelob", mana_cost=SHELOB_COST_FACTS))
    choice = _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": "obj-other"},
        ),
    )
    assert choice == 5


def test_another_seats_cost_is_never_borrowed() -> None:
    # Memory is per seat: seat 2's selection says nothing about seat 3's X.
    policy = _policy()
    policy.decide(_priority_request(source_id="obj-shelob", mana_cost=SHELOB_COST_FACTS))
    other_seat = dict(_state())
    other_seat["seat"] = 2
    other_seat["actor_id"] = "actor-3"
    other_seat["priority_player_id"] = "actor-3"
    other_seat["active_player_id"] = "actor-3"
    other_seat["players"] = [
        {**other_seat["players"][0], "player_id": "actor-3", "seat": 2},
        *other_seat["players"][1:],
    ]
    choice = _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": "obj-shelob"},
            state=other_seat,
        ),
    )
    assert choice == 5


def test_the_next_priority_decision_of_a_seat_invalidates_its_memory() -> None:
    # A remembered cost must never outlive the action it described: one more
    # priority window for the same seat drops it before choosing again.
    policy = _policy()
    policy.decide(_priority_request(source_id="obj-shelob", mana_cost=SHELOB_COST_FACTS))
    policy.decide(
        _priority_request(
            source_id="obj-shelob",
            mana_cost=SHELOB_COST_FACTS,
            offset=2,
        )
    )
    choice = _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": "obj-shelob"},
            offset=3,
        ),
    )
    assert choice == 3


def test_passing_priority_remembers_nothing() -> None:
    # Only the pass option is on offer: no cost is remembered, so the bounded
    # fallback applies to any later announce rather than a borrowed cost.
    policy = _policy()
    request = _priority_request(source_id="obj-shelob", mana_cost=SHELOB_COST_FACTS)
    request["legal_options"] = [request["legal_options"][0]]
    response = policy.decide(request)
    assert response["selected_option_ids"] == ["priority-pass"]
    choice = _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": "obj-shelob"},
        ),
    )
    assert choice == 5


def test_unreadable_priority_cost_never_becomes_a_number() -> None:
    # A cost breakdown the Lab cannot read is dropped whole, not partially
    # summed: the announce falls back to the budget rather than to a number
    # built out of whichever fields happened to parse.
    policy = _policy()
    broken = {**SHELOB_COST_FACTS, "mana_cost_generic": "1"}
    policy.decide(_priority_request(source_id="obj-shelob", mana_cost=broken))
    choice = _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": "obj-shelob"},
        ),
    )
    assert choice == 5


def test_x_symbol_count_comes_from_the_engine_prompt() -> None:
    # {X}{X}{1}{B}: XMage's VariableManaCost.getText() prints each symbol on
    # its own, so the engine prompt is "Announce the value for {X}{X}" and
    # holds the count the bridge never publishes. Five untapped sources less
    # the {1}{B} leaves 3 mana to share between the two symbols: X <= 1.
    policy = _policy()
    policy.decide(_priority_request(source_id="obj-twox", mana_cost=SHELOB_COST_FACTS))
    choice = _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": "obj-twox"},
            prompt="Announce the value for {X}{X}",
        ),
    )
    assert choice == 1


def test_every_x_symbol_of_a_wider_cost_shares_the_same_budget() -> None:
    # Three symbols on a cost with nothing else in it: five untapped sources
    # over three symbols is X <= 1, and the prompt is what says three.
    policy = _policy()
    policy.decide(_priority_request(source_id="obj-threex", mana_cost=ZERO_COST_FACTS))
    choice = _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": "obj-threex"},
            prompt="Announce the value for {X}{X}{X}",
        ),
    )
    assert choice == 1


def test_the_remembered_cost_is_consumed_by_the_announce_that_used_it() -> None:
    # One cost is announced once. The remembered value is taken, not copied,
    # so a second announce_x for the same source before the next priority
    # decision of that seat cannot answer from the same cost again: it falls
    # back to the visible budget, 5 instead of 3.
    policy = _policy()
    policy.decide(_priority_request(source_id="obj-shelob", mana_cost=SHELOB_COST_FACTS))
    first = _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": "obj-shelob"},
        ),
    )
    assert first == 3
    second = _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": "obj-shelob"},
            offset=3,
        ),
    )
    assert second == 5


def test_a_cost_stated_on_the_announce_frame_wins_over_the_memory() -> None:
    # A cost read directly off the announce frame is the engine's own latest
    # statement and is used in preference to what priority reported earlier.
    policy = _policy()
    policy.decide(_priority_request(source_id="obj-shelob", mana_cost=SHELOB_COST_FACTS))
    choice = _announced(
        policy,
        _announce_x_request(
            context={
                "numeric_min": 0,
                "numeric_max": INT_MAX,
                "outcome": "benefit",
                "numeric_non_x_mana_value": 4,
                "numeric_x_symbols": 1,
            },
            source_object={"source_object_id": "obj-shelob"},
        ),
    )
    assert choice == 1


# --- Control: unreadable cost falls back to the budget alone -----------------


@pytest.mark.parametrize(
    "context",
    [
        # No cost facts on the announce frame: what the pinned bridge sends.
        {"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
        # Present but unusable. None of these may become a guess: the answer is
        # the budget, which none of these values could have produced.
        {
            "numeric_min": 0,
            "numeric_max": INT_MAX,
            "outcome": "benefit",
            "numeric_non_x_mana_value": "2",
            "numeric_x_symbols": 1,
        },
        {
            "numeric_min": 0,
            "numeric_max": INT_MAX,
            "outcome": "benefit",
            "numeric_non_x_mana_value": 2,
            "numeric_x_symbols": 0,
        },
        {
            "numeric_min": 0,
            "numeric_max": INT_MAX,
            "outcome": "benefit",
            "numeric_non_x_mana_value": -2,
            "numeric_x_symbols": 1,
        },
        {
            "numeric_min": 0,
            "numeric_max": INT_MAX,
            "outcome": "benefit",
            "numeric_non_x_mana_value": True,
            "numeric_x_symbols": 1,
        },
        {
            "numeric_min": 0,
            "numeric_max": INT_MAX,
            "outcome": "benefit",
            "numeric_non_x_mana_value": 2,
        },
    ],
    ids=["absent", "non-integer", "zero-symbols", "negative", "boolean", "symbols-absent"],
)
def test_unreadable_cost_falls_back_to_the_budget_alone(context: dict[str, Any]) -> None:
    # The bounded fallback: non-X cost 0 over a single X symbol, so the whole
    # visible budget is the ceiling. Five untapped Swamps, not 2147483647.
    assert _announced(_policy(), _announce_x_request(context=context)) == 5


def test_budget_fallback_is_not_a_mana_budget_for_a_non_mana_x() -> None:
    # Player.announceX also serves the engine's non-mana VariableCostImpl
    # prompt, which prints its own "{X}" and then the action's own text:
    # "Announce the value for {X} (remove X counters)". A power/toughness or
    # counter X is not paid in mana, so the pool must not bound it. Only the
    # engine's whole mana prompt, the prefix plus nothing but "{X}" symbols,
    # is a mana X.
    response = _policy().decide(
        _announce_x_request(
            prompt="Announce the value for {X} (remove X counters)",
            context={
                "numeric_min": 0,
                "numeric_max": INT_MAX,
                "outcome": "benefit",
            },
        )
    )
    assert response["numeric_choice"] == INT_MAX


def test_a_non_mana_x_is_not_budgeted_even_with_a_remembered_mana_cost() -> None:
    # The same source id and the same remembered cost, but the engine is now
    # asking for a counter, not mana. The cost is not consumed as mana either:
    # only a mana announcement is a use of it.
    policy = _policy()
    policy.decide(_priority_request(source_id="obj-shelob", mana_cost=SHELOB_COST_FACTS))
    choice = _announced(
        policy,
        _announce_x_request(
            prompt="Announce the value for {X} (remove X counters)",
            context={"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": "obj-shelob"},
        ),
    )
    assert choice == INT_MAX


def test_untapped_lands_without_readable_mana_ability_text_do_not_raise_the_budget() -> None:
    # Only "add <mana>" ability text counts, and only while the permanent is
    # untapped and face up. Four of five Swamps are tapped here, and the
    # fifth's text is not a mana ability, so the pilot believes it has none.
    state = _state()
    battlefield = state["players"][0]["battlefield"]
    for item in battlefield:
        item["abilities"] = ["Flying."]  # a real permanent, no mana ability
    assert _announced(_policy(), _announce_x_request(state=state)) == 0


def test_face_down_mana_source_is_not_counted() -> None:
    state = _state()
    state["players"][0]["battlefield"][0]["face_down"] = True
    assert _announced(_policy(), _announce_x_request(state=state)) == 2


def test_opponent_boards_are_never_read() -> None:
    # Affordability comes from the actor's own zones only: four hidden
    # opponents' worth of untapped, mana-ability-bearing permanents must not
    # move the answer.
    state = _state()
    for opponent in state["players"][1:]:
        opponent["battlefield"] = [
            {
                "object_id": f"opp-land-{index}",
                "name": "Swamp",
                "tapped": False,
                "face_down": False,
                "abilities": ["{T}: Add {B}."],
            }
            for index in range(3)
        ]
    assert _announced(_policy(), _announce_x_request(state=state)) == 3


# --- The domain stays authoritative and still fails closed ------------------


def test_hint_does_not_relax_out_of_domain_validation() -> None:
    class _CeilingPilot(GenericCommanderPilot):
        def choose_number(self, state: Any, domain: dict[str, Any], rng: random.Random) -> int:
            return INT_MAX + 1

    config = PilotConfig(
        pilot_name="auto", strength=PilotStrength.AVERAGE, mode=PilotDecisionMode.DETERMINISTIC
    )
    hostile = _CeilingPilot(config)
    runtimes = [
        _RuntimePilot(
            binding=FullGamePilotBinding(
                seat=seat,
                deck_id=f"fixture-{seat}",
                strategy="generic",
                commander_names=("Isamaru, Hound of Konda",),
                config=config,
                pilot_identity="GenericCommanderPilot",
                pilot_version="1.0.0",
                decision_policy_version="xmage-full-game-policy-1.0.0",
            ),
            pilot=hostile if seat == 1 else GenericCommanderPilot(config),
        )
        for seat in range(1, 5)
    ]
    policy = ExternalPilotDecisionPolicy(tuple(runtimes), 20261010)  # type: ignore[arg-type]
    with pytest.raises(FullGameProtocolError, match="outside authoritative domain"):
        policy.decide(_announce_x_request())


def test_cost_facts_never_repair_malformed_bounds() -> None:
    # The hint is a strategy input; bounds stay strict and still fail closed.
    with pytest.raises(FullGameProtocolError):
        _policy().decide(
            _announce_x_request(
                context={
                    "numeric_min": 0,
                    "numeric_non_x_mana_value": 2,
                    "numeric_x_symbols": 1,
                }
            )
        )
