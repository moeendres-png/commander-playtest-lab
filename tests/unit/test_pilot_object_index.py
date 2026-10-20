"""The pilot's per-state object index must never serve another state's objects."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from commander_lab.engine.rules.full_game_pilot import state as pilot_state


def _policy() -> pilot_state._PolicyState:
    pilots = tuple(SimpleNamespace(binding=SimpleNamespace(seat=seat)) for seat in (1, 2))
    return pilot_state._PolicyState(pilots, scenario_seed=1)  # type: ignore[arg-type]


def _state(value: int) -> dict[str, object]:
    return {"players": [{"player_id": "p1", "battlefield": [{"object_id": "o1", "value": value}]}]}


def test_find_object_reads_the_current_state() -> None:
    policy = _policy()
    first, second = _state(1), _state(2)
    assert policy._find_object("o1", first) == {"object_id": "o1", "value": 1}
    assert policy._find_object("o1", second) == {"object_id": "o1", "value": 2}
    assert policy._find_object("o1", first) == {"object_id": "o1", "value": 1}


def test_find_object_survives_an_address_reused_by_a_new_state() -> None:
    # id() is unique only among live objects, so a freed state's address can come
    # back for the next state. Simulate that by making every id() equal; an index
    # keyed on the id would then serve the previous state's objects.
    policy = _policy()
    with patch.object(pilot_state, "id", lambda _obj: 1, create=True):
        assert policy._find_object("o1", _state(1)) == {"object_id": "o1", "value": 1}
        assert policy._find_object("o1", _state(2)) == {"object_id": "o1", "value": 2}
