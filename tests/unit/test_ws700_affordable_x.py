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

Limitation, stated rather than papered over: the pinned bridge sends neither
the non-X mana value nor the X count on an ``announce_x`` frame, so real
engine traffic keeps the pre-existing whole-domain behaviour. The Lab reads
those two facts when the Core supplies them and never invents a cost; the
controls below pin that silence explicitly.
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


# --- Control: unreadable affordability keeps the pre-existing behaviour ------


@pytest.mark.parametrize(
    "context",
    [
        # No cost facts at all: today's pinned bridge shape for announce_x.
        {"numeric_min": 0, "numeric_max": INT_MAX, "outcome": "benefit"},
        # Present but unusable. None of these may become a guess.
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
def test_unreadable_cost_keeps_the_pre_fix_domain(context: dict[str, Any]) -> None:
    assert _announced(_policy(), _announce_x_request(context=context)) == INT_MAX


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
