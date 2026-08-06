from pathlib import Path

import pytest

from commander_lab.models import (
    ArchetypeName,
    ExtractionMethod,
    FormatBand,
    PackageAblationInput,
    PackageDefinition,
    PackageRegistry,
    PackageStatus,
)
from commander_lab.packages import ArchetypePackageExtractor, PackageExtractionError
from commander_lab.tools import CommanderToolService, ToolRegistry

ROOT = Path(__file__).resolve().parents[2]


def extractor() -> ArchetypePackageExtractor:
    return ArchetypePackageExtractor(ROOT)


def test_archetype_weights_are_multi_axis_and_normalized() -> None:
    for deck_id in ("korvold/current", "rogshai/current"):
        profile = extractor().extract_archetypes(deck_id)
        assert len(profile.weights) >= 4
        assert sum(item.weight for item in profile.weights) == pytest.approx(1.0)
        assert profile.automatic_deck_application is False


def test_curated_and_machine_extracted_statuses_are_separate() -> None:
    result = extractor().packages_for_deck("korvold/current")
    assert result["curated_packages"]
    assert all(item["status"] in {"curated", "validated"} for item in result["curated_packages"])
    assert all(item["status"] == "machine_extracted" for item in result["machine_candidates"])
    assert result["machine_candidates_are_confirmed"] is False
    assert result["automatic_deck_application"] is False


def test_identical_card_can_have_different_roles_in_distinct_packages() -> None:
    shared = "Boros Charm"
    a = PackageDefinition(
        package_id="test-protection", version="1.0.0", name="Protection", commander="Test",
        archetype=ArchetypeName.CONTROL, core_cards=(shared,), minimum_density=1, redundancy=1,
        enablers=(shared,), source_ids=("test",), confidence=0.8, format_band=FormatBand.LOCAL_META,
        status=PackageStatus.CURATED, extraction_methods=(ExtractionMethod.MANUAL_CURRATION,),
    )
    b = PackageDefinition(
        package_id="test-finisher", version="1.0.0", name="Finisher", commander="Test",
        archetype=ArchetypeName.VOLTRON, core_cards=(shared,), minimum_density=1, redundancy=1,
        finishers=(shared,), source_ids=("test",), confidence=0.8, format_band=FormatBand.LOCAL_META,
        status=PackageStatus.CURATED, extraction_methods=(ExtractionMethod.MANUAL_CURRATION,),
    )
    registry = PackageRegistry(generated_at="2026-08-06", packages=(a, b))
    assert registry.latest("test-protection").enablers == (shared,)
    assert registry.latest("test-finisher").finishers == (shared,)


def test_incomplete_package_and_minimum_density_are_reported() -> None:
    result = extractor().evaluate("korvold/current", "korvold-graveyard-protection")
    assert result.minimum_density >= 1
    assert isinstance(result.minimum_density_met, bool)
    assert result.package_completeness <= 1.0
    assert result.warnings  # sample and/or deck-scope warning remains explicit


def test_redundant_payoffs_are_counted_without_isolated_card_claim() -> None:
    result = extractor().evaluate("rogshai/current", "rogshai-commander-damage")
    assert result.redundancy_present >= 2
    assert result.redundancy_met is True
    assert "Ishai, Ojutai Dragonspeaker" in result.present_cards


def test_false_cooccurrence_never_becomes_curated() -> None:
    result = extractor().packages_for_deck("rogshai/current")
    assert result["machine_candidates"] == []
    assert result["machine_rejections"]
    assert all(row["sample_size"] < 3 for row in result["machine_rejections"])
    assert all("same-format" in row["reason"] for row in result["machine_rejections"])


def test_package_version_comparison_is_explicit() -> None:
    comparison = extractor().compare_versions(
        "korvold-land-sacrifice-recursion", "1.0.0", "1.1.0"
    )
    assert comparison.added_core_cards == ("Aftermath Analyst",)
    assert comparison.minimum_density_delta == 1


def test_deck_version_mismatch_is_warned() -> None:
    x = extractor()
    original = x.decks["korvold/current"]
    x.decks["korvold/wrong-hash"] = original.model_copy(update={"deck_id": "korvold/wrong-hash", "deck_hash": "0" * 64})
    result = x.evaluate("korvold/wrong-hash", "korvold-land-sacrifice-recursion")
    assert "deck version is outside curated supported_deck_hashes" in result.warnings


def test_korvold_and_rogshai_packages_cannot_mix() -> None:
    with pytest.raises(PackageExtractionError, match="commander mismatch"):
        extractor().evaluate("rogshai/current", "korvold-independent-finishers")


