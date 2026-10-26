from __future__ import annotations

import random
from statistics import median

from commander_lab.models import FormatBand

from .features import contextual_card_utility
from .models import MetaFunctionalProfile
from .search_base import SearchEngineBase
from .search_context import SearchCard

WHOLE_DECK_META_SNAPSHOT_ID = "meta-2026-08-13-whole-deck-phase2-1"
# Meta-Lane PR5: snapshot packages for the RogShai search path, kept in a
# separate immutable file so the PR2 refresh snapshot stays untouched.
ROGSHAI_PR5_PACKAGE_FILE = "data/meta/packages/rogshai-2026-10-25.json"


class _ConstructMixin(SearchEngineBase):
    def _load_project_meta_references(self) -> dict[FormatBand, MetaFunctionalProfile]:
        from commander_lab.meta.store import MetaKnowledgeBase

        from .meta import all_sources_stale, build_meta_functional_profile, load_snapshot

        if self.context.root is None:
            return {}
        snapshot = MetaKnowledgeBase(self.context.root).load_snapshot(WHOLE_DECK_META_SNAPSHOT_ID)
        profiles = {
            name: card.profile for name, card in self.context.cards.items() if card.semantic_known
        }
        commander = "Ishai, Ojutai Dragonspeaker / Rograkh, Son of Rohgahh"
        try:
            package_snapshot = load_snapshot(self.context.root / ROGSHAI_PR5_PACKAGE_FILE)
            packages = package_snapshot.packages
            # PR6: a package file whose every source is stale contributes
            # nothing — stale external endorsement must not score.
            if all_sources_stale(package_snapshot):
                packages = ()
        except (OSError, ValueError):
            # A missing or malformed package file must not break the
            # search: without packages the scoring behaves exactly as
            # before PR5. The PR5 tests pin the file's presence.
            packages = ()
        result: dict[FormatBand, MetaFunctionalProfile] = {}
        for band, weight in self.policy.meta_band_weights.items():
            if weight <= 0.0:
                continue
            try:
                profile = build_meta_functional_profile(
                    snapshot,
                    commander=commander,
                    format_band=band,
                    profiles=profiles,
                )
            except ValueError:
                continue
            band_packages = tuple(
                package
                for package in packages
                if band.value in {category.value for category in package.categories}
            )
            result[band] = profile.model_copy(update={"snapshot_packages": band_packages})
        return result

    def _build_utility_map(self) -> dict[str, float]:
        known_land: list[float] = []
        known_nonland: list[float] = []
        raw: dict[str, float | None] = {}
        for name, card in self.context.cards.items():
            if card.search_utility_override is not None:
                value = card.search_utility_override
            elif card.semantic_known:
                value = contextual_card_utility(card.profile, self.policy).search_utility
            else:
                value = None
            raw[name] = value
            if value is not None:
                (known_land if card.profile.is_land else known_nonland).append(value)
        neutral_land = median(known_land) if known_land else 0.0
        neutral_nonland = median(known_nonland) if known_nonland else 0.0
        return {
            name: (
                value
                if value is not None
                else (neutral_land if self.context.cards[name].profile.is_land else neutral_nonland)
            )
            for name, value in raw.items()
        }

    def _land_quality(self, card: SearchCard) -> float:
        produced = len(card.profile.produces_colors)
        basic = 0.15 if card.is_basic else 0.0
        return produced * 0.8 + basic + self._utility.get(card.oracle_name, 0.0) * 0.05

    def _target_land_count(self, rng: random.Random | None = None) -> int:
        low = self.mana_policy.preferred_land_minimum
        high = self.mana_policy.preferred_land_maximum
        if rng is None or low == high:
            return round((low + high) / 2)
        return rng.randint(low, high)

    def _target_basic_count(self, land_count: int, rng: random.Random | None = None) -> int:
        low = min(land_count, self.mana_policy.preferred_basic_minimum)
        high = min(land_count, self.mana_policy.preferred_basic_maximum)
        if low > high:
            low = high
        if rng is None or low == high:
            return round((low + high) / 2)
        return rng.randint(low, high)

    def _basic_distribution(self, count: int) -> list[str]:
        if count <= 0:
            return []
        weights = (("Island", 0.40), ("Plains", 0.35), ("Mountain", 0.25))
        allocation = {name: int(count * weight) for name, weight in weights}
        while sum(allocation.values()) < count:
            for name, _ in weights:
                if sum(allocation.values()) >= count:
                    break
                allocation[name] += 1
        cards: list[str] = []
        for name, _ in weights:
            available = self.context.cards.get(name)
            if available is None:
                continue
            quantity = min(allocation[name], available.available_quantity)
            cards.extend([name] * quantity)
        return cards

    def constructive_start(
        self, *, rng: random.Random | None = None, diversified: bool = False
    ) -> tuple[str, ...]:
        land_count = self._target_land_count(rng if diversified else None)
        basic_target = self._target_basic_count(land_count, rng if diversified else None)
        nonbasic_land_need = max(0, land_count - basic_target)
        land_pool = [
            card
            for card in self.context.cards.values()
            if card.profile.is_land
            and not card.is_basic
            and card.oracle_name not in self.context.commander_names
            and card.available_quantity > 0
        ]
        if diversified and rng is not None:
            land_pool.sort(
                key=lambda card: (
                    self._land_quality(card) + rng.random() * 1.5,
                    card.oracle_name,
                ),
                reverse=True,
            )
        else:
            land_pool.sort(
                key=lambda card: (self._land_quality(card), card.oracle_name), reverse=True
            )
        lands = [card.oracle_name for card in land_pool[:nonbasic_land_need]]
        lands.extend(self._basic_distribution(land_count - len(lands)))
        if len(lands) < land_count:
            for card in land_pool[nonbasic_land_need:]:
                if card.oracle_name not in lands:
                    lands.append(card.oracle_name)
                if len(lands) == land_count:
                    break
        if len(lands) != land_count:
            raise RuntimeError(
                f"insufficient land candidates for constructive start: {len(lands)} / {land_count}"
            )

        need = 98 - land_count
        nonland_pool = [
            card
            for card in self.context.cards.values()
            if not card.profile.is_land
            and card.oracle_name not in self.context.commander_names
            and card.available_quantity > 0
        ]
        if diversified and rng is not None:
            ranked = sorted(
                nonland_pool,
                key=lambda card: (self._utility[card.oracle_name], card.oracle_name),
                reverse=True,
            )
            guided_count = need // 2
            selected = ranked[:guided_count]
            remaining = [card for card in nonland_pool if card not in selected]
            rng.shuffle(remaining)
            selected.extend(remaining[: need - guided_count])
        else:
            selected = sorted(
                nonland_pool,
                key=lambda card: (self._utility[card.oracle_name], card.oracle_name),
                reverse=True,
            )[:need]
        if len(selected) != need:
            raise RuntimeError(
                f"insufficient nonland candidates for constructive start: {len(selected)} / {need}"
            )
        return tuple(lands + [card.oracle_name for card in selected])
