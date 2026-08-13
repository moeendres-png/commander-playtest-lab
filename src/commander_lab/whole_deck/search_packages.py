from __future__ import annotations

import random
from collections import Counter, defaultdict

from commander_lab.models import CardRole

from .search_base import Proposal, SearchEngineBase
from .search_context import ENGINE_ROLES, SearchCard


class _PackageNeighborhoodMixin(SearchEngineBase):
    def _generic_role_proposal(
        self,
        mainboard: tuple[str, ...],
        rng: random.Random,
        roles: frozenset[CardRole],
        n: int,
    ) -> Proposal:
        current = Counter(mainboard)
        additions = self._candidate_additions(
            current, lambda card: bool(set(card.profile.roles) & set(roles))
        )
        additions.sort(
            key=lambda card: (
                self._utility[card.oracle_name] + rng.random() * 0.4,
                card.oracle_name,
            ),
            reverse=True,
        )
        add = [card.oracle_name for card in additions[:n]]
        if len(add) < n:
            fallback = self._candidate_additions(
                current, lambda card: not card.profile.is_land
            )
            fallback.sort(
                key=lambda card: (
                    self._utility[card.oracle_name] + rng.random() * 0.2,
                    card.oracle_name,
                ),
                reverse=True,
            )
            add.extend(card.oracle_name for card in fallback if card.oracle_name not in add)
            add = add[:n]
        selected = [
            self.context.cards[name]
            for name in set(mainboard)
            if name not in self.context.commander_names
            and not self.context.cards[name].profile.is_land
        ]
        selected.sort(
            key=lambda card: (
                bool(set(card.profile.roles) & set(roles)),
                self._utility[card.oracle_name],
                card.oracle_name,
            )
        )
        remove = [card.oracle_name for card in selected if card.oracle_name not in add][
            : len(add)
        ]
        return self._apply_replacements(mainboard, remove, add), tuple(remove), tuple(add)

    def _package_proposal(
        self,
        mainboard: tuple[str, ...],
        rng: random.Random,
        roles: frozenset[CardRole] | None,
        n: int,
    ) -> Proposal:
        current = Counter(mainboard)
        packages: dict[str, list[SearchCard]] = defaultdict(list)
        for card in self.context.cards.values():
            if (
                card.oracle_name in self.context.commander_names
                or current[card.oracle_name]
                or card.available_quantity <= 0
            ):
                continue
            if roles is not None and not (set(card.profile.roles) & set(roles)):
                continue
            for package_id in card.profile.package_ids:
                packages[package_id].append(card)
        viable = [
            (package_id, cards)
            for package_id, cards in packages.items()
            if len(cards) >= self.config.minimum_neighborhood_changes
        ]
        if not viable:
            return self._generic_role_proposal(mainboard, rng, roles or ENGINE_ROLES, n)
        viable.sort(key=lambda item: (len(item[1]), item[0]), reverse=True)
        _, package_cards = viable[0]
        package_cards.sort(
            key=lambda card: (self._utility[card.oracle_name], card.oracle_name), reverse=True
        )
        k = min(
            max(self.config.minimum_neighborhood_changes, n),
            self.config.maximum_neighborhood_changes,
            len(package_cards),
        )
        add = [card.oracle_name for card in package_cards[:k]]
        removable = [
            self.context.cards[name]
            for name in set(mainboard)
            if not self.context.cards[name].profile.is_land and name not in add
        ]
        removable.sort(key=lambda card: (self._utility[card.oracle_name], card.oracle_name))
        remove = [card.oracle_name for card in removable[:k]]
        return self._apply_replacements(mainboard, remove, add), tuple(remove), tuple(add)

    def _curve_proposal(
        self, mainboard: tuple[str, ...], rng: random.Random, n: int
    ) -> Proposal:
        current = Counter(mainboard)
        selected = [
            self.context.cards[name]
            for name in set(mainboard)
            if not self.context.cards[name].profile.is_land
        ]
        selected.sort(
            key=lambda card: (
                card.profile.mana_value,
                -self._utility[card.oracle_name],
                card.oracle_name,
            ),
            reverse=True,
        )
        remove = [card.oracle_name for card in selected[:n]]
        additions = self._candidate_additions(
            current,
            lambda card: not card.profile.is_land and card.profile.mana_value <= 2.5,
        )
        additions.sort(
            key=lambda card: (
                self._utility[card.oracle_name] + rng.random() * 0.3,
                -card.profile.mana_value,
                card.oracle_name,
            ),
            reverse=True,
        )
        add = [card.oracle_name for card in additions[: len(remove)]]
        used_remove = remove[: len(add)]
        return (
            self._apply_replacements(mainboard, used_remove, add),
            tuple(used_remove),
            tuple(add),
        )
