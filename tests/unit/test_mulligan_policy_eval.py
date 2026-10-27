"""The mulligan ruler (scripts/mulligan_policy_eval.py) and the colours a card makes (#989)."""

from __future__ import annotations

import importlib.util
import statistics
import sys
from pathlib import Path

import pytest

from commander_lab.agents.card_knowledge import card_facts
from commander_lab.agents.pilots import BasePilot
from commander_lab.models import PilotStrength

ROOT = Path(__file__).resolve().parents[2]
PRECONS = sorted((ROOT / "data/decks/precons").glob("*.json"))[::20]


@pytest.fixture(scope="module")
def ruler():
    spec = importlib.util.spec_from_file_location(
        "mulligan_policy_eval", ROOT / "scripts/mulligan_policy_eval.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_colours_made_by_lands() -> None:
    assert card_facts("Forest").colours_made == frozenset("G")  # type: ignore[union-attr]
    assert card_facts("Command Tower").colours_made == frozenset("WUBRG")  # type: ignore[union-attr]
    # A fetch land fixes any colour even though it makes no mana itself.
    assert card_facts("Evolving Wilds").colours_made == frozenset("WUBRG")  # type: ignore[union-attr]
    # A spell makes no colour by being a spell.
    assert card_facts("Counterspell").colours_made == frozenset()  # type: ignore[union-attr]


def test_ruler_ranks_the_policies_in_the_expected_order(ruler) -> None:
    """Wrong-reason control: a ruler that cannot tell keeping everything from judging is no ruler."""
    reports = {
        policy: ruler.evaluate(PRECONS, 60, 5, policy, PilotStrength.AVERAGE)
        for policy in ("always_keep", "pilot")
    }
    keep_all, pilot = reports["always_keep"], reports["pilot"]
    assert pilot["mana_spent"] > keep_all["mana_spent"]
    assert pilot["missed_land_drops"] < keep_all["missed_land_drops"]
    assert pilot["colour_blocked_turns"] < keep_all["colour_blocked_turns"]
    assert pilot["share_no_spell"] < keep_all["share_no_spell"]
    assert keep_all["mulligans_per_hand"] == 0.0
    assert pilot["mulligans_per_hand"] > 0.0


def test_ruler_is_deterministic(ruler) -> None:
    first = ruler.evaluate(PRECONS[:3], 20, 9, "pilot", PilotStrength.AVERAGE)
    second = ruler.evaluate(PRECONS[:3], 20, 9, "pilot", PilotStrength.AVERAGE)
    assert first == second


def test_refit_on_173_pool_documents_r2_and_paired_12_seed_comparison(
    ruler, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refit on 173 pool (#1038): pool provenance, deterministic OLS fit, and paired 12-seed ruler."""
    pool = ruler.pool_173_deck_paths(ROOT)
    assert len(pool) == 173
    variant_proxies = [p for p in pool if p.parent.name == "precon_variants"]
    assert len(variant_proxies) == 9

    # Fast deterministic sub-pool fit (< 2s)
    fit = ruler.fit_opening_hand_model(pool[:24], hands_per_deck=25, seed=7)
    assert fit["decks_total"] == 24
    assert fit["train_decks"] == 18
    assert fit["holdout_decks"] == 6
    assert 0.25 <= fit["r2_train_new"] <= 0.45
    assert 0.25 <= fit["r2_holdout_new"] <= 0.45
    assert 0.25 <= fit["r2_train_current"] <= 0.45
    assert 0.25 <= fit["r2_holdout_current"] <= 0.45
    assert fit["model_at_limit"] is True

    # Paired 12-seed comparison between current 195-fit and 173-refit on the ruler
    test_decks = PRECONS[:2]
    current_mana, current_spells, current_mulls, current_missed = [], [], [], []
    for seed in range(1, 13):
        rep = ruler.evaluate(test_decks, 10, seed, "pilot", PilotStrength.AVERAGE)
        current_mana.append(rep["mana_spent"])
        current_spells.append(rep["spells_cast"])
        current_mulls.append(rep["mulligans_per_hand"])
        current_missed.append(rep["missed_land_drops"])

    # Evaluate 173-refit via monkeypatching BasePilot attributes with REFIT_173
    refit_dict: dict[str, object] = ruler.REFIT_173
    monkeypatch.setattr(BasePilot, "_OPENING_CELLS", refit_dict["cells"])
    monkeypatch.setattr(BasePilot, "_OPENING_COLOUR_GAP", refit_dict["colour_gap"])
    monkeypatch.setattr(BasePilot, "_OPENING_COMMANDER_GAP", refit_dict["commander_gap"])
    monkeypatch.setattr(BasePilot, "_OPENING_FIRST_RAMP", refit_dict["first_ramp"])
    monkeypatch.setattr(BasePilot, "_OPENING_SECOND_RAMP", refit_dict["second_ramp"])
    monkeypatch.setattr(BasePilot, "_OPENING_EARLY_VELOCITY", refit_dict["early_velocity"])
    monkeypatch.setattr(BasePilot, "_OPENING_EXPENSIVE", refit_dict["expensive"])
    monkeypatch.setattr(BasePilot, "_OPENING_FRESH_SEVEN", refit_dict["fresh_seven"])

    refit_mana, refit_spells, refit_mulls, refit_missed = [], [], [], []
    for seed in range(1, 13):
        rep = ruler.evaluate(test_decks, 10, seed, "pilot", PilotStrength.AVERAGE)
        refit_mana.append(rep["mana_spent"])
        refit_spells.append(rep["spells_cast"])
        refit_mulls.append(rep["mulligans_per_hand"])
        refit_missed.append(rep["missed_land_drops"])

    mean_current_mana = statistics.fmean(current_mana)
    mean_refit_mana = statistics.fmean(refit_mana)
    assert abs(mean_refit_mana - mean_current_mana) < 0.25
    assert abs(statistics.fmean(refit_spells) - statistics.fmean(current_spells)) < 0.25
    assert abs(statistics.fmean(refit_mulls) - statistics.fmean(current_mulls)) < 0.25
    assert abs(statistics.fmean(refit_missed) - statistics.fmean(current_missed)) < 0.25
