"""Simulation results do not count in the tier list and are for now neither collected nor
processed for it; the ``simulation`` weight stays as an option at 0 in the defaults and in every
preset (Owner decision 2026-11-12, Refs #1205). Nothing else on the tier page is fed by them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, evidence, strength, strength_view
from commander_lab.studio.strength import Observation, StrengthSettings
from tests.unit.test_studio_builder import _fill

COMMANDER = "Test Commander"


def test_default_and_every_preset_give_simulation_the_weight_zero() -> None:
    assert StrengthSettings().weights[strength.SIMULATION] == 0.0
    assert strength.DEFAULT_WEIGHTS[strength.SIMULATION] == 0.0
    assert set(strength.PRESETS) == {"Ausgewogen", "Commander-nah", "Turniernah"}
    for name, preset in strength.PRESETS.items():
        assert preset.weights[strength.SIMULATION] == 0.0, name
    meta = strength_view.presets()
    assert meta["recommended"]["weights"][strength.SIMULATION] == 0.0  # type: ignore[index]
    label = meta["panel"]["labels"]["weights.simulation"]  # type: ignore[index]
    assert label == "Simulation (empfohlen: 0, derzeit ohne Daten)"


def test_no_component_but_the_adjustable_simulation_weight_is_simulation_derived() -> None:
    derived = {
        name
        for name in strength.COMPONENTS
        if "sim" in name or "sim" in strength.signal_for(name, "upgraded")
    }
    assert derived == {strength.SIMULATION}
    assert strength.signal_for(strength.SIMULATION, "upgraded") == ""  # no stored signal feeds it
    for component in strength_view.presets()["components"]:  # type: ignore[attr-defined]
        if component["key"] != strength.SIMULATION:
            assert component["default_weight"] > 0 or component["key"] == "simulation"


def _observations(with_simulation: bool) -> dict[str, dict[str, Observation]]:
    observations: dict[str, dict[str, Observation]] = {}
    for index, name in enumerate("abcdef"):
        per_card = {
            "commander_inclusion": Observation(index / 10, index * 10, 100),
            "synergy": Observation(0.1 * (6 - index)),
        }
        if with_simulation:
            per_card["simulation"] = Observation(float(index * index))
        observations[name] = per_card
    return observations


def test_with_weight_zero_a_simulation_value_changes_no_index_tier_or_coverage() -> None:
    collected = {"commander_inclusion", "synergy"}
    without = strength.score_pool(StrengthSettings(), _observations(False), collected)
    with_values = strength.score_pool(
        StrengthSettings(), _observations(True), {*collected, "simulation"}
    )
    assert len(without) == 6 and without.keys() == with_values.keys()
    for card, result in without.items():
        other = with_values[card]
        assert (result["index"], result["tier"], result["coverage"], result["present"]) == (
            other["index"],
            other["tier"],
            other["coverage"],
            other["present"],
        )


def test_the_weight_is_adjustable_and_then_counts() -> None:
    settings = StrengthSettings(weights={**strength.DEFAULT_WEIGHTS, "simulation": 4.0})
    collected = {"commander_inclusion", "synergy", "simulation"}
    default = strength.score_pool(StrengthSettings(), _observations(True), collected)
    weighted = strength.score_pool(settings, _observations(True), collected)
    assert [weighted[card]["index"] for card in "abcdef"] != [
        default[card]["index"] for card in "abcdef"
    ]


@pytest.fixture
def store(tmp_path: Path) -> StudioStore:
    opened = StudioStore.open(tmp_path / "studio")
    _fill(opened, tmp_path)
    return opened


def _store_simulation(store: StudioStore) -> None:
    source = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    with store.connection as db:
        db.execute(
            "INSERT INTO simulation_run(run_id, deck_id, pod, engine_pin, pilot_policy, seeds, "
            "games_planned, games_completed, games_failed, wins_fractional, hand_dwell_status, "
            "source_id) VALUES ('run-1', 'x', 'pod', 'pin', 'tuned', '[]', 5, 5, 0, 3.0, "
            "'OK', ?)",
            (source,),
        )
        db.execute(
            "INSERT INTO simulation_card(run_id, card_id, card_name, games_completed, "
            "games_offered, games_cast_after_offer, games_rotted, offered_castable, cast_count) "
            "VALUES ('run-1', 'card:project:0002', 'Forest', 5, 5, 5, 0, 5, 9)"
        )
    store.bind_unbound(COMMANDER)


def test_stored_simulation_runs_feed_neither_the_index_nor_the_tier_page_counts(
    store: StudioStore,
) -> None:
    weighted = StrengthSettings(weights={**strength.DEFAULT_WEIGHTS, "simulation": 5.0})
    before = strength_view.compute(store, COMMANDER, weighted)
    evidence_before = evidence.pool_evidence(store, [COMMANDER])
    _store_simulation(store)
    after = strength_view.compute(store, COMMANDER, weighted)
    assert after == before  # not even with a positive weight: no outcome model reads the rows
    row = next(
        item for item in after["cards"][0]["components"] if item["component"] == "simulation"
    )
    assert row["status"] == strength.NOT_COLLECTED
    evidence_after = evidence.pool_evidence(store, [COMMANDER])
    cards_before = {str(c["name"]): c for c in evidence_before["cards"]}  # type: ignore[attr-defined]
    cards_after = {str(c["name"]): c for c in evidence_after["cards"]}  # type: ignore[attr-defined]
    for name, card in cards_after.items():
        coverage = card["coverage"]
        assert "simulated_result" not in coverage["present"]  # type: ignore[index]
        assert "simulated_result" not in coverage["missing"]  # type: ignore[index]
        # the layer count the page sorts by is the same with and without simulation rows
        assert coverage["present"] == cards_before[name]["coverage"]["present"]  # type: ignore[index]
    forest = cards_after["Forest"]["layers"]["simulated_result"]  # type: ignore[index]
    assert forest["status"] == "PRESENT"  # still shown on its own, never counted


def test_the_research_list_does_not_flag_cards_as_not_simulated(store: StudioStore) -> None:
    payload = evidence.pool_evidence(store, [COMMANDER])
    cards = payload["cards"]
    assert isinstance(cards, list) and cards
    needs = {need for card in cards for need in card["coverage"]["needs"]}
    assert "NO_SIMULATION" not in needs
    assert needs  # other gaps are still listed
    # the layer itself stays available for the card detail
    assert all("simulated_result" in card["layers"] for card in cards)
