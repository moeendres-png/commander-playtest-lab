"""Which land the full-game pilot plays and which it fetches (#989 phase 6).

Recorded real pod games showed every land scoring alike, so the land that sorted last by name was
played and a "search for a basic land" took Swamp or Plains whatever the hand needed (203 searches
in 24 games: Swamp 79, Plains 64, Island and Forest never). These tests pin the ranking from the
actor's hand, board and commander colours, and that a tie is broken by the seeded rng and not by
a name.
"""

from __future__ import annotations

import random
from typing import Any

from commander_lab.agents import GenericCommanderPilot
from commander_lab.agents.card_knowledge import card_facts
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.engine.rules.full_game_pilot_lands import (
    choose_land_to_play,
    choose_lands_to_fetch,
    commander_identity,
    enters_tapped,
)
from commander_lab.models import PilotConfig, PilotStrength

_PASS = {"option_id": "pass", "label": "Pass priority", "option_type": "pass_priority"}


def _land(object_id: str, name: str, *, tapped: bool = False) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "name": name,
        "tapped": tapped,
        "power": 0,
        "toughness": 0,
        "damage": 0,
    }


def _state(
    *,
    board: list[str],
    hand: list[str],
    commander: str,
    command_zone: bool = True,
    tapped: bool = False,
    life: int = 40,
) -> dict[str, Any]:
    actor = {
        "player_id": "actor",
        "is_actor": True,
        "seat": 0,
        "life": life,
        "hand_count": len(hand),
        "library_count": 80,
        "graveyard_count": 0,
        "battlefield": [
            _land(f"b{index}", name, tapped=tapped) for index, name in enumerate(board)
        ],
        "graveyard": [],
        "command": [{"object_id": "cmd", "name": commander}] if command_zone else [],
        "hand": [{"object_id": f"h{index}", "name": name} for index, name in enumerate(hand)],
        "mana_pool": {},
    }
    opponent = {
        "player_id": "opponent-1",
        "seat": 1,
        "life": 40,
        "hand_count": 7,
        "library_count": 90,
        "graveyard_count": 0,
        "battlefield": [],
        "graveyard": [],
        "command": [],
    }
    return {
        "game_id": "engine-opaque",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 5,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "precombat_main",
        "step": "precombat_main",
        "players": [actor, opponent],
        "stack": [],
        "commander_status": [{"owner_id": "actor", "name": commander, "casts_from_command": 0}],
    }


def _rng(seed: int = 7) -> random.Random:
    return random.Random(seed)


def test_the_commander_names_the_colours_a_land_may_serve() -> None:
    state = _state(board=[], hand=[], commander="Ishai, Ojutai Dragonspeaker")
    assert commander_identity(state) == frozenset({"W", "U"})


def test_the_land_that_lets_a_spell_be_cast_is_played() -> None:
    # Two Islands and a Plains, a WW creature in hand: only the second Plains casts it. Swamp sorts
    # last by name and was the old pick.
    state = _state(
        board=["Island", "Island", "Plains"],
        hand=["White Orchid Phantom", "Swamp", "Island", "Plains"],
        commander="Ishai, Ojutai Dragonspeaker",
    )
    picks = {
        choose_land_to_play(["Swamp", "Island", "Plains"], state, _rng(seed)) for seed in range(12)
    }
    assert picks == {"Plains"}


def test_the_second_blue_source_comes_before_a_land_the_commander_cannot_use() -> None:
    state = _state(
        board=["Island", "Plains", "Plains"],
        hand=["Counterspell", "Swamp", "Island"],
        commander="Ishai, Ojutai Dragonspeaker",
    )
    picks = {choose_land_to_play(["Swamp", "Island"], state, _rng(seed)) for seed in range(12)}
    assert picks == {"Island"}


def test_a_land_that_enters_tapped_is_played_when_no_untapped_land_casts_anything_extra() -> None:
    # Everything in hand is out of reach this turn, so the tapped scry land costs nothing.
    state = _state(
        board=["Mountain", "Plains", "Mountain"],
        hand=["Temple of Triumph", "Plains"],
        commander="Quintorius, Loremaster",
    )
    picks = {
        choose_land_to_play(["Temple of Triumph", "Plains"], state, _rng(seed))
        for seed in range(12)
    }
    assert picks == {"Temple of Triumph"}


