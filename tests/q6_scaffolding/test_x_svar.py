"""Tests: X / SVar / symbolic-value distinctions (Task-2A correction kept)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from q6_scaffolding.forge_parser import extract_features, parse_script

CARDS = Path(__file__).resolve().parent / "fixtures" / "cards"


def _card(name):
    return (CARDS / name).read_text(encoding="utf-8")


def _features(text, name="<memory>"):
    return extract_features(parse_script(text, name), text)


def _file_features(name):
    text = _card(name)
    return extract_features(parse_script(text, name), text)


def test_fireball_mana_and_numeric_x():
    feats = _file_features("fireball.txt")
    assert feats["has_x_value"] is True
    assert "MANACOST_X" in feats["x_sources"]
    assert "NUMERIC_X" in feats["x_sources"]


def test_braids_svar_name_x_is_not_a_mechanic():
    feats = _file_features("braids_arisen_nightmare.txt")
    assert feats["has_x_value"] is False
    assert "NUMERIC_X" not in feats["x_sources"]
    assert "MANACOST_X" not in feats["x_sources"]


def test_svar_x_count_definition_is_state_defined():
    feats = _file_features("ajani_unrelenting.txt")
    assert "SVAR_X_DEFINED" in feats["x_sources"]
    assert "X_COUNT_DEFINED" in feats["x_sources"]
    # Ajani's NumCards$ X is a variable amount in an effect body.
    assert "NUMERIC_X" in feats["x_sources"]
    assert feats["has_x_value"] is True


def test_standalone_x_in_numeric_slot_counts():
    feats = _features("Name:X\nA:SP$ DealDamage | NumDmg$ X\n")
    assert feats["has_x_value"] is True
    assert feats["x_sources"] == ["NUMERIC_X"]


def test_x_inside_words_is_not_x_value():
    feats = _features("Name:X\nA:SP$ Draw | NumCards$ 1 | SpellDescription$ Exile text box\n")
    assert feats["has_x_value"] is False
    assert feats["x_sources"] == []


def test_condition_cross_reference_to_x_is_symbolic():
    feats = _features(
        "Name:X\n"
        "A:SP$ Draw | NumCards$ 1 | SubAbility$ DBDraw\n"
        "SVar:DBDraw:DB$ Draw | ConditionCheckSVar$ X | ConditionSVarCompare$ GT0\n"
    )
    assert "X_CONDITION_REF" in feats["x_sources"]
    # The symbolic reference alone is not an X mechanic.
    assert "NUMERIC_X" not in feats["x_sources"]
    assert feats["has_x_value"] is False


def test_astral_cornucopia_chosen_and_defined_x():
    feats = _file_features("astral_cornucopia.txt")
    assert "MANACOST_X" in feats["x_sources"]
    assert "SVAR_X_DEFINED" in feats["x_sources"]
    assert "X_COUNT_DEFINED" in feats["x_sources"]
    assert feats["has_x_value"] is True


def test_finale_x_with_condition_reference():
    feats = _file_features("finale_of_devastation.txt")
    assert "MANACOST_X" in feats["x_sources"]
    assert "X_CONDITION_REF" in feats["x_sources"]


def test_no_x_sources_for_vanilla_creature():
    feats = _features("Name:X\nManaCost:G\nTypes:Creature\nPT:2/2\nK:Trample\n")
    assert feats["has_x_value"] is False
    assert feats["x_sources"] == []
