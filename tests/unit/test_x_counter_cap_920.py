"""Full-game pilot: an X paid by removing counters from its source (#920).

Pod 042 of the precon sweep aborts on Marath, Will of the Wild: ``{X}, Remove X
+1/+1 counters from Marath``. The engine bounds the mana X by nothing, the
benefit-biased pilot announces what its mana allows, the mana is paid, and the
custom counter cost cannot remove that many counters, so the activation is
reversed and the game stops.

The counters are board-public and the cost is printed on the option the pilot
chose, so the pilot keeps its announced X within what the source has. The
engine's own domain is never narrowed here; the cap is a strategy hint like the
mana budget it joins.
"""

from __future__ import annotations

from typing import Any

from commander_lab.engine.rules.full_game_pilot.common import option_x_counter_cap
from tests.unit.test_ws700_affordable_x import (
    INT_MAX,
    ZERO_COST_FACTS,
    _announce_x_request,
    _announced,
    _policy,
    _priority_request,
    _state,
)

MARATH_ID = "obj-marath"
MARATH_NAME = "Marath, Will of the Wild"
MARATH_LABEL = (
    "Marath, Will of the Wild — {X}, Remove X +1/+1 counters from Marath: Choose one "
    "&mdash;<br>&bull Put X +1/+1 counters on target creature.<br>"
)
MARATH_METADATA = {"source_object_id": MARATH_ID, "source_name": MARATH_NAME}


