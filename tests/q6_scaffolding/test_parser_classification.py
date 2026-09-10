"""Tests: parser and classification behavior on real card scripts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import pytest
from q6_scaffolding.classify import (
    PRETAG_AUTHORITY,
    PRETAG_TRUTH_SOURCE,
    classify_card,
    family_names,
    primary_capability,
    register_family,
)
from q6_scaffolding.forge_parser import extract_features, parse_script

CARDS = Path(__file__).resolve().parent / "fixtures" / "cards"


def _card(name):
    return (CARDS / name).read_text(encoding="utf-8")


def _features(name):
    text = _card(name)
    return extract_features(parse_script(text, name), text)


def test_lightning_bolt_targets_and_ready_signals():
    feats = _features("lightning_bolt.txt")
    assert feats["has_targets"] is True
    assert feats["has_mana_cost"] is True
    assert feats["has_x_value"] is False
    assert feats["has_trigger"] is False


def test_fireball_x_value_detected():
    feats = _features("fireball.txt")
    assert feats["has_x_value"] is True
    assert feats["has_targets"] is True


def test_braids_svar_name_is_not_x_value():
    feats = _features("braids_arisen_nightmare.txt")
    assert feats["has_x_value"] is False
    assert feats["nested_svar"] is True
    assert feats["has_multiplayer"] is True
    assert feats["has_trigger"] is True


def test_boros_charm_modal():
    feats = _features("boros_charm.txt")
    assert feats["has_modal_choice"] is True


def test_sundering_modal_faces_parsed_without_ambiguity():
    parsed = parse_script(_card("sundering_eruption_volcanic_fissure.txt"), "sundering")
    assert parsed["ambiguous"] is False
    faces = [ln for ln in parsed["lines"] if ln["kind"] == "Face"]
    assert len(faces) == 2  # AlternateMode:Modal + bare ALTERNATE separator
    assert parsed["unsupported"] == []


def test_gisela_meldpair_unsupported():
    parsed = parse_script(
        _card("gisela_the_broken_blade_brisela_voice_of_nightmares.txt"), "gisela"
    )
    assert "topkey:MeldPair" in parsed["unsupported"]


def test_ai_hint_line_is_benign_allowlisted():
    parsed = parse_script(_card("willbender.txt"), "willbender")
    assert parsed["unsupported"] == []
    assert parsed["ambiguous"] is False


def test_willbender_hidden_info():
    assert _features("willbender.txt")["has_hidden"] is True


def test_frenetic_efreet_randomness():
    assert _features("frenetic_efreet.txt")["has_random"] is True


def test_tutor_shuffle_is_not_randomness():
    feats = _features("sundering_eruption_volcanic_fissure.txt")
    assert feats["has_random"] is False
    assert feats["has_shuffle"] is True


def test_force_of_will_alternative_cost_not_trigger_mode():
    feats = _features("force_of_will.txt")
    assert feats["has_alternative_cost"] is True
    assert feats["unknown_trigger_modes"] == []
    assert feats["has_trigger"] is False


def test_soul_warden_trigger_with_known_mode():
    feats = _features("soul_warden.txt")
    assert feats["has_trigger"] is True
    assert feats["unknown_trigger_modes"] == []


def test_councils_judgment_vote_and_multiplayer():
    feats = _features("councils_judgment.txt")
    assert feats["has_multiplayer"] is True
    assert feats["has_choices"] is True


def test_missing_colon_is_ambiguous():
    parsed = parse_script("Name:X\nThis line has no separator\n", "bad")
    assert parsed["ambiguous"] is True
    assert any(d["code"] == "missing_colon" for d in parsed["diagnostics"])


def test_duplicate_params_are_ambiguous():
    parsed = parse_script("A:SP$ Draw | NumCards$ 1 | NumCards$ 2\n", "dup")
    assert parsed["ambiguous"] is True


def test_svar_without_separator_is_ambiguous():
    parsed = parse_script("SVar:NoSeparatorHere\n", "svar")
    assert parsed["ambiguous"] is True


def test_unknown_topkey_is_unsupported_not_ambiguous():
    parsed = parse_script("Name:X\nMeldPair:Y\n", "meld")
    assert parsed["unsupported"] == ["topkey:MeldPair"]
    assert parsed["ambiguous"] is False


def test_parser_never_throws_on_garbage():
    parsed = parse_script("\x00:\n:::\nA:SP no dollars\nSVar\n", "garbage")
    assert parsed["diagnostics"]


def test_classification_pretags_are_hypotheses_only():
    classification = classify_card("id-1", _features("lightning_bolt.txt"))
    assert "TARGET_SELECTION" in classification.capability_families
    kinds = [t["kind"] for t in classification.expected_decision_pretags]
    assert "TARGET_SELECTION" in kinds
    for tag in classification.expected_decision_pretags:
        assert tag["authority"] == PRETAG_AUTHORITY
        assert tag["truth_source"] == PRETAG_TRUTH_SOURCE


def test_pretags_deduplicated_and_ordered():
    classification = classify_card("id-2", _features("councils_judgment.txt"))
    kinds = [t["kind"] for t in classification.expected_decision_pretags]
    assert kinds == sorted(set(kinds), key=kinds.index)
    assert len(kinds) == len(set(kinds))


def test_primary_capability_selects_distinctive_family():
    assert primary_capability(["MANA_PAYMENT_CHOICE", "TARGET_SELECTION"]) == ("TARGET_SELECTION")
    assert primary_capability([]) == "UNCLUSTERED"


def test_taxonomy_extension_requires_provenance():
    with pytest.raises(ValueError):
        register_family("TEST_FAMILY_X1", "description", "")
    with pytest.raises(ValueError):
        register_family("", "description", "provenance")
    family = register_family("TEST_FAMILY_X1", "test-only family", "unit test provenance")
    assert "TEST_FAMILY_X1" in family_names()
    assert family.provenance == "unit test provenance"
    with pytest.raises(ValueError):
        register_family("TEST_FAMILY_X1", "again", "provenance")


def test_all_clustered_families_are_registered():
    for name in (
        "divination.txt",
        "lightning_bolt.txt",
        "braids_arisen_nightmare.txt",
        "willbender.txt",
    ):
        classification = classify_card(name, _features(name))
        for family in classification.capability_families:
            assert family in family_names(), f"unregistered family {family}"
