from pathlib import Path

from commander_lab.models import (
    ArchetypeName,
    ExtractionMethod,
    FormatBand,
    PackageDefinition,
    PackageRegistry,
    PackageStatus,
)

ROOT = Path(__file__).resolve().parents[2]


def test_identical_card_can_have_different_roles_in_distinct_packages() -> None:
    shared = "Boros Charm"
    a = PackageDefinition(
        package_id="test-protection",
        version="1.0.0",
        name="Protection",
        commander="Test",
        archetype=ArchetypeName.CONTROL,
        core_cards=(shared,),
        minimum_density=1,
        redundancy=1,
        enablers=(shared,),
        source_ids=("test",),
        confidence=0.8,
        format_band=FormatBand.LOCAL_META,
        status=PackageStatus.CURATED,
        extraction_methods=(ExtractionMethod.MANUAL_CURRATION,),
    )
    b = PackageDefinition(
        package_id="test-finisher",
        version="1.0.0",
        name="Finisher",
        commander="Test",
        archetype=ArchetypeName.VOLTRON,
        core_cards=(shared,),
        minimum_density=1,
        redundancy=1,
        finishers=(shared,),
        source_ids=("test",),
        confidence=0.8,
        format_band=FormatBand.LOCAL_META,
        status=PackageStatus.CURATED,
        extraction_methods=(ExtractionMethod.MANUAL_CURRATION,),
    )
    registry = PackageRegistry(generated_at="2026-08-06", packages=(a, b))
    assert registry.latest("test-protection").enablers == (shared,)
    assert registry.latest("test-finisher").finishers == (shared,)


def test_package_membership_is_attached_to_structural_cards() -> None:
    from commander_lab.engine.structural import load_project_structural_decks

    decks = load_project_structural_decks(ROOT)
    spellslinger = next(
        card
        for card in decks["rogshai/current"].cards
        if card.oracle_name == "Whirlwind of Thought"
    )
    assert "rogshai-independent-spellslinger" in spellslinger.package_ids
    assert "rogshai-combat-draw" not in spellslinger.package_ids


def test_package_membership_influences_specialized_pilot_score() -> None:
    from commander_lab.agents.pilots import build_pilot
    from commander_lab.models import PilotActionView, PilotConfig, PilotStateView, PilotStrength

    state = PilotStateView(
        player_id="p1",
        deck_id="rogshai/current",
        strategy="rogshai",
        turn=5,
        pod_size=4,
        life=30,
        hand_size=5,
        mana_available=5,
        lands=4,
        ramp_mana=1,
        resources=1,
        tokens=0,
        board_power=1,
        engine_value=0,
        graveyard_size=3,
        battlefield_names=(),
        hand_names=(),
        role_counts={},
        commanders=(),
        opponents=(),
    )
    base = dict(
        action_kind="card",
        card_name="Whirlwind of Thought",
        mana_cost=4,
        roles=frozenset(),
        role_strengths={},
        floor_value=0.8,
        immediate_impact=0.6,
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
    assert (
        pilot.evaluate_action(state, with_package).total_utility
        > pilot.evaluate_action(state, without).total_utility
    )
