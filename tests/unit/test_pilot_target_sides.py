"""Whose side a target belongs on, who gets a gift, how close a player is to dead (#989 phase 1).

Each rule was measured on nine recorded precon games before it was written: 44 of 172 target
choices with a side to take went to the wrong one (a destroy aimed at the pilot's own token, a
+4/+4 on an opponent's creature, Humble Defector handed to the strongest opponent, a "target
player loses 7 life" aimed at the pilot). Every test has a control that shows the rule changes
nothing it should not.
"""

from __future__ import annotations

from typing import Any

from commander_lab.engine.rules.full_game_pilot_targets import (
    commander_clock_bonus,
    commander_damage_dealt,
    commander_damage_taken,
    life_clock,
    target_side,
)
from tests.unit.test_full_game_pilot_mana_and_may import _option, _policy, _request, _state

ACTOR = "actor"


def _perm(object_id: str, name: str, power: int, toughness: int) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "name": name,
        "power": power,
        "toughness": toughness,
        "tapped": False,
        "controller_id": "?",
    }


def _give(state: dict[str, Any], seat: int, *permanents: dict[str, Any]) -> None:
    owner = state["players"][seat]
    for item in permanents:
        owner["battlefield"].append({**item, "controller_id": owner["player_id"]})


def _target_request(
    outcome: str,
    options: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    source: str = "Some Spell",
    minimum: int = 1,
) -> dict[str, Any]:
    request = _request(
        "target",
        options,
        context={"outcome": outcome, "required": minimum > 0, "targeted": True},
        state=state,
        prompt="Select a target",
    )
    request["minimum_selections"] = minimum
    request["source_object"] = {
        "ability_type": "spell",
        "source_name": source,
        "source_object_id": f"stack-{source}",
        "ability_original_id": f"ability-{source}",
    }
    return request


def _permanent(object_id: str, name: str) -> dict[str, Any]:
    return _option(object_id, "target", name, name=name, object_id=object_id, zone="battlefield")


def _player(index: int) -> dict[str, Any]:
    # "Full Game Seat N" is seat N-1; the option id is the engine's, never the state's.
    return _option(f"u{index}", "target", f"Full Game Seat {index + 1}", object_id=f"u{index}")


def _choose(request: dict[str, Any]) -> list[str]:
    return _policy().decide(request)["selected_option_ids"]


def _strong_actor(state: dict[str, Any]) -> None:
    # The actor is the stronger player, as it was when the old code aimed a destroy at its own
    # token: its own threat score outweighed the small value of the opponent's creature.
    _give(
        state,
        0,
        _perm("mine-big", "Bronze Guardian", 11, 5),
        _perm("mine-big-2", "Bronze Guardian", 11, 5),
        _perm("mine-big-3", "Bronze Guardian", 11, 5),
        _perm("mine-token", "Wizard Token", 0, 1),
        _perm("mine-rock", "Sol Ring", 0, 0),
    )


def _two_sides() -> dict[str, Any]:
    state = _state(step="precombat_main")
    _strong_actor(state)
    _give(state, 1, _perm("their-bird", "Birds of Paradise", 0, 1))
    return state


_BOTH = [_permanent("mine-token", "Wizard Token"), _permanent("their-bird", "Birds of Paradise")]


# --- the side of the target -------------------------------------------------------------


def test_a_destroy_goes_to_an_opponent_even_when_its_creature_is_small() -> None:
    assert _choose(_target_request("destroypermanent", _BOTH, _two_sides())) == ["their-bird"]


def test_a_boost_goes_to_the_actors_own_creature() -> None:
    state = _two_sides()
    state["players"][1]["battlefield"][0].update(power=4, toughness=4)
    options = [
        _permanent("mine-big", "Savannah Lions"),
        _permanent("their-bird", "Birds of Paradise"),
    ]
    assert _choose(_target_request("boostcreature", options, state)) == ["mine-big"]


def test_a_boost_goes_to_the_best_own_creature_not_the_worst() -> None:
    state = _two_sides()
    options = [_permanent("mine-token", "Wizard Token"), _permanent("mine-big", "Bronze Guardian")]
    assert _choose(_target_request("boostcreature", options, state)) == ["mine-big"]


def test_the_side_only_ranks_when_the_choice_offers_both() -> None:
    # A cost that taps one of the actor's own creatures carries the engine's `tap` like the
    # effect that taps an opponent's. With only its own to pick from, an optional choice still
    # picks one (Reaver Titan's "tap another untapped creature you control" went unpaid).
    state = _two_sides()
    options = [_permanent("mine-big", "Bronze Guardian"), _permanent("mine-token", "Wizard Token")]
    request = _target_request("tap", options, state, minimum=0)
    assert len(_choose(request)) == 1


def test_an_outcome_without_a_side_keeps_the_old_ranking() -> None:
    # Control: copy, put-into-play and neutral name no side; the value ranking decides as before.
    state = _two_sides()
    state["players"][1]["battlefield"][0].update(power=6, toughness=6)
    options = [
        _permanent("mine-big", "Savannah Lions"),
        _permanent("their-bird", "Birds of Paradise"),
    ]
    assert _choose(_target_request("copy", options, state)) == ["their-bird"]


