from __future__ import annotations

from .mana import BASIC_LANDS


def land_gate_values(mainboard, cards, mana_policy):
    land_count = sum(bool(cards[name].profile.is_land) for name in mainboard if name in cards)
    basic_count = sum(name in BASIC_LANDS for name in mainboard)
    issues = []
    if land_count < mana_policy.hard_land_minimum or land_count > mana_policy.hard_land_maximum:
        issues.append(
            f"whole_deck_land_hard_gate:{land_count}:"
            f"{mana_policy.hard_land_minimum}-{mana_policy.hard_land_maximum}"
        )
    return land_count, basic_count, tuple(issues)
