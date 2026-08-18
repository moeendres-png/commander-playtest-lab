from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.canonical_features import (
    CanonicalFeatureError,
    load_canonical_feature_annotations,
)
from commander_lab.candidate_screening import CandidateScreener
from commander_lab.deck_registry import DeckPolicyRegistry
from commander_lab.models import Color
from commander_lab.repositories.candidates import (
    load_candidate_profiles,
    load_current_candidate_eligibility,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_project(root: Path) -> tuple[Path, ...]:
    scope = root / "data/current/active.json"
    manifest = root / "data/current/decks.json"
    inventory = root / "data/current/inventory.json"
    eligibility = root / "data/current/eligibility.json"
    availability = root / "data/current/availability.json"
    release = root / "data/current/releases.json"
    opponents = root / "data/current/opponents.json"
    alpha_features = root / "data/current/alpha_features/manifest.json"
    beta_features = root / "data/current/beta_features/manifest.json"

    _write_json(
        scope,
        {
            "active_own_decks": ["fixture/alpha", "fixture/beta"],
            "historical_own_decks": ["fixture/history"],
            "primary_deckbuilding_focus": "fixture/alpha",
            "frozen_opponent_only_decks": ["fixture/opponent"],
        },
    )
    _write_json(
        manifest,
        {
            # Deliberately misleading historical/global field: live activation must ignore it.
            "global_active_own_decks": ["rogshai/current"],
            "decks": {
                "fixture/alpha": {
                    "deck_hash": "a" * 64,
                    "commanders": ["Alpha Commander"],
                    "validation": {"metrics": {"commander_identity": ["W"]}},
                },
                "fixture/beta": {
                    "deck_hash": "b" * 64,
                    "commanders": ["Beta Commander"],
                    "validation": {"metrics": {"commander_identity": ["U"]}},
                },
            },
        },
    )
    _write_json(
        inventory,
        {
            "cards": [
                {
                    "oracle_name": "White Insight",
                    "quantity": 1,
                    "currently_owned": True,
                    "commander_legality": "legal",
                    "color_identity": "W",
                    "card_type": "Instant",
                    "mana_cost": "{W}",
                    "mana_value": 1,
                    "oracle_text": "Draw a card.",
                },
                {
                    "oracle_name": "Blue Denial",
                    "quantity": 1,
                    "currently_owned": True,
                    "commander_legality": "legal",
                    "color_identity": "U",
                    "card_type": "Instant",
                    "mana_cost": "{U}",
                    "mana_value": 1,
                    "oracle_text": "Counter target spell.",
                },
                {
                    "oracle_name": "Historical Only",
                    "quantity": 1,
                    "currently_owned": True,
                    "commander_legality": "legal",
                    "color_identity": "B",
                    "card_type": "Instant",
                    "mana_cost": "{B}",
                    "mana_value": 1,
                    "oracle_text": "Draw a card.",
                },
            ]
        },
    )
    _write_json(
        eligibility,
        {
            "eligible_by_deck": {
                "fixture/alpha": {
                    "White Insight": {
                        "commander_legal": True,
                        "physical_available_quantity": 1,
                    }
                },
                "fixture/beta": {
                    "Blue Denial": {
                        "commander_legal": True,
                        "physical_available_quantity": 1,
                    }
                },
                "fixture/history": {
                    "Historical Only": {
                        "commander_legal": True,
                        "physical_available_quantity": 1,
                    }
                },
            }
        },
    )
    _write_json(availability, {"cards": {"White Insight": 1, "Blue Denial": 1}})
    _write_json(
        release,
        {
            "active_own_decks": ["fixture/alpha", "fixture/beta"],
            "inactive_former_own_decks": ["fixture/history"],
            "released_allocations": {},
        },
    )
    _write_json(opponents, {"scenarios": []})

    _write_json(
        alpha_features,
        {
            "deck_id": "fixture/alpha",
            "canonical_candidate_count": 1,
            "materialized_role_or_package_rows": 1,
            "parts": ["part.json"],
        },
    )
    _write_json(
        alpha_features.parent / "part.json",
        [["White Insight", ["card_draw"], ["package:alpha:draw"]]],
    )
    _write_json(
        beta_features,
        {
            "deck_id": "fixture/beta",
            "canonical_candidate_count": 1,
            "materialized_role_or_package_rows": 1,
            "parts": ["part.json"],
        },
    )
    _write_json(
        beta_features.parent / "part.json",
        [["Blue Denial", ["counterspell"], ["package:beta:counter"]]],
    )

    _write_json(
        root / "config/deck_decision_registry.json",
        {
            "schema_version": "1.0.0",
            "sources": {
                "active_scope": "data/current/active.json",
                "deck_manifest": "data/current/decks.json",
                "inventory_snapshot": "data/current/inventory.json",
                "candidate_eligibility": "data/current/eligibility.json",
                "optimization_availability": "data/current/availability.json",
                "inactive_release_delta": "data/current/releases.json",
                "opponent_context": "data/current/opponents.json",
            },
            "deck_policies": {
                "fixture/alpha": {
                    "feature_projection_manifest": "data/current/alpha_features/manifest.json",
                    "package_prefixes": ["package:alpha:"],
                },
                "fixture/beta": {
                    "feature_projection_manifest": "data/current/beta_features/manifest.json",
                    "package_prefixes": ["package:beta:"],
                },
            },
        },
    )
    return (scope, manifest, inventory, eligibility, availability, release, opponents)


def test_registry_uses_live_scope_and_manifest_metadata(tmp_path: Path) -> None:
    _fixture_project(tmp_path)
    registry = DeckPolicyRegistry(tmp_path)

    assert registry.active_deck_ids == ("fixture/alpha", "fixture/beta")
    assert registry.primary_deck_id == "fixture/alpha"
    assert registry.historical_deck_ids == ("fixture/history",)
    assert registry.frozen_opponent_ids == frozenset({"fixture/opponent"})
    assert registry.commander_identity("fixture/alpha") == frozenset({Color.WHITE})
    assert registry.commander_identity("fixture/beta") == frozenset({Color.BLUE})
    with pytest.raises(ValueError, match="not an active own-deck"):
        registry.assert_active("rogshai/current")


def test_candidate_eligibility_ignores_historical_rows(tmp_path: Path) -> None:
    _fixture_project(tmp_path)
    eligibility = load_current_candidate_eligibility(tmp_path)

    assert eligibility == {
        "fixture/alpha": {"White Insight"},
        "fixture/beta": {"Blue Denial"},
    }


def test_feature_projection_is_deck_scoped_and_prefix_guarded(tmp_path: Path) -> None:
    _fixture_project(tmp_path)
    registry = DeckPolicyRegistry(tmp_path)

    alpha = load_canonical_feature_annotations(
        tmp_path, deck_id="fixture/alpha", registry=registry
    )
    beta = load_canonical_feature_annotations(
        tmp_path, deck_id="fixture/beta", registry=registry
    )

    assert alpha["White Insight"].package_ids == frozenset({"package:alpha:draw"})
    assert beta["Blue Denial"].package_ids == frozenset({"package:beta:counter"})
    assert "Blue Denial" not in alpha
    assert "White Insight" not in beta

    _write_json(
        tmp_path / "data/current/alpha_features/part.json",
        [["White Insight", ["card_draw"], ["package:beta:leak"]]],
    )
    with pytest.raises(CanonicalFeatureError, match="escape configured deck policy"):
        load_canonical_feature_annotations(
            tmp_path, deck_id="fixture/alpha", registry=registry
        )


def test_candidate_profiles_and_screening_do_not_leak_between_decks(tmp_path: Path) -> None:
    tracked = _fixture_project(tmp_path)
    before = {path: path.read_bytes() for path in tracked}

    profiles = load_candidate_profiles(tmp_path)
    alpha_profiles = [
        candidate
        for candidate in profiles.values()
        if candidate.allowed_deck_ids == ("fixture/alpha",)
    ]
    beta_profiles = [
        candidate
        for candidate in profiles.values()
        if candidate.allowed_deck_ids == ("fixture/beta",)
    ]

    assert [row.card.oracle_name for row in alpha_profiles] == ["White Insight"]
    assert [row.card.oracle_name for row in beta_profiles] == ["Blue Denial"]
    assert alpha_profiles[0].card.package_ids == frozenset({"package:alpha:draw"})
    assert beta_profiles[0].card.package_ids == frozenset({"package:beta:counter"})

    alpha_screen = CandidateScreener(tmp_path, service=object()).screen_pool("fixture/alpha")
    beta_screen = CandidateScreener(tmp_path, service=object()).screen_pool("fixture/beta")
    assert [row["oracle_name"] for row in alpha_screen["rows"]] == ["White Insight"]
    assert [row["oracle_name"] for row in beta_screen["rows"]] == ["Blue Denial"]

    after = {path: path.read_bytes() for path in tracked}
    assert before == after