def test_the_two_labels_with_a_known_wrong_flag_are_overridden() -> None:
    assert target_side("unboostcreature", "Collective Effort") == "own"
    assert target_side("destroypermanent", "Collective Effort") == "opponent"
    assert target_side("destroypermanent", "Terastodon") is None
    assert target_side("drawcard", "Corpse Augur") is None
    assert target_side("drawcard", "Stroke of Genius") == "own"


def test_a_player_whose_graveyard_is_the_point_is_not_a_side() -> None:
    # Control: Corpse Augur draws for the creature cards in the target player's graveyard.
    state = _state(step="precombat_main")
    request = _target_request("drawcard", [_player(0), _player(1)], state, source="Corpse Augur")
    assert len(_choose(request)) == 1


def test_a_graveyard_card_is_not_ranked_by_side() -> None:
    # Control: "return target creature card" from a graveyard is a card to take. A recursion
    # that offers both graveyards is decided by the card, not by whose graveyard it lies in.
    state = _state(step="precombat_main")
    state["players"][0]["graveyard"] = [_perm("mine-dead", "Savannah Lions", 2, 1)]
    state["players"][1]["graveyard"] = [_perm("their-dead", "Birds of Paradise", 0, 1)]
    mine = _option("mine-dead", "target", "Savannah Lions", object_id="mine-dead", zone="graveyard")
    theirs = _option(
        "their-dead", "target", "Birds of Paradise", object_id="their-dead", zone="graveyard"
    )
    alone = _choose(_target_request("returntohand", [mine], state))
    assert alone == ["mine-dead"]
    assert len(_choose(_target_request("returntohand", [mine, theirs], state))) == 1


# --- gifts -----------------------------------------------------------------------------


def _table_of_unequal_boards() -> dict[str, Any]:
    state = _state(step="precombat_main")
    _give(state, 1, _perm("a1", "Savannah Lions", 2, 1), _perm("a2", "Sol Ring", 0, 0))
    _give(state, 2, _perm("b1", "Birds of Paradise", 0, 1))
    _give(
        state,
        3,
        _perm("c1", "Savannah Lions", 2, 1),
        _perm("c2", "Savannah Lions", 2, 1),
        _perm("c3", "Sol Ring", 0, 0),
        _perm("c4", "Savannah Lions", 2, 1),
    )
    return state


def test_a_gift_goes_to_the_weakest_opponent() -> None:
    # Humble Defector ("target opponent gains control of this creature"), Ms. Bumbleflower
    # ("target opponent draws a card"): each is tagged `drawcard`, and offers only opponents.
    options = [_player(1), _player(2), _player(3)]
    request = _target_request(
        "drawcard", options, _table_of_unequal_boards(), source="Humble Defector"
    )
    assert _choose(request) == ["u2"]


def test_a_draw_that_may_target_the_actor_goes_to_the_actor() -> None:
    # Control: Stroke of Genius offers every player; the draw is for the pilot.
    options = [_player(0), _player(1), _player(2), _player(3)]
    request = _target_request(
        "drawcard", options, _table_of_unequal_boards(), source="Stroke of Genius"
    )
    assert _choose(request) == ["u0"]


# --- the life clock --------------------------------------------------------------------


def test_the_clock_is_zero_above_twenty_and_grows_faster_the_lower_it_falls() -> None:
    assert life_clock(40.0) == 0.0
    assert life_clock(20.0) == 0.0
    assert life_clock(15.0) < life_clock(10.0) < life_clock(5.0) < life_clock(1.0)
    # Quadratic, not linear: the second ten points of life lost are worth three times the first.
    assert life_clock(0.0) - life_clock(10.0) > 3 * (life_clock(10.0) - life_clock(20.0)) * 0.9


def _life_table(*lives: int) -> dict[str, Any]:
    state = _table_of_unequal_boards()
    for seat, life in enumerate(lives, start=1):
        state["players"][seat]["life"] = life
    return state


def test_damage_goes_to_the_player_close_to_dead() -> None:
    # Seat 3 holds the strongest board, so the threat ranking alone aims at it; the player at
    # three life on the weakest board is the one to finish.
    options = [_player(1), _player(2), _player(3)]
    request = _target_request("damage", options, _life_table(40, 3, 40), source="Abraded Bluffs")
    assert _choose(request) == ["u2"]


def test_the_clock_does_not_start_while_every_player_is_healthy() -> None:
    # Control: 25 life is not close to anything; the strongest board stays the target.
    options = [_player(1), _player(2), _player(3)]
    request = _target_request("damage", options, _life_table(40, 25, 40), source="Abraded Bluffs")
    assert _choose(request) == ["u3"]


def test_an_attack_target_goes_to_the_player_at_one_life() -> None:
    options = [_player(2), _player(3)]
    request = _target_request("damage", options, _life_table(40, 1, 27), source="")
    assert _choose(request) == ["u2"]


