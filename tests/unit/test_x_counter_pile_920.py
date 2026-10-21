"""Full-game pilot: an X paid by removing X counters from one permanent (#920).

Plan seed 6, game seed 106, pod 040 of the precon sweep aborts on Moxite Refinery:
``{2}, {T}, Remove X counters from an artifact or creature you control``. The engine bounds
neither X nor the pick: the seat names X, picks one permanent and one counter type, and the
activation is reversed when that pile holds fewer counters than X, which stops the game.

The counters are board-public and the cost is printed on the option the pilot chose, so the
pilot keeps its announced X within the largest pile of a permanent of the printed types and
then pays from that pile.
"""

from __future__ import annotations

from typing import Any

from commander_lab.engine.rules.full_game_pilot_views import (
    is_x_counter_pile_cost,
    x_counter_pile_cap,
)
from tests.unit.test_ws700_affordable_x import (
    ZERO_COST_FACTS,
    _announce_x_request,
    _announced,
    _policy,
    _priority_request,
    _state,
)

REFINERY_ID = "obj-refinery"
REFINERY_NAME = "Moxite Refinery"
REFINERY_LABEL = (
    "{2}, {T}, Remove X counters from an artifact or creature you control: Choose one. "
    "Activate only as a sorcery."
)


def _item(name: str, object_id: str, counters: dict[str, int] | None = None) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "name": name,
        "tapped": False,
        "face_down": False,
        "abilities": [],
        "counters": [{"type": kind, "count": count} for kind, count in (counters or {}).items()],
    }


def _board(foundry: dict[str, int] | None = None) -> list[dict[str, Any]]:
    # Golem Foundry, Darksteel Reactor and Skullclamp are artifacts in the printed catalog,
    # Grizzly Bears a creature, Forest a land.
    return [
        _item(REFINERY_NAME, REFINERY_ID),
        _item("Golem Foundry", "obj-foundry", foundry or {"charge": 5, "+1/+1": 2}),
        _item("Darksteel Reactor", "obj-reactor", {"charge": 3}),
        _item("Grizzly Bears", "obj-bears", {"+1/+1": 4}),
        _item("Forest", "obj-forest", {"charge": 9}),
        _item("Unknown Rock", "obj-rock", {"charge": 7}),
    ]


# --- the pure reading ---------------------------------------------------------


def test_cap_is_the_largest_pile_on_a_permanent_of_the_printed_types() -> None:
    # The Forest (land) and the card missing from the catalog hold more, but cannot pay.
    assert x_counter_pile_cap(REFINERY_LABEL, _board()) == 5


def test_a_permanent_you_control_may_be_any_type() -> None:
    label = "Remove X counters from a permanent you control: Draw X cards."
    assert x_counter_pile_cap(label, _board()) == 9


def test_a_creature_only_cost_ignores_artifacts() -> None:
    label = "Remove X counters from a creature you control: Draw X cards."
    assert x_counter_pile_cap(label, _board()) == 4


def test_no_counters_is_a_cap_of_zero() -> None:
    assert x_counter_pile_cap(REFINERY_LABEL, [_item("Golem Foundry", "obj-foundry")]) == 0


def test_other_costs_read_as_no_cap() -> None:
    battlefield = _board()
    # Marath-style: counters of a named kind from the source itself.
    marath = "{X}, Remove X +1/+1 counters from Marath, Will of the Wild: Choose one."
    assert x_counter_pile_cap(marath, battlefield) is None
    # A fixed number is not an X.
    fixed = "Remove three counters from among artifacts you control: Draw."
    assert x_counter_pile_cap(fixed, battlefield) is None
    assert x_counter_pile_cap("", battlefield) is None
    assert x_counter_pile_cap(REFINERY_LABEL, None) is None
    assert is_x_counter_pile_cost(REFINERY_LABEL)
    assert not is_x_counter_pile_cost(marath)


# --- the announce, the pick and the counter type ------------------------------


