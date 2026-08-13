from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from .search_context import SearchCard


class _PoolOpsMixin:
    def _candidate_additions(self, current: Counter[str], predicate: Any) -> list[SearchCard]:
        rows: list[SearchCard] = []
        for card in self.context.cards.values():
            if card.oracle_name in self.context.commander_names or card.available_quantity <= 0:
                continue
            if not card.is_basic and current[card.oracle_name] >= 1:
                continue
            if card.is_basic and current[card.oracle_name] >= card.available_quantity:
                continue
            if predicate(card):
                rows.append(card)
        return rows

    def _apply_replacements(self, mainboard: tuple[str, ...], remove: Sequence[str], add: Sequence[str]) -> tuple[str, ...]:
        cards = list(mainboard)
        for name in remove:
            cards.remove(name)
        cards.extend(add)
        return tuple(cards)
