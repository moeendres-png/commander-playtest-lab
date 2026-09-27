from pathlib import Path

from commander_lab.optimization import DEFAULT_CONSTRAINTS
from commander_lab.tools.candidates import load_current_optimization_availability

ROOT = Path(__file__).resolve().parents[2]


def test_rogshai_is_not_simultaneously_constrained_by_korvold() -> None:
    assert DEFAULT_CONSTRAINTS["rogshai/current"].simultaneous_deck_ids == ()


def test_released_korvold_card_is_available_to_rogshai_pool() -> None:
    availability = load_current_optimization_availability(ROOT)
    assert availability["Lightning Greaves"] >= 1
    assert availability["Idol of Oblivion"] >= 1
