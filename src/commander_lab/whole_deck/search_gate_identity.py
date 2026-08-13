from __future__ import annotations

from collections.abc import Mapping, Sequence

from .search_context import SearchCard


def identity_issues(
    mainboard: Sequence[str],
    cards: Mapping[str, SearchCard],
    commanders: Sequence[str],
) -> tuple[str, ...]:
    issues: list[str] = []
    commander_set = set(commanders)
    if any(name in commander_set for name in mainboard):
        issues.append("commander_in_mainboard")
    for name in set(mainboard):
        card = cards.get(name)
        if card is not None and not card.color_identity <= {"W", "U", "R"}:
            issues.append(f"color_identity:{name}")
    for name in commanders:
        card = cards.get(name)
        if card is None or card.available_quantity < 1:
            issues.append(f"commander_unavailable:{name}")
    return tuple(issues)
