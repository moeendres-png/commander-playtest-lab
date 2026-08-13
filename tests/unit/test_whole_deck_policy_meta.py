from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.engine.structural import load_project_structural_decks
from commander_lab.engine.structural.profiles import StructuralProfileCatalog
from commander_lab.meta.store import MetaKnowledgeBase
from commander_lab.models import FormatBand, StructuralCardProfile
from commander_lab.whole_deck import (
    FunctionalEvidenceQuality,
    PolicyId,
    build_meta_functional_profile,
    card_feature_vector,
    contextual_card_utility,
    functional_meta_distance,
    get_policy,
    policy_registry,
    profile_card_names,
    profile_structural_deck,
)

ROGSHAI = "Ishai, Ojutai Dragonspeaker / Rograkh, Son of Rohgahh"


def _profiles(repo_root: Path) -> dict[str, StructuralCardProfile]:
    catalog = StructuralProfileCatalog.from_json(
        repo_root / "data/cards/structural_role_profiles.json"
    )
    return {profile.oracle_name: profile for profile in catalog.profiles}


def test_policy_registry_contains_required_versioned_policies() -> None:
    registry = policy_registry()
    assert set(registry) == set(PolicyId)
    assert len({policy.policy_version for policy in registry.values()}) == 1
    assert all(policy.schema_version for policy in registry.values())


def test_feature_vector_is_deterministic(repo_root: Path) -> None:
    profile = _profiles(repo_root)["Counterspell"]
    first = card_feature_vector(profile)
    second = card_feature_vector(profile)
    assert first == second
    assert first.feature_hash == second.feature_hash


def test_card_utility_is_explicitly_non_empirical(repo_root: Path) -> None:
    profile = _profiles(repo_root)["Counterspell"]
    utility = contextual_card_utility(profile, get_policy(PolicyId.META_HIGH))
    assert utility.evidence_type == "search_heuristic_not_empirical_or_causal"
    assert "counter" in utility.components


def test_missing_profiles_fail_soft_with_evidence_marking(repo_root: Path) -> None:
    profiles = _profiles(repo_root)
    result = profile_card_names(
        ("Counterspell", "Definitely Missing Card"),
        profiles,
        format_band=FormatBand.HIGH_POWER,
        source_snapshot_id="test",
        profile_id="test:partial",
    )
    assert result.missing_profile_cards == ("Definitely Missing Card",)
    assert result.name_fallback_cards == ()
    assert result.profiled_card_count == 1
    assert all(
        row.evidence_quality == FunctionalEvidenceQuality.PARTIAL_STRUCTURAL
        for row in result.dimensions.values()
    )
    assert all(row.support_fraction == 0.5 for row in result.dimensions.values())


def test_name_fallback_is_opt_in_and_low_evidence(repo_root: Path) -> None:
    profiles = _profiles(repo_root)
    result = profile_card_names(
        ("Counterspell", "Imaginary Mox"),
        profiles,
        format_band=FormatBand.HIGH_POWER,
        source_snapshot_id="test",
        profile_id="test:fallback",
        allow_name_fallback=True,
    )
    assert result.name_fallback_cards == ("Imaginary Mox",)
    assert any(
        row.evidence_quality == FunctionalEvidenceQuality.MIXED
        for row in result.dimensions.values()
    )


def test_functional_meta_distance_is_deterministic_and_band_separated(repo_root: Path) -> None:
    decks = load_project_structural_decks(repo_root)
    deck = decks["rogshai/current"]
    candidate = profile_structural_deck(deck, format_band=FormatBand.HIGH_POWER)
    reference = profile_structural_deck(
        deck, format_band=FormatBand.HIGH_POWER, source_snapshot_id="reference"
    )
    policy = get_policy(PolicyId.META_HIGH)
    first = functional_meta_distance(candidate, reference, policy=policy)
    second = functional_meta_distance(candidate, reference, policy=policy)
    assert first == second
    assert first.raw_distance == 0.0
    assert first.policy_weighted_distance == 0.0

    wrong_band = profile_structural_deck(deck, format_band=FormatBand.CEDH_TOURNAMENT)
    with pytest.raises(ValueError, match="cannot collapse format bands"):
        functional_meta_distance(candidate, wrong_band, policy=policy)


