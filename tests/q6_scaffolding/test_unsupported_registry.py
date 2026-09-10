"""Tests: unsupported-construct registry (explicit, stable, fail-closed)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from q6_scaffolding.classify import classify_card
from q6_scaffolding.forge_parser import extract_features, parse_script
from q6_scaffolding.registries import unsupported_registry
from q6_scaffolding.skeleton import generate_skeleton, route_state

CARDS = Path(__file__).resolve().parent / "fixtures" / "cards"


def _card(name):
    return (CARDS / name).read_text(encoding="utf-8")


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
    return parsed, feats, state, reasons


def test_gisela_meldpair_still_unsupported():
    parsed, _, state, reasons = _routed("gisela_the_broken_blade_brisela_voice_of_nightmares.txt")
    assert "topkey:MeldPair" in parsed["unsupported"]
    assert state.value == "UNSUPPORTED"
    assert reasons == ["unsupported_construct:topkey:MeldPair"]


def test_handlifemodifier_avatar_unsupported():
    _, _, state, reasons = _routed("akroma_angel_of_wrath_avatar.txt")
    assert state.value == "UNSUPPORTED"
    assert reasons == ["unsupported_construct:topkey:HandLifeModifier"]


def test_draft_card_unsupported():
    _, _, state, reasons = _routed("aether_searcher.txt")
    assert state.value == "UNSUPPORTED"
    assert reasons == ["unsupported_construct:topkey:Draft"]


def test_setcolorid_unsupported():
    _, _, state, reasons = _routed("cryptic_spires.txt")
    assert state.value == "UNSUPPORTED"
    assert reasons == ["unsupported_construct:topkey:SETCOLORID"]


def test_registry_covers_every_parser_unsupported_topkey():
    patterns = {c["pattern"] for c in unsupported_registry()["constructs"]}
    for topkey in (
        "topkey:HandLifeModifier",
        "topkey:Draft",
        "topkey:MeldPair",
        "topkey:SETCOLORID",
        "topkey:Lights",
    ):
        assert topkey in patterns, f"unsupported topkey missing from registry: {topkey}"


def test_dbcleanup_is_parsed_not_unsupported():
    parsed, feats, _state, _ = _routed("spirit_of_resilience.txt")
    assert parsed["unsupported"] == []
    assert parsed["ambiguous"] is False
    assert "DBCleanup" in feats["svar_names"]


def test_copyfacefrom_is_face_record_not_unsupported():
    parsed, _, _state, _ = _routed("bind_liberate.txt")
    assert parsed["unsupported"] == []
    faces = [ln for ln in parsed["lines"] if ln["kind"] == "Face"]
    assert any(f["key"] == "CopyFaceFrom" for f in faces)


def test_unknown_verb_exact_and_manual():
    text = "Name:X\nA:SP$ Frobnicate | NumCards$ 1\n"
    parsed = parse_script(text, "synthetic")
    feats = extract_features(parsed, text)
    assert feats["unknown_ability_verbs"] == ["Frobnicate"]
    classification = classify_card("id-frob", feats)
    skeleton = generate_skeleton("id-frob", "Frob", feats, classification)
    state, reasons = route_state(
        ambiguous=parsed["ambiguous"],
        unsupported=parsed["unsupported"],
        features=feats,
        classification=classification,
        skeleton=skeleton,
    )
    assert state.value == "MANUAL_REVIEW_REQUIRED"
    assert reasons == ["unknown_ability_verbs:Frobnicate"]


def test_no_card_name_exceptions_in_parser():
    import tokenize

    import q6_scaffolding.forge_parser as parser_mod

    # Card names may appear in comments/docstrings as motivating examples;
    # they must never drive code (no name-keyed branches or table keys).
    with open(parser_mod.__file__, encoding="utf-8") as handle:
        tokens = tokenize.generate_tokens(handle.readline)
        code_text = " ".join(
            tok.string for tok in tokens if tok.type not in (tokenize.COMMENT, tokenize.STRING)
        ).lower()
    for name in ("gisela", "braids", "lightning", "black lotus", "charizard"):
        assert name not in code_text, f"card-name hack in parser code: {name}"
