from __future__ import annotations

from commander_lab.models import (
    CardRole,
    Color,
    StructuralCardProfile,
)


def _spell(*, mana_value: float, colors: dict[Color, int]) -> StructuralCardProfile:
    return StructuralCardProfile(
        oracle_name="Telemetry Test Spell",
        mana_value=mana_value,
        roles=frozenset({CardRole.DRAW}),
        color_requirements=colors,
        is_permanent=False,
    )
