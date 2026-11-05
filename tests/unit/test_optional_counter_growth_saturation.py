"""Strategic ranking of an optional repeated self-counter trigger."""

from copy import deepcopy
from dataclasses import replace

import pytest

from commander_lab.agents import GenericCommanderPilot
from commander_lab.engine.rules.full_game_pilot.counter_growth import saturated_self_counter
from commander_lab.models import PilotStrength
from tests.unit.test_full_game_pilot_mana_and_may import _boolean, _policy


def _frame():
    req = _boolean(
        "benefit",
        "Whenever one or more +1/+1 counters are put on another creature you control, you may put a +1/+1 counter on <b>Enduring Scalelord</b> [abc].",
    )
    req["source_object"] = {
        "source_object_id": "source",
        "source_name": "Enduring Scalelord",
        "ability_type": "triggered_nonmana",
        "ability_original_id": "original",
    }
    req["pilot_state"]["players"][0]["battlefield"] = [
        {
            "object_id": "source",
            "name": "Enduring Scalelord",
            "power": 497,
            "toughness": 497,
            "damage": 0,
            "abilities": [
                "Flying",
                "Whenever one or more +1/+1 counters are put on another creature you control, you may put a +1/+1 counter on {this}.",
            ],
            "face_down": False,
        },
        {
            "object_id": "peer",
            "name": "Enduring Scalelord",
            "power": 4,
            "toughness": 4,
            "damage": 0,
            "abilities": [
                "Flying",
                "Whenever one or more +1/+1 counters are put on another creature you control, you may put a +1/+1 counter on {this}.",
            ],
            "face_down": False,
        },
    ]
    return req


def _answer(req):
    return _policy().decide(req)["selected_option_ids"]


def test_saturated_source_declines_with_small_peer():
    assert _answer(_frame()) == ["no"]


@pytest.mark.parametrize(
    "strength", [PilotStrength.AVERAGE, PilotStrength.STRONG, PilotStrength.NEAR_OPTIMAL_HEURISTIC]
)
def test_strengths_rank_decline(strength):
    policy = _policy()
    runtime = policy._pilots[1]
    config = runtime.binding.config.model_copy(update={"strength": strength})
    policy._pilots[1] = replace(runtime, pilot=GenericCommanderPilot(config))
    assert policy.decide(_frame())["selected_option_ids"] == ["no"]


def test_other_large_peer_does_not_block_decision():
    req = _frame()
    req["pilot_state"]["players"][0]["battlefield"][1].update(power=506, toughness=506)
    assert _answer(req) == ["no"]


@pytest.mark.parametrize("peer_damage", [0, 500])
def test_another_large_body_reduces_the_value_of_further_growth(peer_damage):
    req = _frame()
    own = req["pilot_state"]["players"][0]["battlefield"]
    own[0].update(power=70, toughness=70)
    own[1].update(power=506, toughness=506, damage=peer_damage)
    assert _answer(req) == (["no"] if peer_damage == 0 else ["yes"])


def test_a_pure_stat_replacement_does_not_create_an_extra_counter_payoff():
    req = _frame()
    req["pilot_state"]["players"][0]["battlefield"].append(
        {
            "object_id": "scales",
            "name": "Hardened Scales",
            "power": 0,
            "toughness": 0,
            "damage": 0,
            "abilities": [],
            "face_down": False,
        }
    )
    assert _answer(req) == ["no"]


@pytest.mark.parametrize("name", ["Enduring Scalelord", "Colossal Dreadmaw"])
def test_counter_engines_do_not_start_an_unbounded_opposing_size_race(name):
    req = _frame()
    req["pilot_state"]["players"][1]["battlefield"].append(
        {
            "object_id": "large-opponent",
            "name": name,
            "power": 1000,
            "toughness": 1000,
            "damage": 0,
            "abilities": [],
            "face_down": False,
        }
    )
    assert _answer(req) == (["no"] if name == "Enduring Scalelord" else ["yes"])


def test_an_opposing_body_is_not_a_friendly_backup():
    req = _frame()
    req["pilot_state"]["players"][0]["battlefield"][0].update(power=70, toughness=70)
    opponent = deepcopy(req["pilot_state"]["players"][0]["battlefield"][1])
    opponent.update(object_id="opposing-peer", power=1000, toughness=1000)
    req["pilot_state"]["players"][1]["battlefield"].append(opponent)
    assert _answer(req) == ["yes"]


@pytest.mark.parametrize("land_state", ["absent", "zero", "animated"])
def test_observed_opponent_land_stats_enter_combat_comparison(land_state):
    req = _frame()
    land = {"object_id": "land", "name": "Plains", "abilities": [], "face_down": False}
    if land_state != "absent":
        size = 1000 if land_state == "animated" else 0
        land.update(power=size, toughness=size, damage=0)
    req["pilot_state"]["players"][1]["battlefield"].append(land)
    assert _answer(req) == (["yes"] if land_state == "animated" else ["no"])


def _stack(depth):
    rule = (
        "stack ability (Whenever one or more +1/+1 counters are put on another creature "
        "you control, you may put a +1/+1 counter on {this}.)"
    )
    return [{"object_id": str(index), "name": rule} for index in range(depth)]


def _draw_after_decline(depth=9):
    policy = _policy()
    request = _frame()
    request["pilot_state"]["stack"] = _stack(10)
    assert policy.decide(request)["selected_option_ids"] == ["no"]
    draw = deepcopy(request)
    draw["source_object"] = None
    draw["prompt"] = "Draw game because of infinite looping?"
    draw["context"]["outcome"] = "detriment"
    draw["pilot_state"]["stack"] = _stack(depth)
    return policy, draw


