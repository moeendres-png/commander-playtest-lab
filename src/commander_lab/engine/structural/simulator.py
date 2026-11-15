"""Structural engine constants and commander-rule helpers.

The role-level match simulator itself was removed; the helpers and the engine version stay.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

ENGINE_VERSION = "structural-0.6.1"


@dataclass(frozen=True)
class StructuralTuning:
    """Global damage scales of the Structural model (#733).

    The defaults are the model's long-standing constants. They exist as one object so the
    model can be measured and fitted against XMage full games
    (``engine/structural/xmage_calibration.py``) instead of being edited by guesswork.
    """

    creature_attack: float = 0.62
    token_attack: float = 0.35
    creature_blocking: float = 0.35
    token_blocking: float = 0.25
    finisher_damage: float = 1.0
    payoff_damage: float = 0.45
    cast_trigger_damage: float = 1.0
    token_creation: float = 0.8

    def as_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in self.__dataclass_fields__}


DEFAULT_TUNING = StructuralTuning()


def commander_cast_cost(base_cost: float, prior_casts: int) -> int:
    """Return structural commander cost including two generic mana per prior cast."""
    if base_cost < 0 or prior_casts < 0:
        raise ValueError("base_cost and prior_casts must be non-negative")
    return math.ceil(base_cost + 2 * prior_casts)


def commander_damage_is_lethal(
    damage_received: dict[str, float] | Iterable[float],
    *,
    threshold: float = 21.0,
) -> bool:
    """Return whether one commander has individually reached the lethal threshold."""
    values = damage_received.values() if isinstance(damage_received, dict) else damage_received
    return any(float(value) >= threshold for value in values)