def _battlefield(counters: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    item: dict[str, Any] = {
        "object_id": MARATH_ID,
        "name": MARATH_NAME,
        "tapped": False,
        "face_down": False,
        "abilities": [],
    }
    if counters is not None:
        item["counters"] = counters
    return [item]


def _marath_state(counters: list[dict[str, Any]] | None, *, lands: int = 8) -> dict[str, Any]:
    state = _state(untapped_lands=lands)
    actor = next(player for player in state["players"] if player["player_id"] == "actor")
    actor["battlefield"] = [*actor["battlefield"], *_battlefield(counters)]
    return state


P1P1 = "+1/+1"


# --- the pure reading ---------------------------------------------------------


def test_cap_is_the_sources_counters_of_the_printed_kind() -> None:
    battlefield = _battlefield([{"type": P1P1, "count": 3}, {"type": "charge", "count": 5}])
    assert option_x_counter_cap(MARATH_LABEL, MARATH_METADATA, battlefield) == 3


def test_source_without_that_counter_has_a_cap_of_zero() -> None:
    battlefield = _battlefield([{"type": "charge", "count": 5}])
    assert option_x_counter_cap(MARATH_LABEL, MARATH_METADATA, battlefield) == 0


def test_this_placeholder_names_the_source() -> None:
    label = "{X}, Remove X +1/+1 counters from {this}: Draw a card."
    battlefield = _battlefield([{"type": P1P1, "count": 2}])
    assert option_x_counter_cap(label, MARATH_METADATA, battlefield) == 2


def test_other_costs_and_other_sources_read_as_no_cap() -> None:
    battlefield = _battlefield([{"type": P1P1, "count": 3}])
    # A fixed number of counters is not an X.
    assert (
        option_x_counter_cap("Remove a +1/+1 counter from Marath: Draw.", {}, battlefield) is None
    )
    # Counters removed from another permanent are not this source's counters.
    elsewhere = "{X}, Remove X +1/+1 counters from target creature: Draw."
    assert option_x_counter_cap(elsewhere, MARATH_METADATA, battlefield) is None
    # A printed name that is not this ability's own permanent.
    other = "{X}, Remove X +1/+1 counters from Another Creature: Draw."
    assert option_x_counter_cap(other, MARATH_METADATA, battlefield) is None
    # No text, no metadata, no battlefield view: unknown is never a number.
    assert option_x_counter_cap("", MARATH_METADATA, battlefield) is None
    assert option_x_counter_cap(MARATH_LABEL, {}, battlefield) is None
    assert option_x_counter_cap(MARATH_LABEL, MARATH_METADATA, None) is None
    assert option_x_counter_cap(MARATH_LABEL, MARATH_METADATA, []) is None


def test_unreadable_counter_entries_are_never_a_number() -> None:
    for counters in (
        None,
        [{"type": P1P1, "count": True}],
        [{"type": P1P1, "count": -1}],
        [{"type": P1P1, "count": "3"}],
    ):
        assert (
            option_x_counter_cap(MARATH_LABEL, MARATH_METADATA, _battlefield(counters)) is None
        ), counters


# --- the announce -------------------------------------------------------------


def _marath_x(counters: list[dict[str, Any]] | None, *, lands: int = 8) -> int:
    """Seat 2 chooses Marath's ability, then announces its X."""
    state = _marath_state(counters, lands=lands)
    policy = _policy()
    chosen = policy.decide(
        _priority_request(
            source_id=MARATH_ID,
            source_name=MARATH_NAME,
            mana_cost=ZERO_COST_FACTS,
            label=MARATH_LABEL,
            state=state,
        )
    )
    assert chosen["selected_option_ids"] != ["priority-pass"], "the ability must be selected"
    return _announced(
        policy,
        _announce_x_request(
            context={"numeric_min": 1, "numeric_max": INT_MAX, "outcome": "benefit"},
            source_object={"source_object_id": MARATH_ID, "source_name": MARATH_NAME},
            state=state,
        ),
    )


def test_announced_x_stays_within_the_sources_counters() -> None:
    # Fails without the cap: 8 untapped Swamps allow X = 8, Marath has 3 counters.
    assert _marath_x([{"type": P1P1, "count": 3}], lands=8) == 3


def test_mana_budget_still_binds_when_it_is_the_smaller() -> None:
    assert _marath_x([{"type": P1P1, "count": 6}], lands=2) == 2


def test_no_visible_counters_leaves_the_mana_budget_alone() -> None:
    # The pilot cannot see the counters (unreadable): it does not invent a cap.
    assert _marath_x(None, lands=4) == 4


def test_the_cap_never_falls_below_the_authoritative_minimum() -> None:
    # Marath is only offered with a counter on it, but a missing counter must
    # still not push the announcement below the engine's own minimum of 1.
    assert _marath_x([{"type": P1P1, "count": 0}], lands=4) == 1


def test_the_cap_is_consumed_by_the_announce_it_was_kept_for() -> None:
    state = _marath_state([{"type": P1P1, "count": 3}])
    policy = _policy()
    policy.decide(
        _priority_request(
            source_id=MARATH_ID,
            source_name=MARATH_NAME,
            mana_cost=ZERO_COST_FACTS,
            label=MARATH_LABEL,
            state=state,
        )
    )
    request = _announce_x_request(
        context={"numeric_min": 1, "numeric_max": INT_MAX, "outcome": "benefit"},
        source_object={"source_object_id": MARATH_ID},
        state=state,
    )
    assert _announced(policy, request) == 3
    # Taken, not copied: nothing is left to bound a later announcement.
    assert not any(policy._priority_x_counter_caps.values())


def test_the_next_priority_decision_drops_the_cap() -> None:
    state = _marath_state([{"type": P1P1, "count": 3}])
    policy = _policy()
    policy.decide(
        _priority_request(
            source_id=MARATH_ID,
            source_name=MARATH_NAME,
            mana_cost=ZERO_COST_FACTS,
            label=MARATH_LABEL,
            state=state,
        )
    )
    # A different action is chosen next: the old cap must not follow it.
    policy.decide(
        _priority_request(
            source_id="obj-other",
            source_name="Other",
            mana_cost=ZERO_COST_FACTS,
            label="{X}: Other effect.",
            state=state,
            offset=2,
        )
    )
    request = _announce_x_request(
        context={"numeric_min": 1, "numeric_max": INT_MAX, "outcome": "benefit"},
        source_object={"source_object_id": MARATH_ID},
        state=state,
        offset=3,
    )
    assert _announced(policy, request) > 3
