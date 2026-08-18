from __future__ import annotations

from collections.abc import Iterable

from commander_lab.models import Deck, StructuralDeckProfile

from .profiles import (
    build_structural_deck_profile as _legacy_build,
    StructuralProfileCatalog,
)

_KORVOLD = "Korvold, Fae-Cursed King"
_ROGSHAI = frozenset({"Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"})


def commander_strategy(commanders: Iterable[str]) -> str:
    """Resolve only explicitly known own-deck strategies; otherwise stay generic.

    The project may gain arbitrary Commander decks over time. Unknown commander identities must
    never inherit RogShai or historical Korvold policy merely because they are not the other one.
    """

    names = frozenset(commanders)
    if _KORVOLD in names:
        return "korvold"
    if _ROGSHAI.issubset(names):
        return "rogshai"
    return "generic"


def build_project_structural_deck_profile(
    deck: Deck,
    profiles: StructuralProfileCatalog,
    *,
    data_snapshot_hash: str,
) -> StructuralDeckProfile:
    """Build a structural profile and correct legacy two-deck strategy fallthrough.

    The underlying builder remains unchanged for card/profile construction. Strategy selection is
    normalized at this project boundary so new decks can enter through manifests/fixtures without
    silently becoming RogShai.
    """

    profile = _legacy_build(deck, profiles, data_snapshot_hash=data_snapshot_hash)
    return profile.model_copy(
        update={"commander_strategy": commander_strategy(profile.commander_names)}
    )


__all__ = ["build_project_structural_deck_profile", "commander_strategy"]
