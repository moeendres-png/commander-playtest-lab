from __future__ import annotations

import re
from collections.abc import Mapping

from commander_lab.models import Color, StructuralCardProfile
from commander_lab.models.roles import CardRole

FACT_FIDELITY_VERSION = "structural-card-facts-2026-08-21-v1"
_PERMANENT_TYPES = frozenset({"Artifact", "Battle", "Creature", "Enchantment", "Land", "Planeswalker"})
_SIMPLE_COLOR_SYMBOL = re.compile(r"\{([WUBRG])\}")


def permanent_from_type_line(type_line: str) -> bool:
    """Derive card permanency from current type-line facts, not name exceptions."""

    card_types = set(type_line.replace("—", " ").replace("//", " ").split())
    return bool(card_types & _PERMANENT_TYPES)


def creature_from_type_line(type_line: str) -> bool:
    return "Creature" in type_line.replace("—", " ").replace("//", " ").split()


def simple_color_requirements(mana_cost: str | None) -> dict[Color, int]:
    """Count only unambiguous W/U/B/R/G pips.

    Hybrid, Phyrexian, variable and alternative costs are intentionally not collapsed into
    false exact requirements. Their decision use is handled by the mechanics-fidelity gate.
    """

    if not mana_cost:
        return {}
    counts: dict[Color, int] = {}
    for symbol in _SIMPLE_COLOR_SYMBOL.findall(mana_cost.upper()):
        color = Color(symbol)
        counts[color] = counts.get(color, 0) + 1
    return counts


def apply_current_card_facts(
    profile: StructuralCardProfile,
    facts: Mapping[str, object] | None,
) -> StructuralCardProfile:
    """Overlay deterministic current Oracle facts onto a legacy Structural profile."""

    if not facts:
        return profile
    type_line = str(facts.get("type_line") or facts.get("card_type") or "").strip()
    mana_cost_raw = facts.get("mana_cost")
    mana_cost = str(mana_cost_raw) if isinstance(mana_cost_raw, str) else None
    updates: dict[str, object] = {}
    if type_line:
        derived_permanent = permanent_from_type_line(type_line)
        derived_creature = creature_from_type_line(type_line)
        updates["is_permanent"] = derived_permanent
        updates["is_creature"] = derived_creature
        derived_land = "Land" in type_line.replace("—", " ").replace("//", " ").split()
        if derived_land:
            roles = set(profile.roles)
            roles.add(CardRole.MANA_SOURCE)
            strengths = dict(profile.role_strengths)
            strengths.setdefault(CardRole.MANA_SOURCE, 1.0)
            updates["roles"] = frozenset(roles)
            updates["role_strengths"] = strengths
            updates["is_land"] = True
    if mana_cost is not None:
        updates["color_requirements"] = simple_color_requirements(mana_cost)

    # Silence is a timing restriction, never a counterspell. Leaving it as CardRole.COUNTER
    # allows the legacy resolver to remove an already-cast spell from the stack illegally.
    if profile.oracle_name == "Silence" and CardRole.COUNTER in profile.roles:
        roles = set(cast_roles(updates.get("roles", profile.roles)))
        roles.discard(CardRole.COUNTER)
        strengths = dict(profile.role_strengths)
        strengths.pop(CardRole.COUNTER, None)
        updates["roles"] = frozenset(roles)
        updates["role_strengths"] = strengths

    if not updates:
        return profile
    note = profile.notes or ""
    suffix = f"fact_fidelity={FACT_FIDELITY_VERSION}"
    updates["notes"] = f"{note} | {suffix}" if note else suffix
    return profile.model_copy(update=updates)


def cast_roles(value: object) -> frozenset[CardRole]:
    if isinstance(value, frozenset):
        return frozenset(role for role in value if isinstance(role, CardRole))
    if isinstance(value, set):
        return frozenset(role for role in value if isinstance(role, CardRole))
    return frozenset()
