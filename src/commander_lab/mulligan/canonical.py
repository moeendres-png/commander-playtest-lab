from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from commander_lab.agents.live_routing import pilot_family, strategy_family
from commander_lab.mana_analysis import DeckManaAnalysis, ManaAnalyzer
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    StructuralCardProfile,
    StructuralDeckProfile,
)
from commander_lab.models.mulligan import MulliganContext, MulliganPolicyName, OpeningHandFeatures
from commander_lab.pod_scheduling import BalancedPodScenarioScheduler
from commander_lab.project_context import ProjectContextError, load_project_context
from commander_lab.repositories.opponents import CurrentOpponentRepository
from commander_lab.storage import sha256_value

from .lab import MulliganLab as _LegacyMulliganLab
from .lab import MulliganLabError


_ROGSHAI_POLICY_PILOTS = {
    MulliganPolicyName.CONSERVATIVE: "RogShaiControlPilot",
    MulliganPolicyName.CURVE_ORIENTED: "RogShaiTempoPilot",
    MulliganPolicyName.COMMANDER_ORIENTED: "RogShaiVoltronPilot",
    MulliganPolicyName.INTERACTION_ORIENTED: "RogShaiControlPilot",
    MulliganPolicyName.MATCHUP_ORIENTED: "RogShaiProtectedFinishPilot",
    MulliganPolicyName.PRIMER_POLICY: "RogShaiProtectedFinishPilot",
    MulliganPolicyName.CURRENT_PILOT: "RogShaiPilot",
    MulliganPolicyName.LEARNED_POLICY: "RogShaiSpellslingerPilot",
}


class MulliganLab(_LegacyMulliganLab):
    """Mulligan Lab with canonical current and historical project contexts.

    Current active-deck runs use the canonical primary pod. Historical own-deck regression runs
    remain supported through their explicitly historical reference scenario; they are never
    promoted back into the active deckbuilding scope. Unknown/non-specialized commander families
    use the neutral GenericCommanderPilot and never inherit RogShai-specific keep routing.
    """

    def __init__(self, root: str | Path) -> None:
        super().__init__(root)
        try:
            self.project_context = load_project_context(self.root)
        except ProjectContextError as exc:
            raise MulliganLabError(str(exc)) from exc
        self.mana_analyzer = ManaAnalyzer(self.root)

    @staticmethod
    def _baseline_pilot_name(deck_id: str) -> str:
        return "RogShaiPilot" if deck_id == "rogshai/current" else "GenericCommanderPilot"

    def _pilot_name_for_policy(
        self, deck_id: str, policy: MulliganPolicyName, requested: str
    ) -> str:
        deck = self.deck(deck_id)
        family = strategy_family(deck.commander_strategy)

        if requested not in {"", "baseline", "test-pilot"}:
            try:
                profile = self.pilot_registry.profile(requested)
            except KeyError as exc:
                raise MulliganLabError(f"unknown explicit pilot profile: {requested}") from exc
            actual = pilot_family(profile.pilot_name)
            if actual != family:
                raise MulliganLabError(
                    f"pilot family mismatch: deck={deck_id} strategy={family} "
                    f"pilot={profile.pilot_name} family={actual}"
                )
            return profile.pilot_name

        if family == "rogshai":
            return _ROGSHAI_POLICY_PILOTS[policy]
        return "GenericCommanderPilot"

    def _pilot_config(
        self, deck: StructuralDeckProfile, policy: MulliganPolicyName, context: MulliganContext
    ) -> PilotConfig:
        name = self._pilot_name_for_policy(deck.deck_id, policy, context.pilot_profile_id)
        profile = self.pilot_registry.profile(name)
        expected_family = strategy_family(deck.commander_strategy)
        actual_family = pilot_family(profile.pilot_name)
        if actual_family != expected_family:
            raise MulliganLabError(
                f"pilot family mismatch: deck={deck.deck_id} strategy={expected_family} "
                f"pilot={profile.pilot_name} family={actual_family}"
            )
        if profile.supported_deck_hashes and deck.deck_hash not in profile.supported_deck_hashes:
            raise MulliganLabError(f"pilot {name} does not support deck hash {deck.deck_hash}")
        return PilotConfig(
            pilot_name=name,
            strength=PilotStrength.STRONG,
            mode=PilotDecisionMode.DETERMINISTIC,
            profile_version=profile.version,
            parameter_hash=profile.parameter_hash,
            source_rule_ids=profile.source_rule_ids,
            allowed_deviation=profile.allowed_deviation,
            supported_deck_hashes=profile.supported_deck_hashes,
            information_policy=profile.information_policy,
        )

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
        required = (
            {
                "W",
                "U",
                "R",
            }
            if deck.deck_id == "rogshai/current"
            else {
                color.value
                for card in deck.cards
                for color in (*card.color_identity, *card.color_requirements.keys())
            }
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
