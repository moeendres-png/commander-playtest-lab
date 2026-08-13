from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Sequence

from commander_lab.models import CardRole, FormatBand

from .models import DeckDesignPolicy, MetaFunctionalProfile
from .search_context import SearchCard, WholeDeckSearchContext
from .search_models import (
    ManaBasePolicy,
    WholeDeckHardGate,
    WholeDeckMutation,
    WholeDeckNeighborhood,
    WholeDeckSearchConfig,
    WholeDeckSearchResult,
    WholeDeckVariant,
)

Proposal = tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]
MaybeProposal = Proposal | None
SearchStart = tuple[str, tuple[str, ...], int]
SearchArchive = dict[str, WholeDeckVariant]
CardPredicate = Callable[[SearchCard], bool]


class SearchEngineBase:
    """Typed contract shared by the small Whole-Deck search mixins.

    The concrete engine supplies these methods through sibling mixins.  Keeping the
    contract in one non-public base preserves the modular runtime structure while
    making strict static typing explicit instead of relying on dynamic attributes.
    """

    context: WholeDeckSearchContext
    policy: DeckDesignPolicy
    config: WholeDeckSearchConfig
    mana_policy: ManaBasePolicy
    meta_references: dict[FormatBand, MetaFunctionalProfile]
    _utility: dict[str, float]

    def _load_project_meta_references(self) -> dict[FormatBand, MetaFunctionalProfile]:
        raise NotImplementedError

    def _build_utility_map(self) -> dict[str, float]:
        raise NotImplementedError

    def _land_quality(self, card: SearchCard) -> float:
        raise NotImplementedError

    def _target_land_count(self, rng: random.Random | None = None) -> int:
        raise NotImplementedError

    def _target_basic_count(self, land_count: int, rng: random.Random | None = None) -> int:
        raise NotImplementedError

    def _basic_distribution(self, count: int) -> list[str]:
        raise NotImplementedError

    def constructive_start(
        self, *, rng: random.Random | None = None, diversified: bool = False
    ) -> tuple[str, ...]:
        raise NotImplementedError

    def _candidate_additions(
        self, current: Counter[str], predicate: CardPredicate
    ) -> list[SearchCard]:
        raise NotImplementedError

    def _apply_replacements(
        self, mainboard: tuple[str, ...], remove: Sequence[str], add: Sequence[str]
    ) -> tuple[str, ...]:
        raise NotImplementedError

    def _generic_role_proposal(
        self,
        mainboard: tuple[str, ...],
        rng: random.Random,
        roles: frozenset[CardRole],
        n: int,
    ) -> Proposal:
        raise NotImplementedError

    def _package_proposal(
        self,
        mainboard: tuple[str, ...],
        rng: random.Random,
        roles: frozenset[CardRole] | None,
        n: int,
    ) -> Proposal:
        raise NotImplementedError

    def _curve_proposal(self, mainboard: tuple[str, ...], rng: random.Random, n: int) -> Proposal:
        raise NotImplementedError

    def _land_balance_proposal(
        self, mainboard: tuple[str, ...], rng: random.Random, n: int
    ) -> Proposal:
        raise NotImplementedError

    def _basic_mix_proposal(
        self, mainboard: tuple[str, ...], rng: random.Random, n: int
    ) -> Proposal:
        raise NotImplementedError

    def _feature_summary(self, mainboard: tuple[str, ...]) -> dict[str, object]:
        raise NotImplementedError

    def _synthetic_mana_summary(self, mainboard: tuple[str, ...]) -> dict[str, object]:
        raise NotImplementedError

    def _meta_distance(self, mainboard: tuple[str, ...]) -> dict[str, float | None]:
        raise NotImplementedError

    def _objective(
        self,
        mainboard: tuple[str, ...],
        features: dict[str, object],
        mana: dict[str, object],
        meta: dict[str, float | None],
    ) -> float:
        raise NotImplementedError

    def _hard_gate(self, mainboard: tuple[str, ...]) -> WholeDeckHardGate:
        raise NotImplementedError

    def _evaluate(
        self,
        mainboard: tuple[str, ...],
        *,
        seed: int,
        parent_variant_id: str | None,
        mutation: WholeDeckMutation | None,
        start_type: str | None = None,
    ) -> WholeDeckVariant:
        raise NotImplementedError

    def evaluate_mainboard(
        self,
        mainboard: tuple[str, ...],
        *,
        seed: int | None = None,
        parent_variant_id: str | None = None,
        mutation: WholeDeckMutation | None = None,
    ) -> WholeDeckVariant:
        raise NotImplementedError

    def propose(
        self,
        mainboard: tuple[str, ...],
        neighborhood: WholeDeckNeighborhood,
        rng: random.Random,
    ) -> Proposal:
        raise NotImplementedError

    def _temperature(self, step: int) -> float:
        raise NotImplementedError

    def _accept(self, delta: float, temperature: float, rng: random.Random) -> tuple[bool, bool]:
        raise NotImplementedError

    def run(self, *, current_control: tuple[str, ...] | None = None) -> WholeDeckSearchResult:
        raise NotImplementedError