def _refinery_state(foundry: dict[str, int] | None = None, *, lands: int = 12) -> dict[str, Any]:
    state = _state(untapped_lands=lands)
    actor = next(player for player in state["players"] if player["player_id"] == "actor")
    actor["battlefield"] = [*actor["battlefield"], *_board(foundry)]
    return state


def _activate_and_announce(
    foundry: dict[str, int] | None = None,
) -> tuple[Any, dict[str, Any], int]:
    """Seat 2 chooses the Refinery's ability, then announces its X (12 lands, {2} cost)."""
    state = _refinery_state(foundry)
    policy = _policy()
    chosen = policy.decide(
        _priority_request(
            source_id=REFINERY_ID,
            source_name=REFINERY_NAME,
            mana_cost={**ZERO_COST_FACTS, "mana_cost_generic": 2},
            label=REFINERY_LABEL,
            state=state,
        )
    )
    assert chosen["selected_option_ids"] != ["priority-pass"], "the ability must be selected"
    announced = _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 0, "numeric_max": 40, "outcome": "benefit"},
            source_object={"source_object_id": REFINERY_ID, "source_name": REFINERY_NAME},
            state=state,
            offset=2,
        ),
    )
    return policy, state, announced


def test_announced_x_stays_within_the_largest_pile() -> None:
    # Ten mana would pay for X = 10; the biggest pile on an artifact or creature is five.
    _, _, announced = _activate_and_announce()
    assert announced == 5


def _object_request(state: dict[str, Any]) -> dict[str, Any]:
    names = {
        item["name"]: item["object_id"]
        for item in _board()
        if item["name"] in {"Golem Foundry", "Darksteel Reactor", "Grizzly Bears"}
    }
    return {
        "decision_id": "opaque-choose-object",
        "decision_offset": 3,
        "actor_id": "actor",
        "decision_class": "choose_object",
        "pilot_state": state,
        "context": {"targeted": False, "outcome": "aidontuseit", "required": True},
        "minimum_selections": 0,
        "maximum_selections": 1,
        "legal_options": [
            {
                "option_id": object_id,
                "option_type": "choice",
                "label": name,
                "metadata": {"object_id": object_id, "name": name, "zone": "battlefield"},
            }
            for name, object_id in names.items()
        ],
        "prompt": "Select up to one artifact or creature you control",
        "source_object": {"source_object_id": REFINERY_ID, "source_name": REFINERY_NAME},
    }


def test_the_permanent_that_pays_is_the_one_with_a_pile_big_enough() -> None:
    # Bears hold the most +1/+1 counters, the Reactor the fewest charge ones; only the Foundry's
    # five charge counters cover X = 5.
    policy, state, announced = _activate_and_announce()
    assert announced == 5
    response = policy.decide(_object_request(state))
    assert response["selected_option_ids"] == ["obj-foundry"]


def test_the_counter_type_is_the_big_pile() -> None:
    # Whatever order the engine lists the types in, and whichever type holds the pile.
    for biggest in ("charge", "+1/+1"):
        other = "+1/+1" if biggest == "charge" else "charge"
        for kinds in ((biggest, other), (other, biggest)):
            policy, state, _ = _activate_and_announce({biggest: 5, other: 2})
            policy.decide(_object_request(state))
            request = {
                "decision_id": "opaque-choice",
                "decision_offset": 4,
                "actor_id": "actor",
                "decision_class": "choice",
                "pilot_state": state,
                "context": {"outcome": "aidontuseit"},
                "minimum_selections": 1,
                "maximum_selections": 1,
                "legal_options": [
                    {
                        "option_id": f"kind-{kind}",
                        "option_type": "choice",
                        "label": kind,
                        "metadata": {},
                    }
                    for kind in kinds
                ],
                "prompt": (
                    "Choose a counter to remove from "
                    "<font color='#B0C4DE' object_id='#'>Golem Foundry</font>"
                ),
            }
            assert policy.decide(request)["selected_option_ids"] == [f"kind-{biggest}"]