def test_an_untapped_land_wins_over_a_tapped_one_when_it_casts_a_spell() -> None:
    state = _state(
        board=["Mountain", "Plains"],
        hand=["Lightning Bolt", "Temple of Triumph", "Mountain"],
        commander="Quintorius, Loremaster",
    )
    # The Mountain would add a second red source to nothing new; the Bolt is castable already, so
    # nothing enables more, and the tapped Temple costs nothing: it goes first.
    picks = {
        choose_land_to_play(["Temple of Triumph", "Mountain"], state, _rng(seed))
        for seed in range(12)
    }
    assert picks == {"Temple of Triumph"}
    wrath = _state(
        board=["Plains", "Plains", "Mountain"],
        hand=["Wrath of God", "Temple of Triumph", "Plains"],
        commander="Quintorius, Loremaster",
    )
    # Four mana for Wrath of God: only the untapped Plains gets there this turn.
    picks = {
        choose_land_to_play(["Temple of Triumph", "Plains"], wrath, _rng(seed))
        for seed in range(12)
    }
    assert picks == {"Plains"}


def test_a_missing_colour_decides_when_nothing_can_be_cast_either_way() -> None:
    state = _state(
        board=["Plains", "Plains"],
        hand=["Negate", "Island", "Plains"],
        commander="Ishai, Ojutai Dragonspeaker",
        tapped=True,
    )
    picks = {choose_land_to_play(["Island", "Plains"], state, _rng(seed)) for seed in range(12)}
    assert picks == {"Island"}


def test_equal_lands_are_told_apart_by_the_rng_not_by_their_names() -> None:
    state = _state(board=[], hand=["Plains", "Island"], commander="Ishai, Ojutai Dragonspeaker")
    picks = {choose_land_to_play(["Plains", "Island"], state, _rng(seed)) for seed in range(40)}
    assert picks == {"Plains", "Island"}


def test_a_search_takes_the_colour_the_hand_needs() -> None:
    state = _state(
        board=["Plains", "Plains"],
        hand=["Negate"],
        commander="Ishai, Ojutai Dragonspeaker",
    )
    names = ["Swamp", "Plains", "Island", "Mountain", "Forest"]
    picks = {choose_lands_to_fetch(names, state, _rng(seed))[0] for seed in range(12)}
    assert picks == {"Island"}


def test_a_search_for_two_lands_takes_two_colours_and_none_outside_the_commander() -> None:
    state = _state(board=["Plains"], hand=["Negate"], commander="Ishai, Ojutai Dragonspeaker")
    names = ["Swamp", "Plains", "Island", "Mountain", "Forest"]
    order = choose_lands_to_fetch(names, state, _rng(), count=2)
    assert order[:2] == ["Island", "Plains"]
    assert sorted(order) == sorted(names)


def test_a_search_is_not_biased_toward_the_colours_that_sort_last() -> None:
    state = _state(board=[], hand=[], commander="Sauron, Lord of the Rings")
    names = ["Swamp", "Plains", "Island", "Mountain", "Forest"]
    first = [choose_lands_to_fetch(names, state, _rng(seed))[0] for seed in range(60)]
    assert set(first) == {"Swamp", "Island", "Mountain"}


def test_enters_tapped_reads_a_check_land_from_the_board() -> None:
    sulfur = card_facts("Sulfur Falls")
    summit = card_facts("Dragonskull Summit")
    assert sulfur is not None and summit is not None
    with_island = _state(board=["Island", "Plains"], hand=[], commander="Esior, Wardwing Familiar")
    with_plains = _state(board=["Plains", "Plains"], hand=[], commander="Esior, Wardwing Familiar")
    assert enters_tapped(sulfur, with_island) is False
    assert enters_tapped(sulfur, with_plains) is True
    with_swamp = _state(board=["Swamp"], hand=[], commander="Kaervek the Merciless")
    assert enters_tapped(summit, with_swamp) is False
    assert enters_tapped(summit, with_plains) is True


def test_enters_tapped_reads_a_reveal_land_from_the_hand() -> None:
    snarl = card_facts("Frostboil Snarl")
    assert snarl is not None
    revealing = _state(board=["Plains"], hand=["Mountain"], commander="Esior, Wardwing Familiar")
    bare = _state(board=["Plains"], hand=["Plains"], commander="Esior, Wardwing Familiar")
    assert enters_tapped(snarl, revealing) is False
    assert enters_tapped(snarl, bare) is True


