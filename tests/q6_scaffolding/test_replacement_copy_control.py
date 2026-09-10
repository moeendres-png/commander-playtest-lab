"""Tests: replacement / prevention / copy / control boundary (no Rules engine)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from q6_scaffolding.classify import classify_card
from q6_scaffolding.forge_parser import extract_features, parse_script
from q6_scaffolding.skeleton import generate_skeleton, route_state

CARDS = Path(__file__).resolve().parent / "fixtures" / "cards"


def _card(name):
    return (CARDS / name).read_text(encoding="utf-8")


def _features(text, name="<memory>"):
    return extract_features(parse_script(text, name), text)


def _file_features(name):
    text = _card(name)
    return extract_features(parse_script(text, name), text)


def _routed(name):
    text = _card(name)
    parsed = parse_script(text, name)
    feats = extract_features(parsed, text)
    classification = classify_card(name, feats)
    skeleton = generate_skeleton(name, name, feats, classification)
    state, reasons = route_state(
        ambiguous=parsed["ambiguous"],
        unsupported=parsed["unsupported"],
        features=feats,
        classification=classification,
        skeleton=skeleton,
    )
    return feats, classification, skeleton, state, reasons


def test_replacement_line_drives_family_and_question():
    feats, classification, skeleton, state, _ = _routed("rest_in_peace.txt")
    assert feats["has_replacement"] is True
    assert "REPLACEMENT_EFFECT" in classification.capability_families
    kinds = {q["related_capability"] for q in skeleton.rules_questions}
    assert "REPLACEMENT_EFFECT" in kinds
    assert state.value == "RULES_ADJUDICATION_REQUIRED"


def test_replace_verbs_drive_replacement_flag():
    feats, _, _, _, _ = _routed("doubling_season.txt")
    assert feats["has_replacement"] is True
    assert feats["unknown_ability_verbs"] == []


def test_fog_prevention_routes_to_adjudication_not_support():
    feats, _, skeleton, state, _ = _routed("fog.txt")
    assert feats["prevention_adjudication_verbs"] == ["Fog"]
    kinds = {q["related_capability"] for q in skeleton.rules_questions}
    assert "REPLACEMENT_EFFECT" in kinds
    assert state.value == "RULES_ADJUDICATION_REQUIRED"


def test_layer_verbs_route_to_layers_question():
    feats, _, skeleton, state, _ = _routed("artificial_evolution.txt")
    assert feats["layer_adjudication_verbs"] == ["ChangeText"]
    kinds = {q["related_capability"] for q in skeleton.rules_questions}
    assert "LAYER_CHARACTERISTIC" in kinds
    assert state.value == "RULES_ADJUDICATION_REQUIRED"


def test_layer_family_registered():
    feats = _features("Name:X\nA:SP$ Animate | Defined$ Self\n")
    classification = classify_card("id-layer", feats)
    assert "LAYER_CHARACTERISTIC" in classification.capability_families


def test_clone_copy_routes_to_copy_question():
    feats, _, skeleton, state, _ = _routed("clone.txt")
    assert feats["has_copy_control"] is True
    kinds = {q["related_capability"] for q in skeleton.rules_questions}
    assert "COPY_CONTROL" in kinds
    assert state.value == "RULES_ADJUDICATION_REQUIRED"


def test_exchange_life_is_not_copy_control():
    feats = _features("Name:X\nA:AB$ ExchangeLife | Defined$ You | ValidTgts$ Opponent\n")
    assert feats["has_copy_control"] is False


def test_cyclonic_rift_is_not_a_clone():
    feats = _features(
        "Name:Cyclonic Rift\n"
        "A:SP$ ChangeZoneAll | ValidCards$ Creature.OppCtrl | Origin$ Battlefield\n"
    )
    assert feats["has_copy_control"] is False


def test_control_spell_forces_manual_review():
    feats, _, _, state, reasons = _routed("aethersnatch.txt")
    assert feats["manual_review_verbs"] == ["ControlSpell"]
    assert state.value == "MANUAL_REVIEW_REQUIRED"
    assert reasons == ["verb_manual_review:ControlSpell"]


def test_subgame_verb_forces_manual_review():
    feats = _features("Name:X\nA:SP$ Subgame | SubAbility$ DBDraw\n")
    _, _, _, _, _ = (None, None, None, None, None)
    classification = classify_card("id-sub", feats)
    skeleton = generate_skeleton("id-sub", "Sub", feats, classification)
    state, reasons = route_state(
        ambiguous=False,
        unsupported=[],
        features=feats,
        classification=classification,
        skeleton=skeleton,
    )
    assert state.value == "MANUAL_REVIEW_REQUIRED"
    assert reasons == ["verb_manual_review:Subgame"]


def test_combat_restriction_maps_to_combat_family():
    feats = _file_features("propaganda.txt")
    assert feats["has_combat"] is True
    classification = classify_card("id-combat", feats)
    assert "COMBAT" in classification.capability_families


def test_no_rules_semantics_encoded_for_copy():
    # The parser records the copy shape; it never records what the copy
    # becomes, layer order, or timestamps.
    feats = _file_features("clone.txt")
    blob = repr(feats)
    assert "timestamp" not in blob
    assert "layer" not in blob.lower() or "layer_adjudication_verbs" in blob
