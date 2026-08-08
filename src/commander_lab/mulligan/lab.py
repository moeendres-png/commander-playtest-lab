from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from statistics import fmean, median

from commander_lab.agents.ensemble import PilotRegistry
from commander_lab.engine.structural import StructuralSimulator, load_project_structural_decks
from commander_lab.models import (
    CardRole,
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    StructuralAbortLimits,
    StructuralCardProfile,
    StructuralDeckProfile,
    StructuralMatchConfig,
)
from commander_lab.models.mulligan import (
    GeneratedKeepRule,
    HypergeometricBaseline,
    KeepRuleClause,
    KeepRuleValidationResult,
    LondonMulliganResult,
    MulliganContext,
    MulliganEstimateLevel,
    MulliganHandTypeSummary,
    MulliganLabResult,
    MulliganPolicyName,
    MulliganPolicySummary,
    OpeningHandEvaluation,
    OpeningHandFeatures,
)
from commander_lab.storage import sha256_value


class MulliganLabError(ValueError):
    pass


KNOWN_TAPPED_SOURCES = {
    "Bojuka Bog",
    "Path of Ancestry",
    "Temple of the False God",
    "Myriad Landscape",
    "Evolving Wilds",
    "Terramorphic Expanse",
}


class MulliganLab:
    """Deterministic opening-hand laboratory.

    This component intentionally separates hand-quality estimates from full-matchup claims.
    Follow-up samples are complete Structural Simulator games with a controlled opening hand;
    they remain role-level model estimates rather than comprehensive MTG rules-engine games.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.decks = load_project_structural_decks(
            self.root,
            include_synthetic_fixtures=True,
            include_current_opponents=True,
        )
        self.simulator = StructuralSimulator(self.decks)
        self.pilot_registry = PilotRegistry(self.root)

    def deck(self, deck_id: str) -> StructuralDeckProfile:
        try:
            return self.decks[deck_id]
        except KeyError as exc:
            raise MulliganLabError(f"unknown deck: {deck_id}") from exc

    @staticmethod
    def _library(deck: StructuralDeckProfile) -> tuple[StructuralCardProfile, ...]:
        commanders = set(deck.commander_names)
        return tuple(card for card in deck.cards if card.oracle_name not in commanders)

    @staticmethod
    def _has_role(card: StructuralCardProfile, role: CardRole) -> bool:
        return role in card.roles

    def _validate_context(self, context: MulliganContext) -> None:
        deck = self.deck(context.deck_id)
        if context.deck_hash != deck.deck_hash:
            raise MulliganLabError("context deck_hash does not match current structural deck")
        if context.seat_position > context.pod_size:
            raise MulliganLabError("seat_position is outside the pod")
        if context.opponent_ensemble_id and context.opponent_ensemble_hash:
            path = (
                self.root / "data" / "opponent_ensembles" / f"{context.opponent_ensemble_id}.json"
            )
            if not path.is_file():
                raise MulliganLabError("opponent ensemble hash supplied for an unknown ensemble")
            import json

            actual = sha256_value(json.loads(path.read_text(encoding="utf-8")))
            if actual != context.opponent_ensemble_hash:
                raise MulliganLabError("opponent ensemble hash mismatch")

    @staticmethod
    def _baseline_pilot_name(deck_id: str) -> str:
        return "KorvoldPilot" if deck_id == "korvold/current" else "RogShaiPilot"

    def _pilot_name_for_policy(
        self, deck_id: str, policy: MulliganPolicyName, requested: str
    ) -> str:
        if requested not in {"", "baseline", "test-pilot"}:
            try:
                self.pilot_registry.profile(requested)
                return requested
            except KeyError:
                pass
        korvold = {
            MulliganPolicyName.CONSERVATIVE: "KorvoldConservativePilot",
            MulliganPolicyName.CURVE_ORIENTED: "KorvoldSacrificePilot",
            MulliganPolicyName.COMMANDER_ORIENTED: "KorvoldAggressivePilot",
            MulliganPolicyName.INTERACTION_ORIENTED: "KorvoldConservativePilot",
            MulliganPolicyName.MATCHUP_ORIENTED: "KorvoldLandRebuildPilot",
            MulliganPolicyName.PRIMER_POLICY: "KorvoldValuePilot",
            MulliganPolicyName.CURRENT_PILOT: "KorvoldPilot",
            MulliganPolicyName.LEARNED_POLICY: "KorvoldValuePilot",
        }
        rogshai = {
            MulliganPolicyName.CONSERVATIVE: "RogShaiControlPilot",
            MulliganPolicyName.CURVE_ORIENTED: "RogShaiTempoPilot",
            MulliganPolicyName.COMMANDER_ORIENTED: "RogShaiVoltronPilot",
            MulliganPolicyName.INTERACTION_ORIENTED: "RogShaiControlPilot",
            MulliganPolicyName.MATCHUP_ORIENTED: "RogShaiProtectedFinishPilot",
            MulliganPolicyName.PRIMER_POLICY: "RogShaiProtectedFinishPilot",
            MulliganPolicyName.CURRENT_PILOT: "RogShaiPilot",
            MulliganPolicyName.LEARNED_POLICY: "RogShaiSpellslingerPilot",
        }
        return (korvold if deck_id == "korvold/current" else rogshai)[policy]

    def _pilot_config(
        self, deck: StructuralDeckProfile, policy: MulliganPolicyName, context: MulliganContext
    ) -> PilotConfig:
        name = self._pilot_name_for_policy(deck.deck_id, policy, context.pilot_profile_id)
        profile = self.pilot_registry.profile(name)
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
        primary = {
            "morcant": (
                "opponent/morcant-elves",
                "opponent/blight-curse-precon",
                "opponent/cosmic-spiderman-midbudget",
            ),
            "cosmic": (
                "opponent/cosmic-spiderman-midbudget",
                "opponent/doom-prevails-precon",
                "opponent/blight-curse-precon",
            ),
            "doom": (
                "opponent/doom-prevails-precon",
                "kaervek/current",
                "opponent/cosmic-spiderman-midbudget",
            ),
        }
        key = (context.opponent_ensemble_id or "").casefold()
        base = next(
            (rows for token, rows in primary.items() if token in key),
            (
                "opponent/morcant-elves",
                "opponent/blight-curse-precon",
                "opponent/cosmic-spiderman-midbudget",
            ),
        )
        if holdout == 1:
            base = (
                "kaervek/current",
                "opponent/doom-prevails-precon",
                "opponent/dance-elements-precon",
            )
        elif holdout == 2:
            base = (
                "opponent/wakanda-forever-precon",
                "opponent/cosmic-spiderman-midbudget",
                "opponent/blight-curse-precon",
            )
        need = max(1, context.pod_size - 1)
        expanded = []
        while len(expanded) < need:
            expanded.extend(base)
        return tuple(expanded[:need])

    @staticmethod
    def _hand_type(features: OpeningHandFeatures) -> str:
        lands = (
            "0-1"
            if features.land_count <= 1
            else "5+"
            if features.land_count >= 5
            else str(features.land_count)
        )
        color = "stable" if features.color_stability_score >= 2 / 3 else "unstable"
        plan = (
            "ramp"
            if features.ramp_count
            else "interaction"
            if features.interaction_count
            else "engine"
            if features.independent_engine_count
            else "payoff"
            if features.commander_synergy_count
            else "other"
        )
        return f"lands={lands}|colors={color}|plan={plan}"

    @staticmethod
    def _context_adjustment(
        context: MulliganContext, f: OpeningHandFeatures
    ) -> tuple[float, float, list[str]]:
        score = 0.0
        threshold = 0.0
        reasons: list[str] = []
        seat_delay = max(0, context.seat_position - 1)
        score += min(0.24, seat_delay * 0.04) * min(1.0, f.interaction_count + f.selection_count)
        if seat_delay:
            reasons.append("seat position adjusts interaction and selection value")
        profile = context.pilot_profile_id.casefold()
        if "conservative" in profile or "control" in profile:
            score += min(0.8, f.protection_count * 0.3 + f.interaction_count * 0.25)
            threshold += 0.12
        elif "aggressive" in profile or "voltron" in profile:
            score += min(0.7, f.commander_synergy_count * 0.25 + f.cheap_noncreature_count * 0.15)
            threshold -= 0.08
        elif "spellslinger" in profile or "value" in profile:
            score += min(0.7, f.independent_engine_count * 0.3 + f.draw_count * 0.2)
        plan = context.game_plan.value
        if plan == "protected_commander":
            score += min(1.0, f.protection_count * 0.45) + (
                0.45 if f.commander_immediate_value else -0.25
            )
        elif plan == "independent_engine":
            score += min(1.0, f.independent_engine_count * 0.55 + f.draw_count * 0.2)
        elif plan == "control":
            score += min(1.0, f.interaction_count * 0.35 + f.boardwipe_count * 0.45)
        elif plan == "fast_pressure":
            score += min(0.9, f.cheap_noncreature_count * 0.2 + f.commander_synergy_count * 0.25)
            threshold -= 0.12
        elif plan == "rebuild":
            score += min(0.8, f.independent_engine_count * 0.3 + f.boardwipe_count * 0.2)
        return score, threshold, reasons

    def features(
        self,
        deck: StructuralDeckProfile,
        cards: Iterable[StructuralCardProfile],
    ) -> OpeningHandFeatures:
        hand = tuple(cards)
        if deck.deck_id == "korvold/current":
            deck_color_values = {"B", "G", "R"}
        elif deck.deck_id == "rogshai/current":
            deck_color_values = {"W", "U", "R"}
        else:
            deck_color_values = {
                color.value
                for card in deck.cards
                for color in (
                    *card.color_identity,
                    *card.color_requirements.keys(),
                    *card.produces_colors,
                )
            }
        colors = {value: 0 for value in deck_color_values}
        for card in hand:
            if card.is_land or CardRole.MANA_SOURCE in card.roles:
                for color in card.produces_colors:
                    if color.value in colors:
                        colors[color.value] += 1
        land_count = sum(card.is_land for card in hand)
        tapped = sum(card.oracle_name in KNOWN_TAPPED_SOURCES for card in hand if card.is_land)
        ramp = sum(self._has_role(card, CardRole.RAMP) and card.mana_value <= 3 for card in hand)
        draw = sum(self._has_role(card, CardRole.DRAW) for card in hand)
        selection = sum(self._has_role(card, CardRole.SELECTION) for card in hand)
        interaction = sum(bool(card.roles & {CardRole.REMOVAL, CardRole.COUNTER}) for card in hand)
        protection = sum(self._has_role(card, CardRole.PROTECTION) for card in hand)
        commander_synergy = sum(card.commander_synergy >= 0.8 for card in hand)
        independent_engine = sum(
            self._has_role(card, CardRole.ENGINE) and card.commander_synergy < 1.2 for card in hand
        )
        expensive = sum(card.mana_value >= 5 and not card.is_land for card in hand)
        graveyard_hate = sum(self._has_role(card, CardRole.GRAVEYARD_HATE) for card in hand)
        wipe = sum(self._has_role(card, CardRole.WIPE) for card in hand)
        win_no_setup = sum(
            self._has_role(card, CardRole.FINISHER)
            and card.floor_value >= 0.9
            and card.immediate_impact >= 0.75
            for card in hand
        )
        sacrifice_resource = sum(
            bool(card.roles & {CardRole.TOKEN_SOURCE, CardRole.SACRIFICE_OUTLET, CardRole.ENABLER})
            or (
                CardRole.LAND_SYNERGY in card.roles
                and CardRole.RECURSION not in card.roles
                and card.mana_value <= 3
                and card.immediate_impact >= 0.75
            )
            for card in hand
        )
        blue_sources = colors.get("U", 0)
        cheap_noncreature = sum(
            not card.is_land and not card.is_creature and card.mana_value <= 2 for card in hand
        )
        combat_draw = sum(
            card.oracle_name in {"Combat Research", "Curiosity", "Staggering Insight"}
            for card in hand
        )
        offensive_without_window = sum(
            bool(card.roles & {CardRole.COMBAT_PAYOFF, CardRole.FINISHER})
            and card.oracle_name not in {"Boros Charm", "Silence"}
            and protection == 0
            for card in hand
        )
        required_colors = max(1, len(deck_color_values))
        present_colors = sum(count > 0 for count in colors.values())
        color_stability = min(1.0, present_colors / required_colors)
        commander_immediate = False
        if deck.deck_id == "korvold/current":
            immediate_sacrifice = sum(
                bool(
                    card.roles
                    & {CardRole.SACRIFICE_OUTLET, CardRole.TOKEN_SOURCE, CardRole.ENABLER}
                )
                and card.mana_value <= 3
                for card in hand
            )
            commander_immediate = immediate_sacrifice > 0 and (ramp > 0 or land_count >= 3)
        elif deck.deck_id == "rogshai/current":
            commander_immediate = blue_sources > 0 and (protection > 0 or interaction > 0)
        gy_cards = sum(
            bool(card.roles & {CardRole.RECURSION, CardRole.LAND_SYNERGY}) for card in hand
        )
        gy_setup = sum(
            bool(card.roles & {CardRole.SACRIFICE_OUTLET, CardRole.ENABLER}) for card in hand
        )
        only_gy = gy_cards >= 2 and gy_setup == 0 and independent_engine == 0
        return OpeningHandFeatures(
            hand_size=len(hand),
            land_count=land_count,
            colored_sources=colors,
            tapped_source_count=tapped,
            ramp_count=ramp,
            draw_count=draw,
            selection_count=selection,
            interaction_count=interaction,
            protection_count=protection,
            commander_synergy_count=commander_synergy,
            independent_engine_count=independent_engine,
            dead_high_cost_count=expensive,
            graveyard_hate_count=graveyard_hate,
            boardwipe_count=wipe,
            wincondition_without_setup_count=win_no_setup,
            sacrifice_resource_count=sacrifice_resource,
            commander_immediate_value=commander_immediate,
            early_blue_source_count=blue_sources,
            cheap_noncreature_count=cheap_noncreature,
            combat_draw_count=combat_draw,
            offensive_payoff_without_window_count=offensive_without_window,
            color_stability_score=color_stability,
            only_graveyard_plan_without_setup=only_gy,
        )

    def evaluate(
        self,
        deck: StructuralDeckProfile,
        cards: Iterable[StructuralCardProfile],
        policy: MulliganPolicyName,
        context: MulliganContext,
        *,
        effective_bottom_count: int = 0,
    ) -> OpeningHandEvaluation:
        hand = tuple(cards)
        f = self.features(deck, hand)
        reasons: list[str] = []
        score = 0.0
        ideal_lands = 3 if deck.deck_id == "korvold/current" else 2.5
        score += 3.0 - abs(f.land_count - ideal_lands) * 1.15
        if deck.deck_id == "korvold/current":
            if not 2 <= f.land_count <= 4:
                score -= 3.0
                reasons.append("Korvold hand outside two-to-four-land band")
            if f.colored_sources.get("G", 0) == 0:
                score -= 2.4
                reasons.append("missing green source")
            score += min(1.8, f.ramp_count * 0.9)
            score += min(1.5, f.sacrifice_resource_count * 0.55)
            score += min(1.0, f.independent_engine_count * 0.6)
            score += min(0.9, f.protection_count * 0.5)
            if f.commander_immediate_value:
                score += 0.8
            if f.only_graveyard_plan_without_setup:
                score -= 1.5
                reasons.append("graveyard plan lacks setup")
            if f.dead_high_cost_count >= 3:
                score -= 1.3
                reasons.append("too many expensive engines")
        elif deck.deck_id == "rogshai/current":
            if not 2 <= f.land_count <= 3:
                score -= 2.7
                reasons.append("RogShai hand outside two-to-three-land band")
            if f.early_blue_source_count == 0:
                score -= 2.5
                reasons.append("missing early blue")
            score += min(1.4, f.ramp_count * 0.75)
            score += min(1.2, f.cheap_noncreature_count * 0.35)
            score += min(1.2, f.interaction_count * 0.45)
            score += min(1.0, f.protection_count * 0.5)
            score += min(0.8, f.combat_draw_count * 0.5)
            if f.offensive_payoff_without_window_count >= 2:
                score -= 1.25
                reasons.append("offensive payoffs lack protected Ishai window")
            if f.color_stability_score < 2 / 3:
                score -= 1.4
                reasons.append("unstable colors")
        else:
            score += min(1.5, f.ramp_count * 0.7)
            score += min(1.0, (f.draw_count + f.selection_count) * 0.4)
        score += min(0.8, f.draw_count * 0.35 + f.selection_count * 0.25)
        score -= f.tapped_source_count * 0.25
        score -= max(0, f.dead_high_cost_count - 1) * 0.45

        if policy == MulliganPolicyName.CONSERVATIVE:
            score += f.color_stability_score * 0.8 + min(0.8, f.protection_count * 0.4)
            threshold = 3.35
        elif policy == MulliganPolicyName.CURVE_ORIENTED:
            score += min(1.2, f.ramp_count * 0.55 + f.cheap_noncreature_count * 0.15)
            score -= f.dead_high_cost_count * 0.25
            threshold = 3.0
        elif policy == MulliganPolicyName.COMMANDER_ORIENTED:
            score += f.commander_synergy_count * 0.35 + (
                1.2 if f.commander_immediate_value else -0.4
            )
            threshold = 3.0
        elif policy == MulliganPolicyName.INTERACTION_ORIENTED:
            score += min(1.5, f.interaction_count * 0.55 + f.protection_count * 0.35)
            threshold = 3.15
        elif policy == MulliganPolicyName.MATCHUP_ORIENTED:
            score += self._matchup_adjustment(context, f)
            threshold = 3.05
        elif policy == MulliganPolicyName.PRIMER_POLICY:
            score += 0.7 if f.commander_immediate_value else -0.35
            score += min(0.8, f.protection_count * 0.4)
            threshold = 3.2
        elif policy == MulliganPolicyName.CURRENT_PILOT:
            score += min(0.6, f.commander_synergy_count * 0.2)
            threshold = 3.0
        else:  # learned policy is a candidate trained only on structural labels
            score += 0.25 * f.ramp_count + 0.2 * f.interaction_count
            threshold = 3.1
        context_score, context_threshold, context_reasons = self._context_adjustment(context, f)
        score += context_score
        threshold += context_threshold
        reasons.extend(context_reasons)
        threshold -= effective_bottom_count * 0.48
        if context.starting_player:
            threshold += 0.1  # no first-turn draw
        if context.pod_size >= 5:
            score += min(0.5, f.independent_engine_count * 0.25 + f.boardwipe_count * 0.2)
        keep = score >= threshold
        if keep:
            reasons.append("score meets model threshold")
        return OpeningHandEvaluation(
            cards=tuple(card.oracle_name for card in hand),
            features=f,
            policy=policy,
            keep=keep,
            score=round(score, 6),
            threshold=round(threshold, 6),
            reasons=tuple(reasons),
        )

    @staticmethod
    def _matchup_adjustment(context: MulliganContext, f: OpeningHandFeatures) -> float:
        identity = (context.opponent_ensemble_id or "").lower()
        if "morcant" in identity or "elf" in identity:
            return min(1.2, f.interaction_count * 0.35 + f.boardwipe_count * 0.7)
        if "doom" in identity:
            return min(1.1, f.interaction_count * 0.4 + f.independent_engine_count * 0.3)
        if "cosmic" in identity or "spider" in identity:
            return min(1.0, f.interaction_count * 0.35 + f.protection_count * 0.35)
        return min(0.5, f.interaction_count * 0.2)

    @staticmethod
    def _card_bottom_value(card: StructuralCardProfile, deck_id: str) -> float:
        if card.is_land:
            return 2.2
        value = card.floor_value + card.immediate_impact
        value += card.strength(CardRole.RAMP) * 1.1
        value += card.strength(CardRole.DRAW) * 0.6
        value += card.strength(CardRole.SELECTION) * 0.45
        value += card.strength(CardRole.PROTECTION) * 0.35
        value += card.strength(CardRole.REMOVAL) * 0.25
        value += card.strength(CardRole.COUNTER) * 0.3
        value += card.commander_synergy * (0.45 if deck_id == "korvold/current" else 0.35)
        value -= max(0.0, card.mana_value - 4.0) * 0.45
        return value

    def london_mulligan_from_draws(
        self,
        deck: StructuralDeckProfile,
        draws: tuple[tuple[StructuralCardProfile, ...], ...],
        policy: MulliganPolicyName,
        context: MulliganContext,
    ) -> LondonMulliganResult:
        multiplayer_free = context.pod_size >= 3
        selected: tuple[StructuralCardProfile, ...] | None = None
        evaluation: OpeningHandEvaluation | None = None
        mulligans = 0
        for index, hand in enumerate(draws):
            effective_bottom = max(0, index - (1 if multiplayer_free and index > 0 else 0))
            evaluation = self.evaluate(
                deck, hand, policy, context, effective_bottom_count=effective_bottom
            )
            if evaluation.keep or index == len(draws) - 1:
                selected = hand
                mulligans = index
                break
        assert selected is not None and evaluation is not None
        bottom_count = max(0, mulligans - (1 if multiplayer_free and mulligans > 0 else 0))
        ranked = sorted(
            enumerate(selected),
            key=lambda row: (
                self._card_bottom_value(row[1], deck.deck_id),
                -row[1].mana_value,
                row[0],
            ),
        )
        bottom_indexes = {index for index, _ in ranked[:bottom_count]}
        kept = tuple(
            card.oracle_name for index, card in enumerate(selected) if index not in bottom_indexes
        )
        bottomed = tuple(
            card.oracle_name for index, card in enumerate(selected) if index in bottom_indexes
        )
        return LondonMulliganResult(
            initial_draws=tuple(tuple(card.oracle_name for card in hand) for hand in draws),
            kept_cards=kept,
            bottomed_cards=bottomed,
            mulligans_taken=mulligans,
            effective_bottom_count=bottom_count,
            free_multiplayer_mulligan_used=multiplayer_free and mulligans > 0,
            evaluation=evaluation,
            commander_names=deck.commander_names,
        )

    def iter_draw_sequences(
        self,
        deck: StructuralDeckProfile,
        *,
        samples: int,
        seed: int,
        max_mulligans: int = 6,
    ):
        if not 1 <= samples <= 5_000_000:
            raise MulliganLabError("samples must be between 1 and 5,000,000")
        library = self._library(deck)
        rng = random.Random(seed)
        for _ in range(samples):
            yield tuple(tuple(rng.sample(library, 7)) for _attempt in range(max_mulligans + 1))

    def sample_draw_sequences(
        self,
        deck: StructuralDeckProfile,
        *,
        samples: int,
        seed: int,
        max_mulligans: int = 6,
    ) -> tuple[tuple[tuple[StructuralCardProfile, ...], ...], ...]:
        if samples > 100_000:
            raise MulliganLabError(
                "materialized sampling is capped at 100,000; use iter_draw_sequences for larger runs"
            )
        return tuple(
            self.iter_draw_sequences(deck, samples=samples, seed=seed, max_mulligans=max_mulligans)
        )

    @staticmethod
    def hypergeometric(
        *, population_size: int, category_size: int, draws: int, category: str
    ) -> HypergeometricBaseline:
        denom = math.comb(population_size, draws)
        probabilities: dict[int, float] = {}
        max_k = min(draws, category_size)
        exact = []
        for k in range(max_k + 1):
            if draws - k > population_size - category_size:
                exact.append(0.0)
            else:
                exact.append(
                    math.comb(category_size, k)
                    * math.comb(population_size - category_size, draws - k)
                    / denom
                )
        for threshold in range(1, min(4, max_k) + 1):
            probabilities[threshold] = sum(exact[threshold:])
        return HypergeometricBaseline(
            population_size=population_size,
            category_size=category_size,
            draws=draws,
            probability_at_least=probabilities,
            category=category,
        )

    def baselines(self, deck: StructuralDeckProfile) -> tuple[HypergeometricBaseline, ...]:
        library = self._library(deck)
        categories = {
            "lands": sum(card.is_land for card in library),
            "early_ramp": sum(
                CardRole.RAMP in card.roles and card.mana_value <= 2 for card in library
            ),
            "interaction": sum(
                bool(card.roles & {CardRole.REMOVAL, CardRole.COUNTER}) for card in library
            ),
            "protection": sum(CardRole.PROTECTION in card.roles for card in library),
            "independent_draw_engine": sum(
                bool(card.roles & {CardRole.DRAW, CardRole.ENGINE}) and card.commander_synergy < 1.2
                for card in library
            ),
        }
        return tuple(
            self.hypergeometric(
                population_size=len(library), category_size=size, draws=7, category=name
            )
            for name, size in categories.items()
        )

    @staticmethod
    def _wilson_half_width(successes: int, n: int) -> float:
        if n <= 0:
            return 0.0
        z = 1.959963984540054
        p = successes / n
        denom = 1 + z * z / n
        return z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom

    def _full_followup_metrics(
        self,
        deck: StructuralDeckProfile,
        result: LondonMulliganResult,
        context: MulliganContext,
        policy: MulliganPolicyName,
        sample_index: int,
        *,
        holdout: int = 0,
        pilot_profile_id: str | None = None,
    ) -> tuple[float | None, float | None, float | None, float, bool]:
        opponents = list(self._opponent_ids(context, holdout=holdout))
        target_seat = min(context.pod_size - 1, max(0, context.seat_position - 1))
        deck_ids = opponents[:]
        deck_ids.insert(target_seat, deck.deck_id)
        pilot_context = context
        if pilot_profile_id is not None:
            pilot_context = context.model_copy(update={"pilot_profile_id": pilot_profile_id})
        target_config = self._pilot_config(deck, policy, pilot_context)
        pilot_configs = [PilotConfig() for _ in deck_ids]
        pilot_configs[target_seat] = target_config
        opening_hands: list[tuple[str, ...] | None] = [None for _ in deck_ids]
        opening_hands[target_seat] = result.kept_cards
        seed = int(
            sha256_value(
                {
                    "seed": context.seed,
                    "policy": policy.value,
                    "sample": sample_index,
                    "holdout": holdout,
                    "pilot": target_config.pilot_name,
                    "opening": result.kept_cards,
                }
            )[:16],
            16,
        )
        match = self.simulator.simulate(
            StructuralMatchConfig(
                match_id=f"mulligan-{policy.value}-{holdout}-{sample_index}",
                seed=seed,
                deck_ids=tuple(deck_ids),
                starting_player_seat=target_seat if context.starting_player else 0,
                pilot_configs=tuple(pilot_configs),
                opening_hand_overrides=tuple(opening_hands),
                limits=StructuralAbortLimits(max_turns=24),
            ),
            run_id="mulligan-lab-followup",
            capture_events=False,
        )
        metrics = match.player_metrics[f"p{target_seat + 1}"]
        return (
            float(metrics.first_ramp_turn) if metrics.first_ramp_turn is not None else None,
            float(metrics.first_commander_cast_turn)
            if metrics.first_commander_cast_turn is not None
            else None,
            float(metrics.first_independent_draw_engine_turn)
            if metrics.first_independent_draw_engine_turn is not None
            else None,
            float(metrics.placement),
            match.completed,
        )

    @staticmethod
    def _mean_present(values: list[float | None]) -> float | None:
        present = [value for value in values if value is not None]
        return fmean(present) if present else None

    def _summarize_hand_types(
        self,
        buckets: dict[str, dict[str, list[float] | int]],
    ) -> tuple[MulliganHandTypeSummary, ...]:
        rows: list[MulliganHandTypeSummary] = []
        for key, bucket in sorted(buckets.items()):
            samples = int(bucket["samples"])
            rows.append(
                MulliganHandTypeSummary(
                    hand_type=key,
                    samples=samples,
                    keep_rate=float(bucket["first_keeps"]) / samples,
                    mulligan_rate=float(bucket["mulligans"]) / samples,
                    average_mulligans=float(bucket["mulligan_total"]) / samples,
                    color_problem_rate=float(bucket["color_issues"]) / samples,
                    average_dead_cards=float(bucket["dead_total"]) / samples,
                    first_ramp_turn_mean=self._mean_present(bucket["ramp_rows"]),
                    commander_cast_turn_mean=self._mean_present(bucket["commander_rows"]),
                    first_draw_engine_turn_mean=self._mean_present(bucket["draw_rows"]),
                    structural_placement_mean=self._mean_present(bucket["placement_rows"]),
                    uncertainty_half_width_95=self._wilson_half_width(
                        int(bucket["first_keeps"]), samples
                    ),
                )
            )
        return tuple(rows)

    def run(
        self,
        context: MulliganContext,
        policies: tuple[MulliganPolicyName, ...],
        *,
        samples: int,
        followup_samples: int = 0,
    ) -> MulliganLabResult:
        self._validate_context(context)
        deck = self.deck(context.deck_id)
        summaries: list[MulliganPolicySummary] = []
        for policy in policies:
            first_keep = 0
            mulligan_count = 0
            mulligan_total = 0
            color_issues = 0
            dead_total = 0
            completed_followups = 0
            score_reservoir: list[float] = []
            ramp_rows: list[float | None] = []
            commander_rows: list[float | None] = []
            draw_rows: list[float | None] = []
            placement_rows: list[float | None] = []
            buckets: dict[str, dict[str, list[float] | int]] = defaultdict(
                lambda: {
                    "samples": 0,
                    "first_keeps": 0,
                    "mulligans": 0,
                    "mulligan_total": 0,
                    "color_issues": 0,
                    "dead_total": 0,
                    "ramp_rows": [],
                    "commander_rows": [],
                    "draw_rows": [],
                    "placement_rows": [],
                }
            )
            for index, seq in enumerate(
                self.iter_draw_sequences(deck, samples=samples, seed=context.seed)
            ):
                first_eval = self.evaluate(deck, seq[0], policy, context)
                result = self.london_mulligan_from_draws(deck, seq, policy, context)
                is_first_keep = result.mulligans_taken == 0
                first_keep += int(is_first_keep)
                mulligan_count += int(result.mulligans_taken > 0)
                mulligan_total += result.mulligans_taken
                color_issue = result.evaluation.features.color_stability_score < 2 / 3
                color_issues += int(color_issue)
                dead_total += result.evaluation.features.dead_high_cost_count
                hand_type = self._hand_type(first_eval.features)
                bucket = buckets[hand_type]
                bucket["samples"] += 1
                bucket["first_keeps"] += int(is_first_keep)
                bucket["mulligans"] += int(result.mulligans_taken > 0)
                bucket["mulligan_total"] += result.mulligans_taken
                bucket["color_issues"] += int(color_issue)
                bucket["dead_total"] += result.evaluation.features.dead_high_cost_count
                if len(score_reservoir) < 10_000:
                    score_reservoir.append(result.evaluation.score)
                else:
                    replacement = random.Random(context.seed + index).randrange(index + 1)
                    if replacement < len(score_reservoir):
                        score_reservoir[replacement] = result.evaluation.score
                if index < followup_samples:
                    row = self._full_followup_metrics(deck, result, context, policy, index)
                    ramp_rows.append(row[0])
                    commander_rows.append(row[1])
                    draw_rows.append(row[2])
                    placement_rows.append(row[3])
                    completed_followups += int(row[4])
                    bucket["ramp_rows"].append(row[0])
                    bucket["commander_rows"].append(row[1])
                    bucket["draw_rows"].append(row[2])
                    bucket["placement_rows"].append(row[3])
            summaries.append(
                MulliganPolicySummary(
                    policy=policy,
                    samples=samples,
                    keep_rate_first_seven=first_keep / samples,
                    final_keep_rate=1.0,
                    mulligan_rate=mulligan_count / samples,
                    average_mulligans=mulligan_total / samples,
                    color_problem_rate=color_issues / samples,
                    average_dead_cards=dead_total / samples,
                    median_hand_score=median(score_reservoir),
                    first_ramp_turn_mean=self._mean_present(ramp_rows),
                    commander_cast_turn_mean=self._mean_present(commander_rows),
                    first_draw_engine_turn_mean=self._mean_present(draw_rows),
                    structural_placement_mean=self._mean_present(placement_rows),
                    uncertainty_half_width_95=self._wilson_half_width(first_keep, samples),
                    full_followup_games=len(placement_rows),
                    completed_followup_games=completed_followups,
                    hand_type_summaries=self._summarize_hand_types(buckets),
                    validation_contexts=(
                        "primary_pod",
                        "holdout_pod_a",
                        "holdout_pod_b",
                        "opponent_ensemble",
                        "multiple_pilots",
                    )
                    if followup_samples
                    else (),
                    estimate_level=(
                        MulliganEstimateLevel.STRUCTURAL_FOLLOWUP
                        if placement_rows
                        else MulliganEstimateLevel.MONTE_CARLO_HAND_QUALITY
                    ),
                )
            )
        run_hash = sha256_value(
            {
                "context": context.model_dump(mode="json"),
                "policies": [p.value for p in policies],
                "samples": samples,
                "followup_samples": followup_samples,
                "summaries": [s.model_dump(mode="json") for s in summaries],
            }
        )
        rules = self.generate_keep_rules(context, summaries, run_hash)
        validations: tuple[KeepRuleValidationResult, ...] = ()
        if rules:
            validations = self.validate_keep_rule_across_contexts(
                rules[0], context, samples=max(3, min(12, followup_samples or 6))
            )
            kinds = {row.context_kind for row in validations}
            required = {"primary_pod", "holdout_pod", "opponent_ensemble", "pilot_profile"}
            status = "holdout_checked" if required.issubset(kinds) else "candidate"
            if validations and sum(row.supported for row in validations) < len(validations) / 2:
                status = "rejected"
            rules[0] = rules[0].model_copy(
                update={
                    "validation_results": validations,
                    "validation_status": status,
                    "validation_contexts": tuple(row.context_id for row in validations),
                }
            )
        return MulliganLabResult(
            context=context,
            sample_count=samples,
            policies=tuple(summaries),
            hypergeometric_baselines=self.baselines(deck),
            generated_rules=tuple(rules),
            overfitting_validation=validations,
            warnings=(
                "Keep rules are model-based candidates, not universal or empirical facts.",
                "Follow-up placement comes from complete Structural Simulator games with forced public opening hands.",
                "Structural follow-up games are not comprehensive MTG rules-engine games.",
                "No external engine validation was performed.",
            ),
        )

    def validate_keep_rule_across_contexts(
        self,
        rule: GeneratedKeepRule,
        context: MulliganContext,
        *,
        samples: int,
    ) -> tuple[KeepRuleValidationResult, ...]:
        deck = self.deck(context.deck_id)
        baseline_policy = rule.policy
        pilot_names = (
            ("KorvoldPilot", "KorvoldSacrificePilot", "KorvoldConservativePilot")
            if context.deck_id == "korvold/current"
            else ("RogShaiPilot", "RogShaiTempoPilot", "RogShaiControlPilot")
        )
        contexts: list[tuple[str, str, MulliganContext, int, str]] = [
            ("primary", "primary_pod", context, 0, pilot_names[0]),
            ("holdout-a", "holdout_pod", context, 1, pilot_names[0]),
            ("holdout-b", "holdout_pod", context, 2, pilot_names[0]),
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
                pilot_names[0],
            ),
        ]
        contexts.extend(
            (
                f"pilot-{name}",
                "pilot_profile",
                context.model_copy(update={"pilot_profile_id": name}),
                0,
                name,
            )
            for name in pilot_names
        )
        output: list[KeepRuleValidationResult] = []
        for context_id, kind, test_context, holdout, pilot_name in contexts:
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
                            pilot_profile_id=pilot_name,
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
                        pilot_profile_id=pilot_name,
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
                    pilot_profile_id=pilot_name,
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

    def generate_keep_rules(
        self,
        context: MulliganContext,
        summaries: Iterable[MulliganPolicySummary],
        source_run_hash: str,
    ) -> list[GeneratedKeepRule]:
        best = min(
            summaries,
            key=lambda row: (row.structural_placement_mean or 99.0, row.average_mulligans),
        )
        if context.deck_id == "korvold/current":
            clauses = (
                KeepRuleClause(
                    feature="land_count",
                    operator="between",
                    value=(2.0, 4.0),
                    rationale="current Korvold land band",
                ),
                KeepRuleClause(
                    feature="colored_sources.G",
                    operator="ge",
                    value=1.0,
                    rationale="green is required for early ramp",
                ),
                KeepRuleClause(
                    feature="ramp_count",
                    operator="ge",
                    value=1.0,
                    rationale="supports a timely value window",
                ),
                KeepRuleClause(
                    feature="sacrifice_resource_count",
                    operator="ge",
                    value=1.0,
                    rationale="avoids ramp-only hands without sacrifice material",
                ),
            )
            exceptions = (
                "Two-land hands require functional acceleration or selection.",
                "Visible graveyard hate reduces graveyard-only keeps.",
            )
        else:
            clauses = (
                KeepRuleClause(
                    feature="land_count",
                    operator="between",
                    value=(2.0, 3.0),
                    rationale="current RogShai land band",
                ),
                KeepRuleClause(
                    feature="early_blue_source_count",
                    operator="ge",
                    value=1.0,
                    rationale="blue enables early interaction and Ishai support",
                ),
                KeepRuleClause(
                    feature="cheap_noncreature_count",
                    operator="ge",
                    value=1.0,
                    rationale="supports tempo and Ishai growth",
                ),
                KeepRuleClause(
                    feature="color_stability_score",
                    operator="ge",
                    value=0.66,
                    rationale="avoids unstable Jeskai starts",
                ),
            )
            exceptions = (
                "Offensive aura/payoff clusters need a protected Ishai window.",
                "Interaction-heavy matchups may keep slower hands with reserve counters.",
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
                    "multi_pilot_candidate",
                ),
                validation_status="candidate",
            )
        ]

    def test_rule(
        self,
        rule: GeneratedKeepRule,
        hand: OpeningHandFeatures,
    ) -> dict[str, object]:
        failures: list[str] = []
        data = hand.model_dump(mode="python")
        for clause in rule.clauses:
            value: object = data
            for part in clause.feature.split("."):
                value = value.get(part) if isinstance(value, dict) else None
            ok = False
            if clause.operator == "between" and isinstance(clause.value, tuple):
                ok = value is not None and clause.value[0] <= float(value) <= clause.value[1]
            elif clause.operator == "ge":
                ok = value is not None and float(value) >= float(clause.value)
            elif clause.operator == "le":
                ok = value is not None and float(value) <= float(clause.value)
            elif clause.operator == "eq":
                ok = value == clause.value
            elif clause.operator == "true":
                ok = value is True
            elif clause.operator == "false":
                ok = value is False
            if not ok:
                failures.append(clause.feature)
        return {
            "rule_id": rule.rule_id,
            "keep": not failures,
            "failed_clauses": failures,
            "model_based": True,
            "absolute_rule": False,
        }
