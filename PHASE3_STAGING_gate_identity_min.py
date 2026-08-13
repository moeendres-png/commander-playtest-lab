from __future__ import annotations


def identity_issues(mainboard, cards, commanders):
    issues = []
    if any(name in commanders for name in mainboard):
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