def test_meta_high_weights_distance_more_than_meta_light(repo_root: Path) -> None:
    decks = load_project_structural_decks(repo_root)
    current = decks["rogshai/current"]
    candidate = profile_structural_deck(current, format_band=FormatBand.HIGH_POWER)
    cards = tuple(
        card.oracle_name for card in current.cards if card.oracle_name != "Counterspell"
    )
    profiles = {card.oracle_name: card for card in current.cards}
    reference = profile_card_names(
        cards,
        profiles,
        format_band=FormatBand.HIGH_POWER,
        source_snapshot_id="different",
        profile_id="different",
    )
    light = functional_meta_distance(candidate, reference, policy=get_policy(PolicyId.META_LIGHT))
    high = functional_meta_distance(candidate, reference, policy=get_policy(PolicyId.META_HIGH))
    assert light.raw_distance == high.raw_distance
    assert high.policy_weighted_distance is not None
    assert light.policy_weighted_distance is not None
    assert high.policy_weighted_distance > light.policy_weighted_distance


def test_neutral_policy_has_no_meta_nearness_bonus(repo_root: Path) -> None:
    deck = load_project_structural_decks(repo_root)["rogshai/current"]
    candidate = profile_structural_deck(deck, format_band=FormatBand.HIGH_POWER)
    reference = profile_structural_deck(
        deck, format_band=FormatBand.HIGH_POWER, source_snapshot_id="reference"
    )
    neutral = get_policy(PolicyId.OWNED_POOL_NEUTRAL)
    assert neutral.functional_meta_weight == 0.0
    assert neutral.meta_band_weights == {}
    distance = functional_meta_distance(candidate, reference, policy=neutral)
    assert distance.policy_weighted_distance == 0.0


def test_identical_deck_can_be_evaluated_under_multiple_policies(repo_root: Path) -> None:
    card = _profiles(repo_root)["Counterspell"]
    a = contextual_card_utility(card, get_policy(PolicyId.META_LIGHT))
    b = contextual_card_utility(card, get_policy(PolicyId.META_HIGH))
    assert a.oracle_name == b.oracle_name == "Counterspell"
    assert a.policy_id != b.policy_id


def test_current_meta_snapshot_bands_are_not_collapsed(repo_root: Path) -> None:
    kb = MetaKnowledgeBase(repo_root)
    snapshot = kb.load_snapshot()
    profiles = _profiles(repo_root)
    high = build_meta_functional_profile(
        snapshot,
        commander=ROGSHAI,
        format_band=FormatBand.HIGH_POWER,
        profiles=profiles,
    )
    cedh = build_meta_functional_profile(
        snapshot,
        commander=ROGSHAI,
        format_band=FormatBand.CEDH_TOURNAMENT,
        profiles=profiles,
    )
    assert high.format_band == FormatBand.HIGH_POWER
    assert cedh.format_band == FormatBand.CEDH_TOURNAMENT
    assert high.profile_hash != cedh.profile_hash


def test_feature_meta_layer_does_not_modify_canonical_deck_or_inventory(repo_root: Path) -> None:
    tracked = (
        repo_root / "data/decks/manifest.json",
        repo_root / "data/collections/current/J_P5_CURRENT_OPTIMIZATION_AVAILABILITY.json",
    )
    before = {path: path.read_bytes() for path in tracked}
    deck = load_project_structural_decks(repo_root)["rogshai/current"]
    profile_structural_deck(deck, format_band=FormatBand.LOCAL_META)
    after = {path: path.read_bytes() for path in tracked}
    assert before == after


def test_compact_current_snapshot_derives_card_frequencies(repo_root: Path) -> None:
    kb = MetaKnowledgeBase(repo_root)
    snapshot = kb.load_snapshot()
    assert snapshot.card_frequencies == ()
    result = kb.query_cards(commander=ROGSHAI, format_band=FormatBand.HIGH_POWER)
    assert result["cards"]
    assert all(row["format_band"] == FormatBand.HIGH_POWER for row in result["cards"])


def test_current_meta_snapshot_is_immutable_and_provenanced(repo_root: Path) -> None:
    pointer = json.loads(
        (repo_root / "data/meta/manifests/latest.json").read_text(encoding="utf-8")
    )
    payload = json.loads((repo_root / pointer["path"]).read_text(encoding="utf-8"))
    assert payload["manifest"]["immutable"] is True
    assert all(source["retrieved_at"] for source in payload["sources"])


def test_legacy_meta_role_proxy_is_explicitly_low_evidence(repo_root: Path) -> None:
    kb = MetaKnowledgeBase(repo_root)
    deck = load_project_structural_decks(repo_root)["rogshai/current"]
    result = kb.compare_deck_to_meta(
        tuple(card.oracle_name for card in deck.cards),
        commander=ROGSHAI,
        format_band=FormatBand.HIGH_POWER,
    )
    assert result["role_proxy_evidence_quality"] == "low_evidence_name_fallback"
    assert result["role_proxy_is_functional_meta_distance"] is False
