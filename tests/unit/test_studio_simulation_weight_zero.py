"""The strength index knows no simulation component (Q1-b4, #1679, Owner decision E15 Q1).

Before Q1-b4 the ``simulation`` weight stayed as an option at 0 (Owner decision 2026-11-12,
Refs #1205); E15 Q1 removed the component from the index together with rubric v1 and the
TopDeck conversion. Simulation results never feed the index or the tier page counts; a stored
profile that still holds ``weights.simulation`` loads (``RETIRED_SETTING_KEYS``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, evidence, strength, strength_view
from commander_lab.studio.strength import Observation, StrengthSettings
from tests.unit.test_studio_builder import _fill

COMMANDER = "Test Commander"
REMOVED = ("simulation", "rubric", "tournament_conversion")


def test_the_index_knows_no_simulation_component() -> None:
    """M1 probe of #1665: no component, weight, label, data class or signal of the index is
    simulation derived, and the settings panel offers no simulation weight."""
    derived = {
        name
        for name in strength.COMPONENTS
        if "sim" in name
        or "sim" in strength.signal_for(name, "upgraded")
        or strength.COMPONENT_DATA_CLASS.get(name) == "SIMULATED_RESULT"
    }
    assert derived == set()
    assert not hasattr(strength, "SIMULATION")
    assert "simulation" not in strength.DEFAULT_WEIGHTS
    assert "simulation" not in strength.LABELS
    assert "SIMULATED_RESULT" not in strength.COMPONENT_DATA_CLASS.values()
    meta = strength_view.presets()
    keys = [item["key"] for item in meta["components"]]  # type: ignore[attr-defined]
    assert "simulation" not in keys
    assert "simulation" not in meta["recommended"]["weights"]  # type: ignore[index]
    panel = meta["panel"]  # type: ignore[index]
    assert not [key for key in panel["labels"] if "simulation" in key]  # type: ignore[index]
    assert not [key for key in panel["help"] if "simulation" in key]  # type: ignore[index]
    grouped = [key for group in panel["groups"] for key in group["keys"]]  # type: ignore[index]
    assert not [key for key in grouped if "simulation" in key]
    # constructing settings with the component in code fails: it is not a component any more
    with pytest.raises(ValueError, match="unknown component"):
        StrengthSettings(weights={"simulation": 0.0})


def test_no_preset_and_no_component_list_names_a_removed_component() -> None:
    """Carries the core of the former ``test_every_preset_keeps_the_rubric_at_zero_and_
    simulation_too`` (``test_studio_rubric.py``): rubric v1, simulation and the TopDeck
    conversion are gone from the default, every preset and every component list."""
    assert set(strength.PRESETS) == {"Ausgewogen", "Commander-nah", "Turniernah"}
    assert strength.PRESETS["Ausgewogen"] == StrengthSettings()
    for name in REMOVED:
        assert name not in strength.COMPONENTS
        assert name not in strength.DEFAULT_WEIGHTS
        for preset_name, preset in strength.PRESETS.items():
            assert name not in preset.weights, (preset_name, name)
            assert name not in preset.to_dict()["weights"], (preset_name, name)  # type: ignore[operator]
        for group in (
            strength.SHARE_COMPONENTS,
            strength.COMMANDER_ONLY_SOURCES,
            strength.COMMANDER_SPECIFIC,
            strength.DIRECT_COMPONENTS,
        ):
            assert name not in group
    assert "conversion" not in strength.MIN_DENOMINATOR_KEYS
    assert "conversion" not in StrengthSettings().min_denominators
    # Playgroup stays a weight-0 column (not removed)
    for name, preset in strength.PRESETS.items():
        assert preset.weights[strength.PLAYGROUP_OBSERVED] == 0.0, name


def test_a_simulation_observation_is_not_read_by_the_index() -> None:
    """A stray ``simulation`` observation (or one of the other removed components) changes no
    index, tier, coverage or row: ``score_pool`` only reads the live components."""
    observations: dict[str, dict[str, Observation]] = {}
    for index, name in enumerate("abcdef"):
        observations[name] = {
            "commander_inclusion": Observation(index / 10, index * 10, 100),
            "synergy": Observation(0.1 * (6 - index)),
        }
    with_values = {
        card: {**per_card, **{name: Observation(float(i + 1)) for i, name in enumerate(REMOVED)}}
        for card, per_card in observations.items()
    }
    collected = {"commander_inclusion", "synergy"}
    without = strength.score_pool(StrengthSettings(), observations, collected)
    stray = strength.score_pool(StrengthSettings(), with_values, {*collected, *REMOVED})
    assert without == stray
    for result in stray.values():
        assert not [row for row in result["components"] if row["component"] in REMOVED]


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
    # a remembered setting that still carries a positive simulation weight is read without it
    weighted = StrengthSettings.from_dict({"weights": {"simulation": 5.0}})
    assert weighted == StrengthSettings()
    before = strength_view.compute(store, COMMANDER, weighted)
    evidence_before = evidence.pool_evidence(store, [COMMANDER])
    _store_simulation(store)
    after = strength_view.compute(store, COMMANDER, weighted)
    assert after == before  # no component reads the rows
    assert not [
        item
        for card in after["cards"]
        for item in card["components"]
        if item["component"] == "simulation"
    ]
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