def test_orphaned_support_and_payoff_without_enabler_are_detected() -> None:
    x = extractor()
    package = PackageDefinition(
        package_id="orphan-test", version="1.0.0", name="Orphan test",
        commander="Korvold, Fae-Cursed King", archetype=ArchetypeName.SACRIFICE,
        core_cards=("Ophiomancer",), support_cards=("Tireless Tracker",),
        optional_cards=("Nonexistent Payoff", "Nonexistent Enabler"), minimum_density=1,
        redundancy=1, enablers=("Nonexistent Enabler",), payoffs=("Nonexistent Payoff",),
        source_ids=("test",), confidence=0.5, format_band=FormatBand.LOCAL_META,
        status=PackageStatus.CURATED, extraction_methods=(ExtractionMethod.MANUAL_CURRATION,),
        supported_deck_hashes=(x.decks["korvold/current"].deck_hash,),
    )
    x.registry = PackageRegistry(generated_at="2026-08-06", packages=(package,))
    result = x.detect_orphans("korvold/current")
    assert result["orphaned_support_cards"] == ["Tireless Tracker"]
    assert result["automatic_deck_application"] is False


def test_existing_package_ablation_tool_accepts_registry_package_id() -> None:
    request = PackageAblationInput(
        deck_id="korvold/current", package_id="korvold-mirkwood-table-damage",
        iterations=1, seed=20260806, max_turns=8,
    )
    result = CommanderToolService(ROOT).run_package_ablation(request)
    assert result.status.value == "completed"
    assert result.result["package_id"] == "korvold-mirkwood-table-damage"
    assert result.result["automatic_deck_application"] is False


def test_all_package_tools_are_invokable() -> None:
    registry = ToolRegistry(CommanderToolService(ROOT))
    archetypes = registry.invoke("extract_archetypes", {"deck_id": "korvold/current"})
    packages = registry.invoke("extract_packages", {"deck_id": "rogshai/current"})
    density = registry.invoke("evaluate_package_density", {
        "deck_id": "rogshai/current", "package_id": "rogshai-combat-draw"
    })
    inspect = registry.invoke("inspect_package", {"package_id": "rogshai-combat-draw"})
    compare = registry.invoke("compare_package_versions", {
        "package_id": "korvold-land-sacrifice-recursion",
        "older_version": "1.0.0", "newer_version": "1.1.0",
    })
    orphans = registry.invoke("detect_orphaned_cards", {"deck_id": "korvold/current"})
    report = registry.invoke("generate_package_report", {
        "deck_id": "korvold/current", "output_name": "phase12_4_test_report.md"
    })
    assert all(item.status.value == "completed" for item in (archetypes, packages, density, inspect, compare, orphans, report))


def test_package_membership_is_attached_to_structural_cards() -> None:
    from commander_lab.engine.structural import load_project_structural_decks
    decks = load_project_structural_decks(ROOT)
    provisioner = next(card for card in decks["korvold/current"].cards if card.oracle_name == "Tireless Provisioner")
    assert "korvold-treasure-clue-food" in provisioner.package_ids
    curiosity = next(card for card in decks["rogshai/current"].cards if card.oracle_name == "Curiosity")
    assert "rogshai-combat-draw" in curiosity.package_ids


def test_package_membership_influences_specialized_pilot_score() -> None:
    from commander_lab.agents.pilots import build_pilot
    from commander_lab.models import PilotActionView, PilotConfig, PilotStateView, PilotStrength
    state = PilotStateView(
        player_id="p1", deck_id="rogshai/current", strategy="rogshai", turn=5, pod_size=4,
        life=30, hand_size=5, mana_available=5, lands=4, ramp_mana=1, resources=1,
        tokens=0, board_power=1, engine_value=0, graveyard_size=3,
        battlefield_names=(), hand_names=(), role_counts={}, commanders=(), opponents=(),
    )
    base = dict(
        action_kind="card", card_name="Whirlwind of Thought", mana_cost=4,
        roles=frozenset(), role_strengths={}, floor_value=.8, immediate_impact=.6,
        remaining_mana=1,
    )
    without = PilotActionView(action_id="without", metadata={}, **base)
    with_package = PilotActionView(
        action_id="with", metadata={"package_ids": "rogshai-independent-spellslinger"}, **base
    )
    pilot = build_pilot(
        PilotConfig(pilot_name="RogShaiSpellslingerPilot", strength=PilotStrength.STRONG),
        strategy="rogshai",
    )
    assert pilot.evaluate_action(state, with_package).total_utility > pilot.evaluate_action(state, without).total_utility


def test_deck_inspection_and_meta_comparison_include_package_diagnostics() -> None:
    from commander_lab.models import InspectDeckInput, CompareDeckToMetaInput
    service = CommanderToolService(ROOT)
    inspect = service.inspect_deck(InspectDeckInput(deck_id="korvold/current"))
    assert inspect.result["package_diagnostics"]["automatic_deck_application"] is False
    compare = service.compare_deck_to_meta(CompareDeckToMetaInput(
        deck_id="korvold/current", commander="Korvold, Fae-Cursed King"
    ))
    assert "local_package_evaluations" in compare.result
    assert compare.result["automatic_deck_application"] is False
