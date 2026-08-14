from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from commander_lab.mana_analysis import DeckManaAnalysis, ManaAnalyzer
from commander_lab.models import StructuralCardProfile, StructuralDeckProfile
from commander_lab.models.mulligan import MulliganContext, OpeningHandFeatures
from commander_lab.pod_scheduling import BalancedPodScenarioScheduler
from commander_lab.project_context import ProjectContextError, load_project_context
from commander_lab.repositories.opponents import CurrentOpponentRepository
from commander_lab.storage import sha256_value

from .lab import MulliganLab as _LegacyMulliganLab
from .lab import MulliganLabError


class MulliganLab(_LegacyMulliganLab):
    """Mulligan Lab with canonical current and historical project contexts.

    Current active-deck runs use the canonical primary pod. Historical own-deck regression runs
    remain supported through their explicitly historical reference scenario; they are never
    promoted back into the active deckbuilding scope.
    """

    def __init__(self, root: str | Path) -> None:
        super().__init__(root)
        try:
            self.project_context = load_project_context(self.root)
        except ProjectContextError as exc:
            raise MulliganLabError(str(exc)) from exc
        self.mana_analyzer = ManaAnalyzer(self.root)

    def _opponent_ids(self, context: MulliganContext, *, holdout: int = 0) -> tuple[str, ...]:
        if context.pod_size != 4:
            raise MulliganLabError(
                "non-4P mulligan contexts require explicit opponent composition in a separate "
                "sensitivity workflow"
            )
        repository = CurrentOpponentRepository(self.root)
        scheduler = BalancedPodScenarioScheduler(
            repository.records(), opponent_registry_hash=repository.registry_hash
        )
        seed_payload = {
            "deck_id": context.deck_id,
            "deck_hash": context.deck_hash,
            "opponent_ensemble_id": context.opponent_ensemble_id,
            "holdout": holdout,
            "axis": "mulligan_opponent_context",
        }
        seed = int(sha256_value(seed_payload)[:16], 16) % (2**31 - 1)
        return scheduler.schedule(1, seed=seed)[0].opponent_deck_ids

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
