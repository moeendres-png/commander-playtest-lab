from __future__ import annotations

from collections.abc import Mapping, Sequence

from .mana import BASIC_LANDS
from .search_context import SearchCard
from .search_models import ManaBasePolicy


def land_gate_values(
    mainboard: Sequence[str],
    cards: Mapping[str, SearchCard],
    mana_policy: ManaBasePolicy,
) -> tuple[int, int, tuple[str, ...]]:
    land_count = sum(cards[name].profile.is_land for name in mainboard if name in cards)
    basic_count = sum(name in BASIC_LANDS for name in mainboard)
    issues: list[str] = []
    if land_count < mana_policy.hard_land_minimum or land_count > mana_policy.hard_land_maximum:
        issues.append(
            f"whole_deck_land_hard_gate:{land_count}:"
            f"{mana_policy.hard_land_minimum}-{mana_policy.hard_land_maximum}"
        )
    return land_count, basic_count, tuple(issues)