def test_draw_proposal_can_be_declined_after_observed_counter_progress():
    policy, draw = _draw_after_decline()
    assert policy.decide(draw)["selected_option_ids"] == ["no"]
    assert policy.decide(draw)["selected_option_ids"] == ["yes"]


def test_later_draw_refusal_requires_further_stack_reduction():
    policy, draw = _draw_after_decline()
    assert policy.decide(draw)["selected_option_ids"] == ["no"]
    draw["pilot_state"]["stack"] = _stack(8)
    assert policy.decide(draw)["selected_option_ids"] == ["no"]
    assert policy.decide(draw)["selected_option_ids"] == ["yes"]


def test_draw_refusal_can_follow_body_development_but_stops_at_utility_cap():
    policy, draw = _draw_after_decline(11)
    peer = draw["pilot_state"]["players"][0]["battlefield"][1]
    peer.update(power=1000, toughness=1000)
    assert policy.decide(draw)["selected_option_ids"] == ["no"]
    peer.update(power=2000, toughness=2000)
    draw["pilot_state"]["stack"] = _stack(12)
    assert policy.decide(draw)["selected_option_ids"] == ["yes"]


@pytest.mark.parametrize("depth", [10, 11])
def test_no_stack_reduction_keeps_draw_agreement(depth):
    policy, draw = _draw_after_decline(depth)
    assert policy.decide(draw)["selected_option_ids"] == ["yes"]


@pytest.mark.parametrize(
    "change",
    ["turn", "game", "mixed", "unknown", "only_yes", "no_history", "payoff", "granted"],
)
def test_uncertain_draw_progress_keeps_prior_draw_strategy(change):
    policy, draw = _draw_after_decline()
    if change == "turn":
        draw["pilot_state"]["turn_number"] += 1
    elif change == "game":
        draw["pilot_state"]["game_id"] = "another-game"
    elif change == "mixed":
        draw["pilot_state"]["stack"][0]["name"] = "Other recurring ability"
    elif change == "unknown":
        draw["pilot_state"].pop("stack")
    elif change == "only_yes":
        draw["legal_options"] = draw["legal_options"][:1]
    elif change == "no_history":
        policy = _policy()
    elif change == "payoff":
        draw["pilot_state"]["players"][0]["battlefield"].append(
            {
                "object_id": "payoff",
                "name": "Fathom Mage",
                "power": 1,
                "toughness": 1,
                "damage": 0,
                "face_down": False,
                "abilities": [],
            }
        )
    elif change == "granted":
        draw["pilot_state"]["players"][0]["battlefield"][0]["abilities"].append(
            "Whenever a +1/+1 counter is put on a creature, draw a card."
        )
    assert policy.decide(draw)["selected_option_ids"] == ["yes"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_source",
        "other_owner",
        "missing_original",
        "other_prompt",
        "small_source",
        "missing_power",
        "bad_damage",
        "no_peer",
        "unknown_life",
        "payoff",
        "only_yes",
        "unknown_permanent",
        "granted_payoff",
        "missing_abilities",
        "face_down",
        "wrong_ability_type",
        "unknown_source",
        "missing_toughness",
        "missing_peer_id",
        "damage_payoff",
        "win_payoff",
    ],
)
def test_uncertain_or_other_choices_keep_existing_ranking(mutation):
    req = deepcopy(_frame())
    state = req["pilot_state"]
    own = state["players"][0]["battlefield"]
    if mutation == "missing_source":
        req.pop("source_object")
    elif mutation == "other_owner":
        state["players"][1]["battlefield"].append(own.pop(0))
    elif mutation == "missing_original":
        req["source_object"]["ability_original_id"] = ""
    elif mutation == "other_prompt":
        req["prompt"] = "Put a +1/+1 counter on target creature?"
    elif mutation == "small_source":
        own[0]["power"] = 70
    elif mutation == "missing_power":
        own[0].pop("power")
    elif mutation == "bad_damage":
        own[0]["damage"] = True
    elif mutation == "no_peer":
        own.pop()
    elif mutation == "unknown_life":
        state["players"][1]["life"] = None
    elif mutation == "payoff":
        own.append(
            {
                "object_id": "payoff",
                "name": "Fathom Mage",
                "power": 1,
                "toughness": 1,
                "damage": 0,
                "face_down": False,
                "abilities": [],
            }
        )
    elif mutation == "only_yes":
        req["legal_options"] = req["legal_options"][:1]
    elif mutation == "unknown_permanent":
        own.append({"object_id": "unknown", "name": "Unknown permanent"})
    elif mutation == "granted_payoff":
        own[1]["abilities"].append("Whenever a +1/+1 counter is put on a creature, draw a card.")
    elif mutation == "missing_abilities":
        own[1].pop("abilities")
    elif mutation == "face_down":
        own[1]["face_down"] = True
    elif mutation == "wrong_ability_type":
        req["source_object"]["ability_type"] = "activated"
    elif mutation == "unknown_source":
        req["source_object"]["source_object_id"] = "unknown"
    elif mutation == "missing_toughness":
        own[0].pop("toughness")
    elif mutation == "missing_peer_id":
        own[1].pop("object_id")
    elif mutation == "damage_payoff":
        own[1]["abilities"].append("Whenever a +1/+1 counter is put on a creature, deal 1 damage.")
    elif mutation == "win_payoff":
        own[1]["abilities"].append("If a creature has twenty counters on it, you win the game.")
    if mutation == "unknown_life":
        assert not saturated_self_counter(state, req["source_object"], req["prompt"])
    else:
        assert _answer(req) == ["yes"]
