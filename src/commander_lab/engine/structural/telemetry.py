from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

from commander_lab.models import CardRole, Color, StructuralCardProfile

T1TelemetryStatus = Literal["NOT_MEASURED", "PARTIAL", "MEASURED"]
PaymentBlocker = Literal["insufficient_total_mana", "missing_color"]

_REACTION_ONLY_ROLES = frozenset({CardRole.COUNTER, CardRole.PROTECTION})


@dataclass(slots=True)
class T1TelemetryAccumulator:
    """Read-only counters for decision-relevant Structural telemetry.

    These counters observe the state already used by Structural action legality. They never feed
    pilot choice, scoring, search, promotion, or holdout logic.
    """

    decision_windows: int = 0
    unused_mana: float = 0.0
    colored_mana_failures: int = 0
    stranded_spells: int = 0
    stranded_reasons: Counter[str] = field(default_factory=Counter)
    commander_recast_opportunities: dict[str, int] = field(default_factory=dict)
    commander_recast_affordable: dict[str, int] = field(default_factory=dict)

    def record_recast(self, commander_name: str, *, affordable: bool) -> None:
        self.commander_recast_opportunities[commander_name] = (
            self.commander_recast_opportunities.get(commander_name, 0) + 1
        )
        if affordable:
            self.commander_recast_affordable[commander_name] = (
                self.commander_recast_affordable.get(commander_name, 0) + 1
            )

    def recast_affordability(self) -> float | None:
        """Return pooled affordability after evaluating every commander independently."""

        opportunities = sum(self.commander_recast_opportunities.values())
        if opportunities == 0:
            return None
        return sum(self.commander_recast_affordable.values()) / opportunities


def is_structural_reaction_only(card: StructuralCardProfile) -> bool:
    """Return whether Structural deliberately withholds this spell from proactive main actions."""

    return bool(not card.is_permanent and card.roles and card.roles.issubset(_REACTION_ONLY_ROLES))


def classify_payment_blocker(
    *,
    mana_available: float,
    available_colors: set[Color],
    card: StructuralCardProfile,
) -> PaymentBlocker | None:
    """Classify only payment blockers the current Structural state can actually observe.

    Color fidelity is intentionally presence-only because the current Structural payer checks
    whether each required color is available, not exact colored-pip source quantities. The caller
    must therefore report T1 as PARTIAL rather than rules-complete telemetry.
    """

    if mana_available + 1e-9 < card.mana_value:
        return "insufficient_total_mana"
    if any(color not in available_colors for color in card.color_requirements):
        return "missing_color"
    return None
