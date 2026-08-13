from __future__ import annotations

import random
from collections import Counter

from .mana import BASIC_LANDS as SEARCH_BASIC_LANDS


class _ManaNeighborhoodMixin:
    def _land_balance_proposal(self, mainboard: tuple[str, ...], rng: random.Random, n: int) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        current = Counter(mainboard)
        lands = [name for name in mainboard if self.context.cards[name].profile.is_land]
        nonlands = [name for name in mainboard if not self.context.cards[name].profile.is_land]
        land_count = sum(self.context.cards[name].profile.is_land for name in mainboard)
        desired = int(round((self.mana_policy.preferred_land_minimum + self.mana_policy.preferred_land_maximum) / 2))
        decrease = land_count > desired or (land_count == desired and rng.random() < 0.5)
        delta = min(3, max(1, abs(land_count - desired)))
        k = max(self.config.minimum_neighborhood_changes, n)
        if decrease and lands:
            land_remove = sorted(lands, key=lambda name: (self._land_quality(self.context.cards[name]), name))[:delta]
            extra_remove = sorted(nonlands, key=lambda name: (self._utility[name], name))[: max(0, k - delta)]
            remove = land_remove + extra_remove
            additions = self._candidate_additions(current, lambda card: not card.profile.is_land)
        else:
            nonland_remove = sorted(nonlands, key=lambda name: (self._utility[name], name))[:delta]
            extra_remove = sorted([name for name in lands if name not in nonland_remove], key=lambda name: (self._land_quality(self.context.cards[name]), name))[: max(0, k - delta)]
            remove = nonland_remove + extra_remove
            additions = self._candidate_additions(current, lambda card: card.profile.is_land and not card.is_basic)
        additions.sort(key=lambda card: ((self._land_quality(card) if card.profile.is_land else self._utility[card.oracle_name]) + rng.random() * 0.2, card.oracle_name), reverse=True)
        add = [card.oracle_name for card in additions[: len(remove)]]
        if not decrease and len(add) < len(remove):
            add.extend(self._basic_distribution(len(remove) - len(add)))
        return self._apply_replacements(mainboard, remove[: len(add)], add), tuple(remove[: len(add)]), tuple(add)

    def _basic_mix_proposal(self, mainboard: tuple[str, ...], rng: random.Random, n: int) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        current = Counter(mainboard)
        basic_positions = [name for name in mainboard if name in SEARCH_BASIC_LANDS]
        nonbasic_lands = [name for name in set(mainboard) if self.context.cards[name].profile.is_land and name not in SEARCH_BASIC_LANDS]
        move_to_nonbasic = len(basic_positions) >= self.config.minimum_neighborhood_changes and (not nonbasic_lands or rng.random() < 0.6)
        k = min(max(self.config.minimum_neighborhood_changes, n), self.config.maximum_neighborhood_changes)
        if move_to_nonbasic:
            additions = self._candidate_additions(current, lambda card: card.profile.is_land and not card.is_basic)
            additions.sort(key=lambda card: (self._land_quality(card), card.oracle_name), reverse=True)
            add = [card.oracle_name for card in additions[: min(k, len(basic_positions))]]
            remove = basic_positions[: len(add)]
        else:
            remove = sorted(nonbasic_lands, key=lambda name: (self._land_quality(self.context.cards[name]), name))[:k]
            add = self._basic_distribution(len(remove))
        return self._apply_replacements(mainboard, remove[: len(add)], add), tuple(remove[: len(add)]), tuple(add)
