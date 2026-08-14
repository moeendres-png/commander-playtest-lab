from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from .search_context import SearchCard


def count_and_availability_issues(
    mainboard: Sequence[str], cards: Mapping[str, SearchCard]
) -> tuple[str, ...]:
    issues: list[str] = []
    if len(mainboard) != 98:
        issues.append(f"mainboard_card_count:{len(mainboard)}")
    for name, quantity in Counter(mainboard).items():
        card = cards.get(name)
        if card is None:
            issues.append(f"outside_candidate_pool:{name}")
            continue
        if not card.is_basic and quantity > 1:
            issues.append(f"singleton:{name}:{quantity}")
        if quantity > card.available_quantity:
            issues.append(f"physical_inventory:{name}:{quantity}>{card.available_quantity}")
    return tuple(issues)
