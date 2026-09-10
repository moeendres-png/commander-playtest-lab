"""Tests: randomness taxonomy (shuffle != discretionary randomness)."""

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


def test_frenetic_efreet_coin_flip():
    feats = _file_features("frenetic_efreet.txt")
    assert feats["has_random"] is True
    assert "COIN_FLIP" in feats["random_kinds"]


def test_tutor_shuffle_is_not_randomness():
    feats = _file_features("sundering_eruption_volcanic_fissure.txt")
    assert feats["has_random"] is False
    assert feats["has_shuffle"] is True
    assert feats["random_kinds"] == ["SHUFFLE"]


def test_rampant_growth_search_shuffle_not_random():
    feats = _file_features("rampant_growth.txt")
    assert feats["has_random"] is False
    assert "SHUFFLE" in feats["random_kinds"]


def test_flay_random_discard():
    feats = _file_features("flay.txt")
    assert feats["has_random"] is True
    assert "RANDOM_DISCARD" in feats["random_kinds"]
    assert "SHUFFLE" not in feats["random_kinds"]


def test_mana_crypt_coin_flip():
    feats = _file_features("mana_crypt.txt")
    assert "COIN_FLIP" in feats["random_kinds"]
    assert feats["has_random"] is True


def test_delina_die_roll():
    feats = _file_features("delina_wild_mage.txt")
    assert "DIE_ROLL" in feats["random_kinds"]
    assert feats["has_random"] is True


def test_troll_is_not_a_die_roll():
    feats = _features(
        "Name:Troll\nManaCost:2 G\nTypes:Creature Troll\nPT:2/2\n"
        "A:SP$ Pump | NumAtt$ +1 | SpellDescription$ Troll gets +1/+0.\n"
    )
    assert feats["has_random"] is False
    assert feats["random_kinds"] == []


def test_would_die_is_not_a_die_roll():
    feats = _features(
        "Name:X\nT:Mode$ ChangesZone | Origin$ Battlefield | Execute$ Foo\n"
        "SVar:Foo:DB$ Draw | SpellDescription$ If it would die, draw a card.\n"
    )
    assert "DIE_ROLL" not in feats["random_kinds"]
    assert feats["has_random"] is False


def test_flip_card_is_not_a_coin_flip():
    feats = _features("Name:X\nA:AB$ SetState | Mode$ Flip | SpellDescription$ Flip CARDNAME.\n")
    assert "COIN_FLIP" not in feats["random_kinds"]
    assert feats["has_random"] is False


def test_ai_hint_random_is_not_mechanics():
    feats = _features("Name:X\nManaCost:2 G\nTypes:Creature\nPT:2/2\nAI:RemoveDeck:Random\n")
    assert feats["has_random"] is False
    assert feats["random_kinds"] == []


def test_synthetic_coin_flip_phrase():
    feats = _features("Name:X\nA:AB$ Effect | SpellDescription$ Flip a coin.\n")
    assert "COIN_FLIP" in feats["random_kinds"]
    assert feats["has_random"] is True


def test_random_order_is_randomness_not_shuffle():
    feats = _features(
        "Name:X\n"
        "A:SP$ Dig | DigNum$ 5 | RestRandomOrder$ True | "
        "SpellDescription$ Put the rest on the bottom in a random order.\n"
    )
    assert "RANDOM_ORDER" in feats["random_kinds"]
    assert feats["has_random"] is True