def test_enters_tapped_counts_basic_lands_for_a_slow_land() -> None:
    marsh = card_facts("Smoldering Marsh")
    assert marsh is not None
    two_basics = _state(
        board=["Mountain", "Swamp", "Command Tower"], hand=[], commander="Kaervek the Merciless"
    )
    one_basic = _state(
        board=["Mountain", "Command Tower"], hand=[], commander="Kaervek the Merciless"
    )
    assert enters_tapped(marsh, two_basics) is False
    assert enters_tapped(marsh, one_basic) is True


def test_enters_tapped_for_a_land_that_always_does() -> None:
    temple = card_facts("Temple of Triumph")
    field = card_facts("Lotus Field")
    assert temple is not None and field is not None
    state = _state(board=["Mountain"], hand=[], commander="Quintorius, Loremaster")
    assert enters_tapped(temple, state) is True
    assert enters_tapped(field, state) is True


def _policy() -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in range(1, 5):
        config = PilotConfig(pilot_name="auto", strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC)
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"fixture-{seat}",
            strategy="generic",
            commander_names=("Ishai, Ojutai Dragonspeaker",),
            config=config,
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(_RuntimePilot(binding=binding, pilot=GenericCommanderPilot(config)))
    return ExternalPilotDecisionPolicy(tuple(runtimes), 20261025)  # type: ignore[arg-type]


def _play_land(name: str) -> dict[str, Any]:
    return {
        "option_id": f"play-{name}",
        "label": f"{name} — Play {name}",
        "option_type": "activated_ability",
        "metadata": {
            "source_name": name,
            "source_object_id": f"hand-{name}",
            "ability_type": "play_land",
        },
    }


def _request(
    decision_class: str,
    options: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    prompt: str = "",
    context: dict[str, Any] | None = None,
    minimum: int = 1,
    maximum: int = 1,
) -> dict[str, Any]:
    return {
        "decision_id": f"opaque-{decision_class}",
        "decision_offset": 1,
        "actor_id": "actor",
        "decision_class": decision_class,
        "pilot_state": state,
        "context": context or {},
        "minimum_selections": minimum,
        "maximum_selections": maximum,
        "legal_options": options,
        "prompt": prompt or decision_class,
    }


def test_the_pilot_plays_the_land_the_hand_needs() -> None:
    state = _state(
        board=["Island", "Island", "Plains"],
        hand=["White Orchid Phantom", "Swamp", "Island", "Plains"],
        commander="Ishai, Ojutai Dragonspeaker",
    )
    options = [_PASS, _play_land("Swamp"), _play_land("Island"), _play_land("Plains")]
    response = _policy().decide(_request("priority", options, state))
    assert response["selected_option_ids"] == ["play-Plains"]


def _library_lands(names: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "option_id": f"lib-{name}",
            "label": name,
            "option_type": "target",
            "metadata": {
                "name": name,
                "object_id": f"lib-{name}",
                "zone": "library",
                "zone_index": i,
            },
        }
        for i, name in enumerate(names)
    ]


def test_the_pilot_fetches_the_missing_colour() -> None:
    state = _state(
        board=["Plains", "Plains"], hand=["Negate"], commander="Ishai, Ojutai Dragonspeaker"
    )
    request = _request(
        "target",
        _library_lands(["Swamp", "Plains", "Island"]),
        state,
        prompt="Select a basic land card",
        context={
            "outcome": "neutral",
            "required": False,
            "target_description": "a basic land card",
            "target_name": "basic land card",
            "targeted": True,
        },
    )
    response = _policy().decide(request)
    assert response["selected_option_ids"] == ["lib-Island"]


def test_a_library_search_for_other_cards_is_left_to_the_pilot() -> None:
    state = _state(board=["Plains"], hand=[], commander="Ishai, Ojutai Dragonspeaker")
    options = _library_lands(["Balefire Liege", "Island"])
    request = _request(
        "target",
        options,
        state,
        prompt="Select a card",
        context={"outcome": "benefit", "required": False, "targeted": True},
    )
    response = _policy().decide(request)
    assert len(response["selected_option_ids"]) == 1
