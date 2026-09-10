"""Tests: trigger/mode disambiguation (no substring-only TRIGGERED_CHOICE)."""

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


def test_true_trigger_records_only_from_t_lines():
    feats = _features("Name:X\nT:Mode$ ChangesZone | Execute$ Foo\n")
    assert feats["has_trigger"] is True
    assert feats["trigger_modes"] == ["ChangesZone"]
    assert feats["unknown_trigger_modes"] == []


def test_static_alternative_cost_is_payment_not_trigger():
    feats = _features("Name:X\nS:Mode$ AlternativeCost | Cost$ ExileCard\n")
    assert feats["has_trigger"] is False
    assert feats["has_alternative_cost"] is True
    assert feats["has_modal_choice"] is False
    assert feats["unknown_trigger_modes"] == []


def test_static_mode_is_not_trigger_mode():
    feats = _features("Name:X\nS:Mode$ Continuous | Affected$ You\n")
    assert feats["has_trigger"] is False
    assert feats["trigger_modes"] == []
    assert feats["static_mode_classes"] == ["STATIC_CONTINUOUS"]


def test_ability_trigger_condition_is_not_modal_choice():
    feats = _features("Name:X\nA:AB$ DelayedTrigger | Mode$ SpellCast | Execute$ Foo\n")
    assert feats["has_trigger"] is True  # DelayedTrigger verb drives trigger
    assert feats["has_trigger_condition"] is True
    assert feats["has_modal_choice"] is False
    assert feats["ability_mode_classes"] == ["TRIGGER_CONDITION"]


def test_ability_targeting_mode_is_not_modal_choice():
    feats = _features("Name:X\nA:SP$ Discard | ValidTgts$ Opponent | Mode$ TgtChoose\n")
    assert feats["has_modal_choice"] is False
    assert feats["ability_mode_classes"] == ["TARGETING_SELECTOR"]
    assert feats["has_targets"] is True


def test_ability_random_mode_drives_randomness_not_modal():
    feats = _features("Name:X\nA:SP$ Discard | ValidTgts$ Player | Mode$ Random\n")
    assert feats["has_modal_choice"] is False
    assert "RANDOM_SELECT" in feats["random_kinds"] or feats["has_random"] is True


def test_charm_verb_and_modal_face_are_modal():
    feats = _features("Name:X\nA:SP$ Charm | Choices$ A,B\n")
    assert feats["has_modal_choice"] is True
    feats = _features("Name:X\nAlternateMode:Modal\n")
    assert feats["has_modal_choice"] is True


def test_can_repeat_modes_is_modal_meta():
    feats = _features("Name:X\nA:SP$ Charm | CanRepeatModes$ True\n")
    assert feats["has_modal_choice"] is True


def test_unknown_ability_mode_reported_exactly_not_coerced():
    feats = _features("Name:X\nA:SP$ Draw | Mode$ Frobnicate\n")
    assert feats["unknown_ability_modes"] == ["Frobnicate"]
    assert feats["has_modal_choice"] is False


def test_unknown_static_mode_reported_exactly():
    feats = _features("Name:X\nS:Mode$ Frobnicate | Affected$ You\n")
    assert feats["unknown_static_modes"] == ["Frobnicate"]


def test_once_variant_modes_are_registered_triggers():
    feats = _features("Name:X\nT:Mode$ DamageDoneOnce | Execute$ Foo\n")
    assert feats["unknown_trigger_modes"] == []
    assert feats["has_trigger"] is True


def test_svar_static_fragment_vs_effect_body():
    feats = _features(
        "Name:X\n"
        "S:Mode$ Continuous | Affected$ You\n"
        "SVar:STCant:Mode$ CantBeCast | ValidCard$ Instant\n"
        "SVar:Body:DB$ Draw | NumCards$ 1\n"
    )
    assert feats["svar_fragment_kinds"].get("STATIC_FRAGMENT") == 1
    assert feats["svar_fragment_kinds"].get("EFFECT_FRAGMENT") == 1


def test_svar_trigger_fragment():
    feats = _features("Name:X\nSVar:Trig:Mode$ ChangesZone | Origin$ Battlefield | Execute$ Foo\n")
    assert feats["svar_fragment_kinds"].get("TRIGGER_FRAGMENT") == 1


def test_adaptive_training_post_delayed_trigger_not_modal():
    feats = _file_features("adaptive_training_post.txt")
    assert feats["has_modal_choice"] is False
    assert feats["has_trigger"] is True
    assert feats["has_trigger_condition"] is True


def test_aggressive_sabotage_tgtchoose_not_modal():
    feats = _file_features("aggressive_sabotage.txt")
    assert feats["has_modal_choice"] is False
    assert "TARGETING_SELECTOR" in feats["ability_mode_classes"]


def test_trigger_condition_maps_to_triggered_family():
    feats = _features("Name:X\nA:AB$ DelayedTrigger | Mode$ SpellCast | Execute$ Foo\n")
    classification = classify_card("id-tc", feats)
    assert "TRIGGERED_CHOICE" in classification.capability_families
