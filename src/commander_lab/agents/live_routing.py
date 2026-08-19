from __future__ import annotations

from commander_lab.models import PilotConfig

from .pilots import BasePilot
from .pilots import auto_pilot_name as _legacy_auto_pilot_name
from .pilots import build_pilot as _legacy_build_pilot

_ROGSHAI_STRATEGIES = frozenset({"rogshai", "ishai_rograkh"})
_KAERVEK_STRATEGIES = frozenset({"kaervek", "punisher_control_reanimation"})
_GENERIC_ARCHETYPES = frozenset({"aggro", "control", "engine", "graveyard", "artifact"})
_RETIRED_KORVOLD_PILOTS = frozenset(
    {
        "korvoldpilot",
        "korvoldvaluepilot",
        "korvoldsacrificepilot",
        "korvoldlandrebuildpilot",
        "korvoldaggressivepilot",
        "korvoldconservativepilot",
    }
)
_ROGSHAI_PILOTS = frozenset(
    {
        "rogshaipilot",
        "rogshaitempopilot",
        "rogshaivoltronpilot",
        "rogshaispellslingerpilot",
        "rogshaicontrolpilot",
        "rogshaiprotectedfinishpilot",
    }
)


def strategy_family(strategy: str) -> str:
    """Resolve the live commander family without former-own-deck fallbacks."""

    normalized = strategy.casefold().strip()
    if normalized in _ROGSHAI_STRATEGIES:
        return "rogshai"
    if normalized in _KAERVEK_STRATEGIES:
        return "kaervek"
    if normalized in _GENERIC_ARCHETYPES:
        return normalized
    return "generic"


def pilot_family(pilot_name: str) -> str:
    normalized = pilot_name.casefold().strip()
    if normalized in _RETIRED_KORVOLD_PILOTS:
        return "retired_korvold"
    if normalized in _ROGSHAI_PILOTS:
        return "rogshai"
    if normalized == "kaervekopponentpilot":
        return "kaervek"
    if normalized == "genericcommanderpilot":
        return "generic"
    if normalized in {
        "aggropilot",
        "controlpilot",
        "enginepilot",
        "graveyardpilot",
        "artifactpilot",
    }:
        return normalized.removesuffix("pilot")
    return "unknown"


def auto_pilot_name(strategy: str) -> str:
    """Return the live automatic pilot for a structural strategy.

    Unknown strategies, including the retired former-own-deck Korvold strategy,
    resolve to the neutral GenericCommanderPilot instead of inheriting RogShai.
    """

    family = strategy_family(strategy)
    if family == "rogshai":
        return "RogShaiPilot"
    if family == "kaervek":
        return "KaervekOpponentPilot"
    if family in _GENERIC_ARCHETYPES:
        return _legacy_auto_pilot_name(family)
    return "GenericCommanderPilot"


def _validate_family(strategy: str, pilot_name: str) -> None:
    expected = strategy_family(strategy)
    actual = pilot_family(pilot_name)

    if actual == "retired_korvold":
        raise ValueError(
            f"retired former-own-deck pilot is not available for live routing: {pilot_name}"
        )

    if expected in {"rogshai", "kaervek", "generic"} and actual != expected:
        raise ValueError(
            f"pilot family mismatch: strategy={expected} pilot={pilot_name} family={actual}"
        )

    if expected in _GENERIC_ARCHETYPES and actual not in {expected, "generic"}:
        raise ValueError(
            f"pilot family mismatch: strategy={expected} pilot={pilot_name} family={actual}"
        )


def build_pilot(config: PilotConfig, *, strategy: str) -> BasePilot:
    """Build a live pilot with explicit commander-family compatibility checks."""

    requested = (
        auto_pilot_name(strategy)
        if config.pilot_name.casefold().strip() == "auto"
        else config.pilot_name
    )
    _validate_family(strategy, requested)
    resolved = config.model_copy(update={"pilot_name": requested})
    return _legacy_build_pilot(resolved, strategy=strategy)


__all__ = ["auto_pilot_name", "build_pilot", "pilot_family", "strategy_family"]
