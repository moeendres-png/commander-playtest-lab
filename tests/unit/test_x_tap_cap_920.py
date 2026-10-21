"""Full-game pilot: an X paid by tapping X untapped permanents (#920).

Plan seed 1, game seed 101, pod 024 of the precon sweep aborts on Necron Overlord:
``{X}, {T}, Tap X untapped artifacts you control``. The engine bounds the mana X by nothing,
the benefit-biased pilot announces what its 13 Swamps allow, the mana is paid, and the tap
cost finds a handful of artifacts, so the activation is reversed and the game stops.

The untapped permanents are board-public and the cost is printed on the option the pilot
chose, so the pilot keeps its announced X within what is there. The engine's own domain is
never narrowed here; the cap is a strategy hint like the mana budget it joins.
"""

from __future__ import annotations

from typing import Any

from commander_lab.engine.rules.full_game_pilot.common import option_x_tap_cap
from tests.unit.test_ws700_affordable_x import (
    INT_MAX,
    ZERO_COST_FACTS,
    _announce_x_request,
    _announced,
    _policy,
    _priority_request,
    _state,
)

OVERLORD_ID = "obj-overlord"
OVERLORD_NAME = "Necron Overlord"
OVERLORD_LABEL = (
    "<i>Relentless March</i> &mdash; {X}, {T}, Tap X untapped artifacts you control: "
    "Target opponent loses X life."
)
OVERLORD_METADATA = {"source_object_id": OVERLORD_ID, "source_name": OVERLORD_NAME}


def _item(
    name: str, object_id: str, *, tapped: bool = False, face_down: bool = False
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "name": name,
        "tapped": tapped,
        "face_down": face_down,
        "abilities": [],
        "counters": [],
    }


def _artifacts(count: int) -> list[dict[str, Any]]:
    # Skullclamp is in the printed card catalog as an artifact and offers no mana.
    return [_item("Skullclamp", f"obj-clamp-{index}") for index in range(count)]


def _overlord_state(artifacts: int, *, lands: int = 8) -> dict[str, Any]:
    state = _state(untapped_lands=lands)
    actor = next(player for player in state["players"] if player["player_id"] == "actor")
    actor["battlefield"] = [
        *actor["battlefield"],
        _item(OVERLORD_NAME, OVERLORD_ID),
        *_artifacts(artifacts),
    ]
    return state


# --- the pure reading ---------------------------------------------------------


def test_cap_counts_the_untapped_artifacts_but_not_the_source() -> None:
    battlefield = [
        _item(OVERLORD_NAME, OVERLORD_ID),
        *_artifacts(3),
        _item("Sol Ring", "obj-ring", tapped=True),
        _item("Skullclamp", "obj-down", face_down=True),
        _item("Swamp", "obj-swamp"),
    ]
    # Tapped, face-down and non-artifact permanents do not count, and the Overlord is tapped
    # by its own {T} before the artifacts are chosen.
    assert option_x_tap_cap(OVERLORD_LABEL, OVERLORD_METADATA, battlefield) == 3


def test_a_source_that_is_not_tapped_by_the_same_cost_counts() -> None:
    label = "{X}, Tap X untapped artifacts you control: Draw X cards."
    battlefield = [_item("Skullclamp", "obj-clamp-0"), _item("Sol Ring", "obj-ring")]
    metadata = {"source_object_id": "obj-clamp-0", "source_name": "Skullclamp"}
    assert option_x_tap_cap(label, metadata, battlefield) == 2


def test_the_printed_kind_selects_what_counts() -> None:
    label = "{X}, Tap X untapped creatures you control: Draw X cards."
    battlefield = [
        _item("Grizzly Bears", "obj-bears"),
        _item("Skullclamp", "obj-clamp-0"),
    ]
    assert option_x_tap_cap(label, {"source_object_id": "obj-other"}, battlefield) == 1


def test_a_card_missing_from_the_catalog_is_never_counted() -> None:
    # Only ever lowers the cap: an unknown permanent is not an artifact the pilot may rely on.
    battlefield = [_item("Treasure Token", "obj-treasure"), _item("Unknown Rock", "obj-rock")]
    assert option_x_tap_cap(OVERLORD_LABEL, OVERLORD_METADATA, battlefield) == 0


def test_other_costs_read_as_no_cap() -> None:
    battlefield = _artifacts(3)
    assert option_x_tap_cap("{X}, {T}: Add X mana.", OVERLORD_METADATA, battlefield) is None
    # A fixed number of permanents is not an X.
    assert option_x_tap_cap("Tap an untapped artifact you control: Draw.", {}, battlefield) is None
    assert option_x_tap_cap("", OVERLORD_METADATA, battlefield) is None
    assert option_x_tap_cap(OVERLORD_LABEL, OVERLORD_METADATA, None) is None


# --- the announce -------------------------------------------------------------


def _overlord_x(artifacts: int, *, lands: int = 8) -> int:
    """Seat 2 chooses the Overlord's ability, then announces its X."""
    state = _overlord_state(artifacts, lands=lands)
    policy = _policy()
    chosen = policy.decide(
        _priority_request(
            source_id=OVERLORD_ID,
            source_name=OVERLORD_NAME,
            mana_cost=ZERO_COST_FACTS,
            label=OVERLORD_LABEL,
            state=state,
        )
    )
    assert chosen["selected_option_ids"] != ["priority-pass"], "the ability must be selected"
    return _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 1, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": OVERLORD_ID, "source_name": OVERLORD_NAME},
            state=state,
        ),
    )


def test_announced_x_stays_within_the_untapped_artifacts() -> None:
    # Fails without the cap: 8 untapped Swamps allow X = 8, only 3 artifacts can be tapped.
    assert _overlord_x(3, lands=8) == 3


def test_mana_budget_still_binds_when_it_is_the_smaller() -> None:
    assert _overlord_x(6, lands=2) == 2


def test_the_cap_never_falls_below_the_authoritative_minimum() -> None:
    # With no artifact to tap the announcement still respects the engine's own minimum of 1.
    assert _overlord_x(0, lands=4) == 1


def test_the_cap_is_consumed_by_the_announce_it_was_kept_for() -> None:
    state = _overlord_state(3)
    policy = _policy()
    policy.decide(
        _priority_request(
            source_id=OVERLORD_ID,
            source_name=OVERLORD_NAME,
            mana_cost=ZERO_COST_FACTS,
            label=OVERLORD_LABEL,
            state=state,
        )
    )
    request = _announce_x_request(
        context={"numeric_min": 1, "numeric_max": INT_MAX, "outcome": "benefit"},
        source_object={"source_object_id": OVERLORD_ID},
        state=state,
    )
    assert _announced(policy, request) == 3
    # Taken, not copied: nothing is left to bound a later announcement.
    assert not any(policy._priority_x_counter_caps.values())