def test_only_damage_and_life_loss_read_the_clock() -> None:
    # Control: exiling a graveyard does not care how much life the player has left.
    options = [_player(1), _player(2), _player(3)]
    low = _target_request("exile", options, _life_table(40, 3, 40), source="Bojuka Bog")
    high = _target_request("exile", options, _life_table(40, 40, 40), source="Bojuka Bog")
    assert _choose(low) == _choose(high)


def test_a_damage_effect_never_aims_at_the_actor_while_an_opponent_is_offered() -> None:
    # Inalla's "target player loses 7 life" and Goblin Bombardment's "any target" were aimed at
    # the pilot itself, whose own threat score was the highest at the table.
    state = _life_table(40, 40, 40)
    _strong_actor(state)
    options = [_player(0), _player(1)]
    assert _choose(_target_request("damage", options, state, source="Inalla")) == ["u1"]


# --- the commander clock ---------------------------------------------------------------


def _commander_table(taken: int) -> dict[str, Any]:
    state = _state(step="precombat_main")
    _give(state, 1, _perm("their-commander", "Test Commander", 1, 1))
    # A bigger board of another opponent: the value ranking prefers it until the clock runs.
    _give(
        state,
        2,
        _perm("their-big", "Bronze Guardian", 11, 5),
        _perm("their-lions", "Savannah Lions", 2, 1),
        _perm("their-lions-2", "Savannah Lions", 2, 1),
        _perm("their-sol", "Sol Ring", 0, 0),
    )
    state["commander_status"] = [
        {
            "owner_id": "opponent-1",
            "name": "Test Commander",
            "casts_from_command": 0,
            "commander_damage_to_player": (
                [{"player_id": ACTOR, "total": taken}, {"player_id": "opponent-2", "total": 9}]
                if taken
                else []
            ),
        },
        {
            "owner_id": ACTOR,
            "name": "Isamaru, Hound of Konda",
            "casts_from_command": 0,
            "commander_damage_to_player": [{"player_id": "opponent-1", "total": 6}],
        },
    ]
    return state


_COMMANDER_OPTIONS = [
    _permanent("their-commander", "Test Commander"),
    _permanent("their-big", "Bronze Guardian"),
]


def test_a_commander_one_hit_from_killing_the_actor_is_answered_first() -> None:
    # 20 taken and 1 power on the board: the next connect makes 21.
    request = _target_request("destroypermanent", _COMMANDER_OPTIONS, _commander_table(20))
    assert _choose(request) == ["their-commander"]


def test_a_commander_that_has_dealt_nothing_is_ranked_by_value() -> None:
    # Control: the same board with no commander damage taken.
    request = _target_request("destroypermanent", _COMMANDER_OPTIONS, _commander_table(0))
    assert _choose(request) == ["their-big"]


def test_the_commander_clock_is_not_spent_on_a_ping() -> None:
    # One damage does not remove a commander whatever it has done; the outcome decides.
    request = _target_request("damage", _COMMANDER_OPTIONS, _commander_table(20))
    assert _choose(request) == ["their-big"]


def test_commander_damage_is_read_per_commander_and_per_player() -> None:
    state = _commander_table(15)
    assert commander_damage_taken(state, ACTOR, "opponent-1") == 15.0
    assert commander_damage_taken(state, ACTOR, "opponent-2") == 0.0
    assert commander_damage_dealt(state, ACTOR, "opponent-1") == {"Isamaru, Hound of Konda": 6.0}
    assert commander_damage_dealt(state, ACTOR, "opponent-3") == {}


def test_the_clock_jumps_when_one_more_hit_is_lethal() -> None:
    state = _commander_table(15)
    commander = _perm("their-commander", "Test Commander", 1, 1)
    slow = commander_clock_bonus(commander, "opponent-1", state, ACTOR, "destroypermanent")
    fast = commander_clock_bonus(
        {**commander, "power": 9}, "opponent-1", state, ACTOR, "destroypermanent"
    )
    assert 0.0 < slow < 6.0
    assert fast >= slow + 8.0
    assert commander_clock_bonus(commander, "opponent-1", state, ACTOR, "damage") == 0.0
    # The actor's own commander and a creature that is no commander carry no clock.
    assert commander_clock_bonus(commander, ACTOR, state, ACTOR, "destroypermanent") == 0.0
    sol = _perm("their-sol", "Sol Ring", 0, 0)
    assert commander_clock_bonus(sol, "opponent-1", state, ACTOR, "destroypermanent") == 0.0


def test_the_pilot_view_carries_the_actors_commander_damage() -> None:
    # The structural simulator filled `commander_damage_from_actor`; the full game never did.
    policy = _policy()
    view = policy._pilot_state(policy._pilots[1], _commander_table(15))
    dealt = {
        opponent.player_id: opponent.commander_damage_from_actor for opponent in view.opponents
    }
    assert dealt["opponent-1"] == {"Isamaru, Hound of Konda": 6.0}
    assert dealt["opponent-2"] == {}
