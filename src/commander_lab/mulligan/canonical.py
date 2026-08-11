from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from commander_lab.mana_analysis import DeckManaAnalysis, ManaAnalyzer
from commander_lab.models import StructuralCardProfile, StructuralDeckProfile
from commander_lab.models.mulligan import MulliganContext, OpeningHandFeatures
from commander_lab.project_context import ProjectContextError, load_project_context

from .lab import MulliganLab as _LegacyMulliganLab
from .lab import MulliganLabError


class MulliganLab(_LegacyMulliganLab):
    """Mulligan Lab with canonical project context and deterministic mana diagnostics.

    The inherited hand policy and follow-up simulation model is intentionally unchanged. Current
    pod membership comes from canonical data, while mana facts refine source/tapped-land features.
    """

    def __init__(self, root: str | Path) -> None:
        super().__init__(root)
        try:
            self.project_context = load_project_context(self.root)
        except ProjectContextError as exc:
            raise MulliganLabError(str(exc)) from exc
        self.mana_analyzer = ManaAnalyzer(self.root)

    def _opponent_ids(self, context: MulliganContext, *, holdout: int = 0) -> tuple[str, ...]:
        need = max(1, context.pod_size - 1)
        if holdout:
            # The canonical source defines a holdout/sensitivity *pool*, not fixed pods or
            # frequencies. Deterministic slices are model test contexts only and never promoted
            # to canonical opponent frequencies.
            holdout_ids = self.project_context.holdout_deck_ids
            if not holdout_ids:
                raise MulliganLabError("canonical holdout/sensitivity opponent pool is empty")
            start = ((holdout - 1) * need) % len(holdout_ids)
            return tuple(holdout_ids[(start + index) % len(holdout_ids)] for index in range(need))

        if context.pod_size != 4:
            raise MulliganLabError(
                "canonical 3P/5P sensitivity contexts require explicit opponent composition; "
                "the MulliganContext does not carry opponent deck ids, so the lab refuses to "
                "invent them"
            )
        if context.deck_id not in self.project_context.active_own_deck_ids:
            raise MulliganLabError(
                f"{context.deck_id} is not a current active own deck; historical reference "
                "contexts must be requested explicitly outside the current primary mulligan path"
            )
        try:
            return self.project_context.primary_opponent_deck_ids(context.deck_id)
        except ProjectContextError as exc:
            raise MulliganLabError(str(exc)) from exc

    def analyze_deck_mana(self, deck_id: str) -> DeckManaAnalysis:
        return self.mana_analyzer.analyze_deck(self.deck(deck_id))

    def features(
        self,
        deck: StructuralDeckProfile,
        cards: Iterable[StructuralCardProfile],
    ) -> OpeningHandFeatures:
        hand = tuple(cards)
        baseline = super().features(deck, hand)
        mana = self.mana_analyzer.analyze_opening_hand(deck, hand)
        required = {
            "korvold/current": {"B", "G", "R"},
            "rogshai/current": {"W", "U", "R"},
        }.get(
            deck.deck_id,
            {
                color.value
                for card in deck.cards
                for color in (*card.color_identity, *card.color_requirements.keys())
            },
        )
        present = sum(mana.colored_sources.get(color, 0) > 0 for color in required)
        stability = present / max(1, len(required))
        return baseline.model_copy(
            update={
                "colored_sources": mana.colored_sources,
                "tapped_source_count": mana.definitely_tapped_source_count,
                "early_blue_source_count": mana.colored_sources.get("U", 0),
                "color_stability_score": stability,
            }
        )


__all__ = ["MulliganLab", "MulliganLabError"]
