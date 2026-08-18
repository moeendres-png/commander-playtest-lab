from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from statistics import fmean
from typing import Literal

from commander_lab.mana_analysis import DeckManaAnalysis, ManaAnalyzer
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    StructuralCardProfile,
    StructuralDeckProfile,
)
from commander_lab.models.mulligan import (
    GeneratedKeepRule,
    KeepRuleClause,
    KeepRuleValidationResult,
    LondonMulliganResult,
    MulliganContext,
    MulliganPolicyName,
    MulliganPolicySummary,
    OpeningHandFeatures,
)
from commander_lab.pod_scheduling import BalancedPodScenarioScheduler
from commander_lab.project_context import ProjectContextError, load_project_context
from commander_lab.repositories.opponents import CurrentOpponentRepository
from commander_lab.storage import sha256_value

from .lab import MulliganLab as _LegacyMulliganLab
from .lab import MulliganLabError

type _KeepRuleContextKind = Literal[
    "primary_pod", "holdout_pod", "opponent_ensemble", "pilot_profile"
]


class MulliganLab(_LegacyMulliganLab):
    """Mulligan Lab with canonical current and historical project contexts.

    Current active-deck runs use the canonical primary pod. Historical own-deck regression runs
    remain supported through their explicitly historical reference scenario; they are never
    promoted back into the active deckbuilding scope. Unknown/future commander families use
    generic structural policy rather than silently inheriting RogShai assumptions.
    """

    _KNOWN_SPECIALIST_STRATEGIES = frozenset({"korvold", "rogshai", "ishai_rograkh"})

    def __init__(self, root: str | Path) -> None:
        super().__init__(root)
        try:
            self.project_context = load_project_context(self.root)
        except ProjectContextError as exc:
            raise MulliganLabError(str(exc)) from exc
        self.mana_analyzer = ManaAnalyzer(self.root)

    def _deck_strategy(self, deck_id: str) -> str:
        return self.deck(deck_id).commander_strategy.casefold()

    def _pilot_name_for_policy(
        self, deck_id: str, policy: MulliganPolicyName, requested: str
    ) -> str:
        if self._deck_strategy(deck_id) not in self._KNOWN_SPECIALIST_STRATEGIES:
            return "GenericCommanderPilot"
        return super()._pilot_name_for_policy(deck_id, policy, requested)

    def _pilot_config(
        self, deck: StructuralDeckProfile, policy: MulliganPolicyName, context: MulliganContext
    ) -> PilotConfig:
        if deck.commander_strategy.casefold() not in self._KNOWN_SPECIALIST_STRATEGIES:
            return PilotConfig(
                pilot_name="GenericCommanderPilot",
                strength=PilotStrength.STRONG,
                mode=PilotDecisionMode.DETERMINISTIC,
            )
        return super()._pilot_config(deck, policy, context)

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

    def generate_keep_rules(
        self,
        context: MulliganContext,
        summaries: Iterable[MulliganPolicySummary],
        source_run_hash: str,
    ) -> list[GeneratedKeepRule]:
        deck = self.deck(context.deck_id)
        if deck.commander_strategy.casefold() in self._KNOWN_SPECIALIST_STRATEGIES:
            return super().generate_keep_rules(context, summaries, source_run_hash)

        rows = tuple(summaries)
        if not rows:
            raise MulliganLabError("cannot generate a keep rule without policy summaries")
        best = min(
            rows,
            key=lambda row: (row.structural_placement_mean or 99.0, row.average_mulligans),
        )
        clauses = (
            KeepRuleClause(
                feature="land_count",
                operator="between",
                value=(2.0, 4.0),
                rationale="generic Commander structural land band",
            ),
            KeepRuleClause(
                feature="color_stability_score",
                operator="ge",
                value=0.5,
                rationale="require at least partial access to the deck's represented colors",
            ),
        )
        exceptions = (
            "No commander-specific keep window is inferred for a generic deck profile.",
            "This is a structural candidate rule and requires cross-context validation.",
        )
        return [
            GeneratedKeepRule(
                rule_id=f"{context.deck_id.replace('/', '.')}.{best.policy.value}.candidate-v1",
                deck_id=context.deck_id,
                deck_hash=context.deck_hash,
                policy=best.policy,
                clauses=clauses,
                exceptions=exceptions,
                source_run_hash=source_run_hash,
                validation_contexts=(
                    "primary_structural",
                    "opponent_ensemble",
                    "generic_pilot_candidate",
                ),
                validation_status="candidate",
            )
        ]

    def validate_keep_rule_across_contexts(
        self,
        rule: GeneratedKeepRule,
        context: MulliganContext,
        *,
        samples: int,
    ) -> tuple[KeepRuleValidationResult, ...]:
        deck = self.deck(context.deck_id)
        if deck.commander_strategy.casefold() in self._KNOWN_SPECIALIST_STRATEGIES:
            return super().validate_keep_rule_across_contexts(rule, context, samples=samples)

        baseline_policy = rule.policy
        pilot_name = "GenericCommanderPilot"
        contexts: list[tuple[str, _KeepRuleContextKind, MulliganContext, int, str]] = [
            ("primary", "primary_pod", context, 0, pilot_name),
            ("holdout-a", "holdout_pod", context, 1, pilot_name),
            ("holdout-b", "holdout_pod", context, 2, pilot_name),
            (
                "ensemble",
                "opponent_ensemble",
                context.model_copy(
                    update={
                        "opponent_ensemble_id": context.opponent_ensemble_id
                        or "morcant-elves-ensemble-v1"
                    }
                ),
                0,
                pilot_name,
            ),
            (
                "pilot-generic",
                "pilot_profile",
                context.model_copy(update={"pilot_profile_id": pilot_name}),
                0,
                pilot_name,
            ),
        ]
        output: list[KeepRuleValidationResult] = []
        for context_id, kind, test_context, holdout, selected_pilot in contexts:
            agreements = 0
            placements: list[float] = []
            baselines: list[float] = []
            for index, seq in enumerate(
                self.iter_draw_sequences(deck, samples=samples, seed=context.seed + 1009)
            ):
                first = seq[0]
                features = self.features(deck, first)
                rule_keep = bool(self.test_rule(rule, features)["keep"])
                baseline_eval = self.evaluate(deck, first, baseline_policy, test_context)
                agreements += int(rule_keep == baseline_eval.keep)
                if rule_keep:
                    forced = LondonMulliganResult(
                        initial_draws=(tuple(card.oracle_name for card in first),),
                        kept_cards=tuple(card.oracle_name for card in first),
                        bottomed_cards=(),
                        mulligans_taken=0,
                        effective_bottom_count=0,
                        free_multiplayer_mulligan_used=False,
                        evaluation=baseline_eval.model_copy(update={"keep": True}),
                        commander_names=deck.commander_names,
                    )
                    placements.append(
                        self._full_followup_metrics(
                            deck,
                            forced,
                            test_context,
                            baseline_policy,
                            index,
                            holdout=holdout,
                            pilot_profile_id=selected_pilot,
                        )[3]
                    )
                baseline_result = self.london_mulligan_from_draws(
                    deck, seq, baseline_policy, test_context
                )
                baselines.append(
                    self._full_followup_metrics(
                        deck,
                        baseline_result,
                        test_context,
                        baseline_policy,
                        index + 10000,
                        holdout=holdout,
                        pilot_profile_id=selected_pilot,
                    )[3]
                )
            placement = fmean(placements) if placements else None
            baseline = fmean(baselines) if baselines else None
            delta = placement - baseline if placement is not None and baseline is not None else None
            agreement = agreements / samples
            output.append(
                KeepRuleValidationResult(
                    context_id=context_id,
                    context_kind=kind,
                    pilot_profile_id=selected_pilot,
                    opponent_deck_ids=self._opponent_ids(test_context, holdout=holdout),
                    samples=samples,
                    keep_agreement_rate=agreement,
                    average_placement=placement,
                    baseline_average_placement=baseline,
                    placement_delta=delta,
                    supported=agreement >= 0.60 and (delta is None or delta <= 0.35),
                )
            )
        return tuple(output)


__all__ = ["MulliganLab", "MulliganLabError"]
