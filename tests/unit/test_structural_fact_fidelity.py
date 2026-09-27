from __future__ import annotations

from commander_lab.engine.structural.fact_fidelity import (
    apply_current_card_facts,
    creature_from_type_line,
    permanent_from_type_line,
    simple_color_requirements,
)
from commander_lab.models import Color, StructuralCardProfile
from commander_lab.models.roles import CardRole


def _profile(name: str, *roles: CardRole) -> StructuralCardProfile:
    return StructuralCardProfile(
        oracle_name=name,
        roles=frozenset(roles),
        role_strengths={role: 1.0 for role in roles},
    )


def test_type_line_replaces_name_exception_permanency() -> None:
    assert permanent_from_type_line("Legendary Creature — Bird Monk")
    assert permanent_from_type_line("Artifact")
    assert not permanent_from_type_line("Instant")
    assert not permanent_from_type_line("Sorcery")
    assert creature_from_type_line("Artifact Creature — Construct")
    assert not creature_from_type_line("Enchantment")


def test_simple_mana_pips_preserve_multiplicity() -> None:
    assert simple_color_requirements("{1}{U}{U}{R}") == {
        Color.BLUE: 2,
        Color.RED: 1,
    }
    assert simple_color_requirements("{W/U}{2}{R/P}") == {}


def test_fact_overlay_makes_instant_nonpermanent() -> None:
    profile = _profile("Psychotic Fury", CardRole.COMBAT_PAYOFF)
    corrected = apply_current_card_facts(
        profile,
        {
            "type_line": "Instant",
            "mana_cost": "{1}{R}",
        },
    )
    assert not corrected.is_permanent
    assert not corrected.is_creature
    assert corrected.color_requirements == {Color.RED: 1}


def test_silence_can_no_longer_resolve_as_counterspell() -> None:
    profile = _profile("Silence", CardRole.COUNTER)
    corrected = apply_current_card_facts(
        profile,
        {
            "type_line": "Instant",
            "mana_cost": "{W}",
        },
    )
    assert CardRole.COUNTER not in corrected.roles
    assert CardRole.COUNTER not in corrected.role_strengths
    assert not corrected.is_permanent


def test_land_fact_enforces_mana_source_role() -> None:
    corrected = apply_current_card_facts(
        _profile("Test Land"),
        {"type_line": "Land", "mana_cost": None},
    )
    assert corrected.is_land
    assert corrected.is_permanent
    assert CardRole.MANA_SOURCE in corrected.roles
