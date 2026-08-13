from __future__ import annotations

from collections import Counter


def count_and_availability_issues(mainboard, cards):
    issues = []
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
