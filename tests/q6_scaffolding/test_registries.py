"""Tests: versioned grammar registries (data-driven, provenance-bearing)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from q6_scaffolding.registries import (
    KNOWN_FLAGS,
    ability_mode_class,
    is_known_trigger_mode,
    static_mode_class,
    static_mode_registry,
    trigger_mode_registry,
    unsupported_registry,
    verb_registry,
    verb_shape,
)

from q6_scaffolding import registries

REPO_ROOT = Path(__file__).resolve().parents[2]
BEFORE = json.loads(
    (
        REPO_ROOT
        / "docs"
        / "qualification"
        / "q6-scaffolding"
        / "evidence"
        / "corpus-inventory-before.json"
    ).read_text(encoding="utf-8")
)

TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")


def test_registries_carry_versions_and_provenance():
    assert verb_registry()["registry_version"] == "q6-verb-registry-0.2.0"
    assert trigger_mode_registry()["registry_version"] == "q6-trigger-mode-registry-0.2.0"
    assert static_mode_registry()["registry_version"] == "q6-static-mode-registry-0.2.0"
    assert unsupported_registry()["registry_version"] == "q6-unsupported-registry-0.2.0"
    for doc in (
        verb_registry(),
        trigger_mode_registry(),
        static_mode_registry(),
        unsupported_registry(),
    ):
        assert doc["provenance"], "registries must be provenance-bearing"
        assert doc["schema"].startswith("q6.")


def test_registry_keys_are_generic_grammar_not_card_names():
    for verb in verb_registry()["verbs"]:
        assert TOKEN_RE.match(verb), f"verb key is not a grammar token: {verb!r}"
    for mode in trigger_mode_registry()["modes"]:
        assert TOKEN_RE.match(mode), f"mode key is not a grammar token: {mode!r}"
    for mode in static_mode_registry()["static_modes"]:
        assert TOKEN_RE.match(mode)
    for mode in static_mode_registry()["ability_modes"]:
        assert TOKEN_RE.match(mode)
    blob = json.dumps(
        [verb_registry(), trigger_mode_registry(), static_mode_registry()],
        sort_keys=True,
    ).lower()
    assert "card_name" not in blob
    assert "lightning" not in blob and "gisela" not in blob


def test_verb_flags_come_from_closed_vocabulary():
    for verb, entry in verb_registry()["verbs"].items():
        assert entry["shape"], f"verb {verb} has no shape"
        for flag in entry["flags"]:
            assert flag in KNOWN_FLAGS, f"verb {verb} has unknown flag {flag!r}"


def test_before_census_verbs_all_registered():
    observed = {v for v, _ in BEFORE["parser_interpretation"]["observed_ability_verbs"]}
    registered = set(verb_registry()["verbs"])
    assert observed <= registered, f"unregistered census verbs: {sorted(observed - registered)}"


def test_before_census_modes_all_registered():
    observed_t = {v for v, _ in BEFORE["parser_interpretation"]["observed_trigger_modes"]}
    assert observed_t <= set(trigger_mode_registry()["modes"])
    valid_only = {v for v, _ in BEFORE["token_observation"]["valid_modes"]}
    assert valid_only <= set(trigger_mode_registry()["modes"])


def test_unknown_verb_is_first_class_answer():
    shape, flags = verb_shape("Frobnicate")
    assert shape is None
    assert flags == []


def test_known_verb_shape_and_flags():
    shape, flags = verb_shape("DamageAll")
    assert shape == "MASS_DAMAGE_SHAPE"
    assert flags == []
    shape, flags = verb_shape("Clone")
    assert shape == "COPY_CONTROL_SHAPE"
    assert "COPY_CONTROL" in flags
    shape, flags = verb_shape("Subgame")
    assert shape == "OTHER_STRUCTURED_SHAPE"
    assert "MANUAL_REVIEW" in flags


def test_trigger_mode_membership():
    assert is_known_trigger_mode("ChangesZone")
    assert is_known_trigger_mode("DamageDoneOnce")
    assert not is_known_trigger_mode("FrobnicateMode")


def test_static_and_ability_mode_classes():
    assert static_mode_class("S", "Continuous") == "STATIC_CONTINUOUS"
    assert static_mode_class("S", "AlternativeCost") == "STATIC_COST_CHOICE"
    assert static_mode_class("S", "CantBlock") == "STATIC_COMBAT"
    assert static_mode_class("S", "Frobnicate") is None
    assert ability_mode_class("TgtChoose") == "TARGETING_SELECTOR"
    assert ability_mode_class("SpellCast") == "TRIGGER_CONDITION"
    assert ability_mode_class("Frobnicate") is None


def test_unsupported_registry_entries_complete():
    doc = unsupported_registry()
    ids = [c["construct_id"] for c in doc["constructs"]]
    assert "UC-TOPKEY-MELDPAIR" in ids
    assert len(ids) == len(set(ids)), "construct IDs must be stable and unique"
    for entry in doc["constructs"]:
        assert entry["pattern"]
        assert entry["first_examples"]
        assert entry["mechanical_reason"]
        assert entry["owning_subsystem"]
        assert isinstance(entry["safely_scaffolding_implementable"], bool)
        assert isinstance(entry["rules_adjudication_required"], bool)
        assert isinstance(entry["runtime_qualification_required"], bool)


def test_registries_reload_deterministically():
    registries.verb_registry.cache_clear()
    try:
        first = verb_registry()["registry_version"]
        registries.verb_registry.cache_clear()
        second = verb_registry()["registry_version"]
        assert first == second
    finally:
        registries.verb_registry.cache_clear()


def test_gisela_stays_unsupported_without_generic_meld_support():
    with pytest.raises(ValueError, match="already registered"):
        from q6_scaffolding.classify import register_family

        register_family("COPY_CONTROL", "duplicate", "test")
