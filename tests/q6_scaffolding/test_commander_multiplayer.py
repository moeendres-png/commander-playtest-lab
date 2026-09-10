"""Tests: Commander / multiplayer mechanical signals (precision + coverage)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from q6_scaffolding.classify import classify_card
from q6_scaffolding.forge_parser import extract_features, parse_script

CARDS = Path(__file__).resolve().parent / "fixtures" / "cards"


def _card(name):
    return (CARDS / name).read_text(encoding="utf-8")


def _features(text, name="<memory>"):
    return extract_features(parse_script(text, name), text)


def _file_features(name):
    text = _card(name)
    return extract_features(parse_script(text, name), text)


def test_devoted_is_not_voting():
    feats = _features("Name:X\nOracle:Devoted druid. Devotion to green.\nA:AB$ Mana | Cost$ T\n")
    assert feats["has_multiplayer"] is False
    assert feats.get("multiplayer_signals", []) == []


def test_steam_is_not_a_team():
    feats = _features("Name:Steam\nOracle:Steam vents hiss. Steampunk contraption.\n")
    assert feats["has_multiplayer"] is False


def test_councils_judgment_vote_and_multiplayer():
    feats = _file_features("councils_judgment.txt")
    assert feats["has_multiplayer"] is True
    assert "vote" in feats["multiplayer_signals"]


def test_target_opponent_detected():
    feats = _file_features("aggressive_sabotage.txt")
    assert feats["has_multiplayer"] is True
    assert "target opponent" in feats["multiplayer_signals"]


def test_braids_each_opponent():
    feats = _file_features("braids_arisen_nightmare.txt")
    assert feats["has_multiplayer"] is True
    assert "each opponent" in feats["multiplayer_signals"]


def test_starting_with_you_detected():
    feats = _features("Name:X\nOracle:Starting with you, each player votes.\n")
    assert feats["has_multiplayer"] is True
    assert "starting with you" in feats["multiplayer_signals"]


def test_multiplayer_maps_to_family_and_pretag():
    feats = _features("Name:X\nA:SP$ Vote | Choices$ A,B | Oracle:Each player votes for a boon.\n")
    classification = classify_card("id-mp", feats)
    assert "MULTIPLAYER_OPPONENT_SELECTION" in classification.capability_families
    kinds = [t["kind"] for t in classification.expected_decision_pretags]
    assert "VOTE_CHOICE" in kinds or "OPPONENT_CHOICE" in kinds


def test_each_opponent_without_choices_has_family_but_no_choice_pretag():
    feats = _features("Name:X\nOracle:Each opponent sacrifices a creature.\n")
    classification = classify_card("id-mp2", feats)
    assert "MULTIPLAYER_OPPONENT_SELECTION" in classification.capability_families


def test_command_tower_commander_signal():
    feats = _file_features("command_tower.txt")
    assert feats["has_commander"] is True
    classification = classify_card("id-ct", feats)
    assert "COMMANDER_MECHANIC" in classification.capability_families


def test_partner_is_commander_signal():
    feats = _file_features("vial_smasher_the_fierce.txt")
    assert feats["has_commander"] is True


def test_command_zone_reference_is_commander_signal():
    feats = _features("Name:X\nOracle:Put it into the command zone.\n")
    assert feats["has_commander"] is True


def test_plain_creature_has_neither_signal():
    feats = _features("Name:X\nManaCost:1 G\nTypes:Creature Elf\nPT:1/1\n")
    assert feats["has_commander"] is False
    assert feats["has_multiplayer"] is False
