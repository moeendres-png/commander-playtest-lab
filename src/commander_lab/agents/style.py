"""AI Pilot Style: continuous aggressive-to-control parameterization.

Governing mission: The AI always plays at full strength (NEAR_OPTIMAL_HEURISTIC).
A single style slider (0.0 = aggressive, 0.5 = balanced, 1.0 = control) shifts utility weights
and mana reservation behavior without creating fragmented special-case card rules.
"""

from __future__ import annotations

from typing import Final

from commander_lab.models import PilotStrength, PilotUtilityWeights

DEFAULT_STYLE: Final[float] = 0.5

# Anchor points for the style parameter s in [0.0, 1.0]:
# - 0.0: Aggressiv (early pressure, tempo, attacks, low reserve)
# - 0.5: Ausgeglichen (balanced / generic near-optimal weights)
# - 1.0: Kontrollierend (board safety, interaction reserve, threat reduction, late finish)
_STYLE_ANCHORS: Final[dict[float, dict[str, float]]] = {
    0.0: {
        "survival": 0.80,
        "mana_efficiency": 1.00,
        "card_advantage": 1.00,
        "tempo": 1.35,
        "engine_development": 1.00,
        "interaction_reserve": 0.50,
        "commander_value": 1.00,
        "threat_reduction": 0.80,
        "win_progress": 1.45,
        "political_visibility": -0.20,
        "rebuild_capacity": 1.00,
    },
    0.5: {
        "survival": 1.00,
        "mana_efficiency": 1.00,
        "card_advantage": 1.00,
        "tempo": 1.00,
        "engine_development": 1.00,
        "interaction_reserve": 1.00,
        "commander_value": 1.00,
        "threat_reduction": 1.00,
        "win_progress": 1.00,
        "political_visibility": -0.65,
        "rebuild_capacity": 1.00,
    },
    1.0: {
        "survival": 1.35,
        "mana_efficiency": 1.00,
        "card_advantage": 1.00,
        "tempo": 0.80,
        "engine_development": 1.00,
        "interaction_reserve": 1.50,
        "commander_value": 1.00,
        "threat_reduction": 1.35,
        "win_progress": 0.80,
        "political_visibility": -0.85,
        "rebuild_capacity": 1.00,
    },
}

_RESERVE_MANA_ANCHORS: Final[dict[float, float]] = {
    0.0: 0.0,
    0.5: 1.0,
    1.0: 2.0,
}


def clamp_style(style: float | None) -> float:
    """Clamp style to the valid interval [0.0, 1.0]. Defaults to 0.5."""
    if style is None:
        return DEFAULT_STYLE
    return max(0.0, min(1.0, float(style)))


def _interpolate(low_val: float, high_val: float, t: float) -> float:
    return low_val + (high_val - low_val) * t


def style_weights(
    style: float | None,
    base_strength: PilotStrength = PilotStrength.NEAR_OPTIMAL_HEURISTIC,
) -> PilotUtilityWeights:
    """Compute interpolated pilot utility weights for a given style in [0.0, 1.0]."""
    s = clamp_style(style)
    if s <= 0.5:
        t = s / 0.5
        w_low = _STYLE_ANCHORS[0.0]
        w_high = _STYLE_ANCHORS[0.5]
    else:
        t = (s - 0.5) / 0.5
        w_low = _STYLE_ANCHORS[0.5]
        w_high = _STYLE_ANCHORS[1.0]

    interpolated = {
        key: round(_interpolate(w_low[key], w_high[key], t), 4) for key in _STYLE_ANCHORS[0.5]
    }
    return PilotUtilityWeights(**interpolated)


def style_reserve_mana(style: float | None) -> float:
    """Target mana to hold open during opponents' turns based on style."""
    s = clamp_style(style)
    if s <= 0.5:
        t = s / 0.5
        return round(_interpolate(_RESERVE_MANA_ANCHORS[0.0], _RESERVE_MANA_ANCHORS[0.5], t), 2)
    t = (s - 0.5) / 0.5
    return round(_interpolate(_RESERVE_MANA_ANCHORS[0.5], _RESERVE_MANA_ANCHORS[1.0], t), 2)


def style_label(style: float | None) -> str:
    """Human-readable descriptor in German for the style value."""
    s = clamp_style(style)
    if s <= 0.20:
        return "Aggressiv"
    if s <= 0.40:
        return "Druckvoll"
    if s <= 0.60:
        return "Ausgeglichen"
    if s <= 0.80:
        return "Defensiv"
    return "Kontrollierend"
