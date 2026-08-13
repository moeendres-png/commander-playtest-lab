from __future__ import annotations

from .search_evaluate import evaluate_variant
from .search_models import WholeDeckMutation, WholeDeckVariant


class _ScoreMixin:
    def _evaluate(
        self,
        mainboard: tuple[str, ...],
        *,
        seed: int,
        parent_variant_id: str | None,
        mutation: WholeDeckMutation | None,
        start_type: str | None = None,
    ) -> WholeDeckVariant:
        return evaluate_variant(self, mainboard, seed, parent_variant_id, mutation, start_type)

    def evaluate_mainboard(
        self,
        mainboard: tuple[str, ...],
        *,
        seed: int | None = None,
        parent_variant_id: str | None = None,
        mutation: WholeDeckMutation | None = None,
    ) -> WholeDeckVariant:
        return self._evaluate(
            mainboard,
            seed=self.config.seed if seed is None else seed,
            parent_variant_id=parent_variant_id,
            mutation=mutation,
        )
