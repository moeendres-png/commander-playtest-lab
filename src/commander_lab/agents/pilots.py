from __future__ import annotations

import math
import random
from collections.abc import Iterable
from dataclasses import dataclass

from commander_lab.models import (
    CardRole,
    PilotActionView,
    PilotConfig,
    PilotDecision,
    PilotDecisionMode,
    PilotStateView,
    PilotStrength,
    PilotUtilityBreakdown,
    PilotUtilityWeights,
)
from commander_lab.models.roles import StructuralMechanic


@dataclass(frozen=True, slots=True)
class _StrengthPolicy:
    temperature: float
    mistake_rate: float
    reserve_mana_target: float
    shortlist: int
    precision: int


_STRENGTH_POLICIES: dict[PilotStrength, _StrengthPolicy] = {
    PilotStrength.WEAK: _StrengthPolicy(
        temperature=1.35, mistake_rate=0.18, reserve_mana_target=0.5, shortlist=8, precision=0
    ),
    PilotStrength.AVERAGE: _StrengthPolicy(
        temperature=0.75, mistake_rate=0.08, reserve_mana_target=1.0, shortlist=6, precision=1
    ),
    PilotStrength.STRONG: _StrengthPolicy(
        temperature=0.32, mistake_rate=0.02, reserve_mana_target=1.5, shortlist=4, precision=3
    ),
    PilotStrength.NEAR_OPTIMAL_HEURISTIC: _StrengthPolicy(
        temperature=0.12,
        mistake_rate=0.0,
        reserve_mana_target=2.0,
        shortlist=3,
        precision=6,
    ),
}


_GENERIC_WEIGHTS: dict[PilotStrength, PilotUtilityWeights] = {
    PilotStrength.WEAK: PilotUtilityWeights(
        survival=0.65,
        mana_efficiency=1.25,
        card_advantage=0.55,
        tempo=1.15,
        engine_development=0.75,
        interaction_reserve=0.25,
        commander_value=1.15,
        threat_reduction=0.65,
        win_progress=1.0,
        political_visibility=-0.15,
        rebuild_capacity=0.25,
    ),
    PilotStrength.AVERAGE: PilotUtilityWeights(
        survival=1.0,
        mana_efficiency=1.05,
        card_advantage=1.0,
        tempo=0.95,
        engine_development=1.0,
        interaction_reserve=0.85,
        commander_value=1.0,
        threat_reduction=1.0,
        win_progress=1.1,
        political_visibility=-0.5,
        rebuild_capacity=0.75,
    ),
    PilotStrength.STRONG: PilotUtilityWeights(
        survival=1.2,
        mana_efficiency=0.95,
        card_advantage=1.15,
        tempo=1.0,
        engine_development=1.1,
        interaction_reserve=1.15,
        commander_value=1.1,
        threat_reduction=1.2,
        win_progress=1.25,
        political_visibility=-0.7,
        rebuild_capacity=1.0,
    ),
    PilotStrength.NEAR_OPTIMAL_HEURISTIC: PilotUtilityWeights(
        survival=1.35,
        mana_efficiency=1.0,
        card_advantage=1.25,
        tempo=1.05,
        engine_development=1.2,
        interaction_reserve=1.35,
        commander_value=1.15,
        threat_reduction=1.3,
        win_progress=1.4,
        political_visibility=-0.85,
        rebuild_capacity=1.2,
    ),
}


def _package_ids(action: PilotActionView) -> frozenset[str]:
    raw = action.metadata.get("package_ids", "")
    return frozenset(part for part in str(raw).split("|") if part)


class BasePilot:
    """Pure structural action evaluator.

    The pilot only ranks validated action descriptions. It never mutates game state.
    """

    pilot_name = "GenericCommanderPilot"

    def __init__(self, config: PilotConfig | None = None) -> None:
        self.config = config or PilotConfig(pilot_name=self.pilot_name)
        self.policy = _STRENGTH_POLICIES[self.config.strength]
        self.weights = self.config.weights or self.default_weights(self.config.strength)
        self.temperature = self.config.temperature or self.policy.temperature
        self.mistake_rate = (
            self.policy.mistake_rate
            if self.config.mistake_rate is None
            else self.config.mistake_rate
        )
        self.reserve_mana_target = (
            self.policy.reserve_mana_target
            if self.config.reserve_mana_target is None
            else self.config.reserve_mana_target
        )

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        return _GENERIC_WEIGHTS[strength]

    def opening_hand_score(
        self,
        cards: Iterable[PilotActionView],
        *,
        commander_names: tuple[str, ...] = (),
    ) -> float:
        card_list = list(cards)
        lands = sum(bool(card.metadata.get("is_land", False)) for card in card_list)
        early_ramp = sum(card.strength(CardRole.RAMP) for card in card_list if card.mana_cost <= 2)
        early_velocity = sum(
            card.strength(CardRole.DRAW) + card.strength(CardRole.SELECTION)
            for card in card_list
            if card.mana_cost <= 2
        )
        early_interaction = sum(
            card.strength(CardRole.REMOVAL)
            + card.strength(CardRole.COUNTER)
            + card.strength(CardRole.PROTECTION)
            for card in card_list
            if card.mana_cost <= 2
        )
        expensive = sum(card.mana_cost >= 5 for card in card_list)
        land_score = 2.4 - abs(3 - lands) * 1.1
        if lands < 2 or lands > 5:
            land_score -= 2.5
        score = land_score
        score += min(2.0, early_ramp * 0.8)
        score += min(1.5, early_velocity * 0.55)
        score += min(1.2, early_interaction * 0.35)
        score -= expensive * 0.45
        score += self.opening_hand_specialist_bonus(card_list, commander_names)
        return score

    def opening_hand_specialist_bonus(
        self,
        cards: list[PilotActionView],
        commander_names: tuple[str, ...],
    ) -> float:
        del cards, commander_names
        return 0.0

    def should_keep_opening_hand(
        self,
        cards: Iterable[PilotActionView],
        *,
        mulligans: int,
        free_first: bool,
        commander_names: tuple[str, ...],
        rng: random.Random,
    ) -> tuple[bool, float]:
        score = self.opening_hand_score(cards, commander_names=commander_names)
        thresholds = {
            PilotStrength.WEAK: 1.6,
            PilotStrength.AVERAGE: 2.3,
            PilotStrength.STRONG: 2.8,
            PilotStrength.NEAR_OPTIMAL_HEURISTIC: 3.1,
        }
        threshold = thresholds[self.config.strength]
        effective_mulligans = max(0, mulligans - (1 if free_first and mulligans > 0 else 0))
        threshold -= effective_mulligans * 0.55
        if self.config.mode == PilotDecisionMode.DETERMINISTIC:
            return score >= threshold, score
        probability = self._logistic((score - threshold) / max(0.1, self.temperature))
        if self.mistake_rate and rng.random() < self.mistake_rate:
            probability = 1.0 - probability
        return rng.random() < probability, score

    def choose_bottom_cards(
        self,
        cards: Iterable[PilotActionView],
        count: int,
        *,
        commander_names: tuple[str, ...],
    ) -> tuple[str, ...]:
        if count <= 0:
            return ()
        card_list = list(cards)
        scored = sorted(
            card_list,
            key=lambda card: (
                self.opening_card_value(card, commander_names),
                -card.mana_cost,
                card.action_id,
            ),
        )
        return tuple(card.action_id for card in scored[:count])

    def opening_card_value(
        self,
        card: PilotActionView,
        commander_names: tuple[str, ...],
    ) -> float:
        del commander_names
        if bool(card.metadata.get("is_land", False)):
            return 2.2
        value = card.floor_value + card.immediate_impact
        if card.mana_cost <= 2:
            value += card.strength(CardRole.RAMP) * 1.4
            value += card.strength(CardRole.DRAW) * 0.8
            value += card.strength(CardRole.SELECTION) * 0.7
            value += card.strength(CardRole.REMOVAL) * 0.45
            value += card.strength(CardRole.COUNTER) * 0.35
            value += card.strength(CardRole.PROTECTION) * 0.35
        value -= max(0.0, card.mana_cost - 4.0) * 0.45
        value -= card.turn_cycle_risk * 0.25
        return value

    def evaluate_action(
        self, state: PilotStateView, action: PilotActionView
    ) -> PilotUtilityBreakdown:
        components = self._base_components(state, action)
        specialist_bonus = self.specialist_bonus(state, action, components)
        weighted = sum(components[name] * weight for name, weight in self.weights.as_dict().items())
        total = weighted + specialist_bonus
        return PilotUtilityBreakdown(
            **components,
            specialist_bonus=specialist_bonus,
            total_utility=total,
        )

    def choose_action(
        self,
        state: PilotStateView,
        actions: Iterable[PilotActionView],
        rng: random.Random,
    ) -> PilotDecision:
        candidates = list(actions)
        if not candidates:
            return PilotDecision(
                pilot_name=self.pilot_name,
                strength=self.config.strength,
                mode=self.config.mode,
            )
        scored = [(action, self.evaluate_action(state, action)) for action in candidates]
        scored.sort(key=lambda item: (item[1].total_utility, item[0].action_id), reverse=True)
        scored = scored[: self.policy.shortlist]
        selected_action, selected_breakdown = self._select(scored, rng)
        return PilotDecision(
            pilot_name=self.pilot_name,
            strength=self.config.strength,
            mode=self.config.mode,
            selected_action_id=selected_action.action_id,
            selected_utility=selected_breakdown.total_utility,
            candidates=tuple(
                (action.action_id, breakdown.total_utility) for action, breakdown in scored
            ),
            selected_breakdown=selected_breakdown,
        )

    def should_take_reaction(
        self,
        state: PilotStateView,
        action: PilotActionView,
        rng: random.Random,
        *,
        threshold: float = 0.5,
    ) -> tuple[bool, PilotUtilityBreakdown]:
        breakdown = self.evaluate_action(state, action)
        if self.config.mode == PilotDecisionMode.DETERMINISTIC:
            return breakdown.total_utility >= threshold, breakdown
        probability = self._logistic(
            (breakdown.total_utility - threshold) / max(0.05, self.temperature)
        )
        if rng.random() < self.mistake_rate:
            probability = 1.0 - probability
        return rng.random() < probability, breakdown

    def choose_combat_target(
        self,
        state: PilotStateView,
        actions: Iterable[PilotActionView],
        rng: random.Random,
    ) -> PilotDecision:
        return self.choose_action(state, actions, rng)

    def choose_target(
        self,
        state: PilotStateView,
        actions: Iterable[PilotActionView],
        rng: random.Random,
    ) -> PilotDecision:
        return self.choose_action(state, actions, rng)

    def specialist_bonus(
        self,
        state: PilotStateView,
        action: PilotActionView,
        components: dict[str, float],
    ) -> float:
        del state, action, components
        return 0.0

    def _select(
        self,
        scored: list[tuple[PilotActionView, PilotUtilityBreakdown]],
        rng: random.Random,
    ) -> tuple[PilotActionView, PilotUtilityBreakdown]:
        if self.config.mode == PilotDecisionMode.DETERMINISTIC:
            precision = self.policy.precision
            return max(
                scored,
                key=lambda item: (
                    round(item[1].total_utility, precision),
                    -item[0].mana_cost,
                    item[0].action_id,
                ),
            )
        if self.mistake_rate and rng.random() < self.mistake_rate:
            return scored[rng.randrange(len(scored))]
        best = max(item[1].total_utility for item in scored)
        logits = [
            math.exp(max(-40.0, (item[1].total_utility - best) / self.temperature))
            for item in scored
        ]
        total = sum(logits)
        roll = rng.random() * total
        cumulative = 0.0
        for item, weight in zip(scored, logits, strict=True):
            cumulative += weight
            if roll <= cumulative:
                return item
        return scored[-1]

    def _base_components(self, state: PilotStateView, action: PilotActionView) -> dict[str, float]:
        roles = action.roles
        mechanics = action.mechanic_tags
        opponent_count = max(0, state.pod_size - 1)
        life_pressure = max(0.0, (22.0 - state.life) / 10.0)
        enemy_pressure = max(0.0, state.enemy_board_total - state.board_power - state.engine_value)
        max_threat = max(action.target_threat, state.max_opponent_threat)
        remaining_mana = max(0.0, action.remaining_mana)
        interaction_roles = {CardRole.COUNTER, CardRole.PROTECTION, CardRole.REMOVAL}
        interaction_in_hand = sum(state.role_counts.get(role, 0) for role in interaction_roles)
        exposure_ratio = (
            state.exposure_before_next_turn / max(1, opponent_count) if opponent_count else 0.0
        )
        uncertainty = state.uncertainty_pressure
        all_in_exposure = float(action.metadata.get("all_in_exposure", 0.0))
        board_exposure = float(action.metadata.get("increases_board_exposure", 0.0))
        protected_finish = bool(action.metadata.get("protected_finish_window", False))
        expected_lethals = int(action.metadata.get("expected_lethal_opponents", 0))

        survival = 0.0
        survival += action.strength(CardRole.PROTECTION) * (1.5 + life_pressure)
        survival += action.strength(CardRole.WIPE) * min(3.0, enemy_pressure * 0.18)
        survival += action.strength(CardRole.REMOVAL) * min(2.5, max_threat * 0.12)
        survival += action.strength(CardRole.COUNTER) * min(2.5, action.threat_score * 0.3)
        graveyard_pressure = (
            action.threat_score
            if action.action_kind == "graveyard_target"
            else state.max_graveyard_pressure
        )
        survival += action.strength(CardRole.GRAVEYARD_HATE) * min(2.0, graveyard_pressure * 0.12)
        if action.action_kind == "commander" and life_pressure > 0.6:
            survival -= 0.5
        if action.action_kind == "commander":
            survival -= state.commander_denial_risk * (0.45 + 0.85 * exposure_ratio)
            survival -= state.boardwipe_risk * board_exposure * 0.8
            survival -= all_in_exposure * (0.25 + uncertainty * 0.65)
        elif board_exposure > 0.0:
            survival -= state.boardwipe_risk * board_exposure * 0.55

        raw_value = (
            action.floor_value
            + action.immediate_impact
            + sum(action.role_strengths.values()) * 0.35
            + action.base_power * 0.08
        )
        target_only = action.action_kind in {
            "combat_target",
            "removal_target",
            "graveyard_target",
        }
        mana_efficiency = (
            0.0
            if action.action_kind == "pass" or target_only
            else raw_value / max(0.75, action.mana_cost)
        )
        if CardRole.RAMP in roles:
            mana_efficiency += action.strength(CardRole.RAMP) * max(0.2, 1.7 - state.turn * 0.14)
        if action.mana_cost == 0 and action.action_kind != "pass":
            mana_efficiency += 1.0

        card_advantage = (
            action.strength(CardRole.DRAW) * (1.5 if state.hand_size <= 4 else 0.9)
            + action.strength(CardRole.SELECTION) * 0.8
            + action.strength(CardRole.RECURSION) * min(2.0, state.graveyard_size * 0.15)
            + action.strength(CardRole.ENGINE) * 0.45
        )

        tempo = (
            action.immediate_impact * 0.35
            if action.action_kind == "pass"
            else action.immediate_impact * 1.15 + max(0.0, 2.5 - action.mana_cost) * 0.18
        )
        tempo += action.strength(CardRole.REMOVAL) * min(2.0, action.target_threat * 0.15)
        tempo += action.strength(CardRole.COUNTER) * min(2.0, action.threat_score * 0.25)
        tempo += action.strength(CardRole.RAMP) * max(0.0, 1.4 - state.turn * 0.12)
        tempo -= action.turn_cycle_risk * 0.7

        package_density = (
            state.role_counts.get(CardRole.ENABLER, 0)
            + state.role_counts.get(CardRole.TOKEN_SOURCE, 0)
            + state.role_counts.get(CardRole.LAND_SYNERGY, 0)
            + state.role_counts.get(CardRole.SACRIFICE_OUTLET, 0)
        )
        engine_development = (
            action.strength(CardRole.ENGINE) * (1.45 if state.turn <= 7 else 0.9)
            + action.strength(CardRole.ENABLER) * 0.7
            + action.strength(CardRole.TOKEN_SOURCE) * 0.8
            + action.strength(CardRole.PAYOFF) * min(2.2, package_density * 0.18)
        )
        if StructuralMechanic.TOKEN_ENGINE in mechanics:
            engine_development += 0.45 + min(0.8, state.tokens * 0.08)
        if StructuralMechanic.ARTIFACT_ENGINE in mechanics:
            engine_development += 0.45
        if StructuralMechanic.GO_WIDE in mechanics:
            engine_development += 0.25 + min(0.8, state.tokens * 0.06)

        if self.reserve_mana_target > 0 and interaction_in_hand:
            reserve_ratio = min(1.5, remaining_mana / self.reserve_mana_target)
            interaction_reserve = max(-0.8, reserve_ratio * 0.8 - 0.4)
        else:
            interaction_reserve = 0.0
        if action.action_kind == "pass" and interaction_in_hand:
            preserve_bonus = {
                PilotStrength.WEAK: 0.0,
                PilotStrength.AVERAGE: 0.3,
                PilotStrength.STRONG: 0.55,
                PilotStrength.NEAR_OPTIMAL_HEURISTIC: 1.2,
            }[self.config.strength]
            threat_context = min(1.35, 0.35 + state.max_opponent_threat * 0.08 + state.turn * 0.025)
            interaction_reserve += preserve_bonus * threat_context
            if bool(action.metadata.get("flexible_interaction", False)):
                interaction_reserve += uncertainty * (0.9 + exposure_ratio * 0.65)
                interaction_reserve += state.stack_pressure * 0.35
        if roles.intersection(interaction_roles) and action.action_kind in {"card", "commander"}:
            interaction_reserve -= 0.7
        if action.action_kind in {"counter", "protection"}:
            interaction_reserve += min(2.5, action.threat_score * 0.22)
            urgency = min(1.0, action.threat_score / 8.0)
            if not bool(action.metadata.get("known_win_attempt", False)):
                interaction_reserve -= (1.0 - urgency) * uncertainty * (1.2 + 0.7 * exposure_ratio)
        if interaction_in_hand == 0:
            interaction_reserve *= 0.35

        commander_value = action.commander_synergy * (1.3 if state.commander_online else 0.75)
        if action.action_kind == "commander":
            commander_value += 1.2 + action.base_power * 0.15
        if CardRole.COMBAT_PAYOFF in roles and state.commander_online:
            commander_value += action.strength(CardRole.COMBAT_PAYOFF) * 1.15
        if StructuralMechanic.COMMANDER_DAMAGE_SUPPORT in mechanics:
            commander_value += 1.0 if state.commander_online else -0.45
        if (
            StructuralMechanic.COMMANDER_DEPENDENT in mechanics
            and not state.commander_online
            and action.action_kind != "commander"
        ):
            commander_value -= 0.6
        if StructuralMechanic.COMMANDER_INDEPENDENT in mechanics and not state.commander_online:
            commander_value += 0.35
        if CardRole.PROTECTION in roles and state.commander_online:
            max_commander_power = max(
                (commander.power for commander in state.commanders if commander.on_battlefield),
                default=0.0,
            )
            commander_value += action.strength(CardRole.PROTECTION) * (
                0.6 + max_commander_power * 0.08
            )

        threat_reduction = (
            action.strength(CardRole.REMOVAL) * min(3.0, action.target_threat * 0.2)
            + action.strength(CardRole.WIPE) * min(4.0, enemy_pressure * 0.16)
            + action.strength(CardRole.COUNTER) * min(3.0, action.threat_score * 0.3)
            + action.strength(CardRole.GRAVEYARD_HATE) * min(2.5, graveyard_pressure * 0.13)
        )
        if state.archenemy_player_id and action.target_player_id == state.archenemy_player_id:
            threat_reduction += 0.45 + min(0.55, action.target_threat * 0.05)

        lethal_pressure = max(0.0, (22.0 - state.lowest_opponent_life) / 7.0)
        win_progress = (
            action.strength(CardRole.FINISHER) * (1.3 + lethal_pressure)
            + action.strength(CardRole.COMBAT_PAYOFF)
            * (0.6 + (0.8 if state.commander_online else 0.0))
            + action.strength(CardRole.PAYOFF) * 0.45
            + action.base_power * 0.12
            + action.multiplayer_scaling * opponent_count * 0.25
        )
        if action.action_kind == "combat_target":
            win_progress += max(0.0, 18.0 - float(action.metadata.get("target_life", 40.0))) * 0.12
            win_progress += float(action.metadata.get("commander_damage_pressure", 0.0)) * 0.18
        if StructuralMechanic.TABLE_DAMAGE in mechanics:
            win_progress += max(0, opponent_count - 1) * (
                0.35 + max(0.0, action.multiplayer_scaling) * 0.18
            )
        if StructuralMechanic.FINISHER_COMPRESSION in mechanics:
            win_progress += 0.65 + max(0, opponent_count - 1) * 0.22
        if StructuralMechanic.COMMANDER_DAMAGE_SUPPORT in mechanics and state.commander_online:
            win_progress += 0.55
        if StructuralMechanic.COMMANDER_DEPENDENT in mechanics and not state.commander_online:
            # Commander-dependent payoffs should not retain their full finishing
            # value after the commander has been removed.  This keeps collateral
            # table-damage/combat payoffs distinct from independent finish axes.
            win_progress *= 0.35
        if expected_lethals > 0:
            win_progress += min(4.5, expected_lethals * 1.35)
            if protected_finish:
                win_progress += 0.9
        finish_probability = float(action.metadata.get("finish_probability", 1.0))
        if CardRole.FINISHER in roles and expected_lethals == 0 and finish_probability < 0.2:
            win_progress -= 1.8

        political_visibility = (
            action.strength(CardRole.ENGINE) * (1.0 - action.immediate_impact * 0.35)
            + action.strength(CardRole.PAYOFF) * 0.75
            + action.strength(CardRole.FINISHER) * 0.8
            + max(0.0, action.base_power - 4.0) * 0.13
            + action.multiplayer_scaling * opponent_count * 0.18
        )
        if action.action_kind in {"counter", "protection"}:
            political_visibility *= 0.4
        if CardRole.WIPE in roles:
            political_visibility += 0.55
        political_visibility += board_exposure * (0.45 + state.boardwipe_risk * 0.35)
        if state.actor_is_archenemy:
            political_visibility += max(0.0, board_exposure) * 0.75

        rebuild_capacity = (
            action.strength(CardRole.RECURSION) * 1.4
            + action.strength(CardRole.DRAW) * 0.75
            + action.strength(CardRole.LAND_SYNERGY) * 0.65
            + action.strength(CardRole.ENGINE) * max(0.0, 0.8 - action.turn_cycle_risk * 0.5)
            + action.strength(CardRole.PROTECTION) * 0.6
        )
        if StructuralMechanic.REBUILD in mechanics:
            rebuild_capacity += 1.2
        if StructuralMechanic.LAND_RECURSION in mechanics:
            rebuild_capacity += 0.9 + min(0.8, state.graveyard_size * 0.04)
        if StructuralMechanic.GRAVEYARD_RECURSION in mechanics:
            rebuild_capacity += 0.75 + min(0.8, state.graveyard_size * 0.035)
        if StructuralMechanic.COMMANDER_INDEPENDENT in mechanics and not state.commander_online:
            rebuild_capacity += 0.35
        if bool(action.metadata.get("preserves_rebuild", False)):
            rebuild_capacity += 0.8 + state.boardwipe_risk * 0.9
        if StructuralMechanic.REBUILD in mechanics:
            rebuild_capacity += state.boardwipe_risk * 0.65
        if StructuralMechanic.COMMANDER_INDEPENDENT in mechanics:
            rebuild_capacity += state.commander_denial_risk * 0.35

        return {
            "survival": survival,
            "mana_efficiency": mana_efficiency,
            "card_advantage": card_advantage,
            "tempo": tempo,
            "engine_development": engine_development,
            "interaction_reserve": interaction_reserve,
            "commander_value": commander_value,
            "threat_reduction": threat_reduction,
            "win_progress": win_progress,
            "political_visibility": political_visibility,
            "rebuild_capacity": rebuild_capacity,
        }

    @staticmethod
    def _logistic(value: float) -> float:
        if value >= 0:
            exp = math.exp(-min(40.0, value))
            return 1.0 / (1.0 + exp)
        exp = math.exp(min(40.0, value))
        return exp / (1.0 + exp)


class KorvoldPilot(BasePilot):
    pilot_name = "KorvoldPilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = _GENERIC_WEIGHTS[strength].model_dump()
        base.update(
            engine_development=base["engine_development"] + 0.2,
            commander_value=base["commander_value"] + 0.25,
            rebuild_capacity=base["rebuild_capacity"] + 0.25,
            win_progress=base["win_progress"] + 0.15,
        )
        return PilotUtilityWeights(**base)

    def opening_hand_specialist_bonus(
        self,
        cards: list[PilotActionView],
        commander_names: tuple[str, ...],
    ) -> float:
        del commander_names
        land_synergy = sum(card.strength(CardRole.LAND_SYNERGY) for card in cards)
        token_sources = sum(card.strength(CardRole.TOKEN_SOURCE) for card in cards)
        outlets = sum(card.strength(CardRole.SACRIFICE_OUTLET) for card in cards)
        ramp = sum(card.strength(CardRole.RAMP) for card in cards if card.mana_cost <= 2)
        protection = sum(card.strength(CardRole.PROTECTION) for card in cards)
        bonus = min(1.2, land_synergy * 0.25) + min(1.0, ramp * 0.35)
        if token_sources and outlets:
            bonus += 0.9
        if protection:
            bonus += 0.25
        return bonus

    def opening_card_value(
        self,
        card: PilotActionView,
        commander_names: tuple[str, ...],
    ) -> float:
        value = super().opening_card_value(card, commander_names)
        value += card.strength(CardRole.RAMP) * 0.45
        value += card.strength(CardRole.LAND_SYNERGY) * 0.35
        value += card.strength(CardRole.TOKEN_SOURCE) * 0.25
        value += card.strength(CardRole.SACRIFICE_OUTLET) * 0.3
        value += card.strength(CardRole.PROTECTION) * 0.2
        return value

    def specialist_bonus(
        self,
        state: PilotStateView,
        action: PilotActionView,
        components: dict[str, float],
    ) -> float:
        del components
        names = set(state.battlefield_names)
        commander = next(
            (item for item in state.commanders if item.name == "Korvold, Fae-Cursed King"), None
        )
        korvold_online = bool(commander and commander.on_battlefield)
        sacrifice_material = state.tokens + state.resources * 0.55
        sacrifice_material += state.role_counts.get(CardRole.TOKEN_SOURCE, 0) * 0.45
        outlets = state.role_counts.get(CardRole.SACRIFICE_OUTLET, 0)
        land_package = state.role_counts.get(CardRole.LAND_SYNERGY, 0)
        bonus = 0.0
        exposure_ratio = state.exposure_before_next_turn / max(1, state.pod_size - 1)

        if action.action_kind == "commander" and action.card_name == "Korvold, Fae-Cursed King":
            immediate_value = sacrifice_material + outlets * 0.8 + land_package * 0.35
            bonus += min(4.5, immediate_value * 0.42)
            if (
                state.mana_available - action.mana_cost >= 1.0
                or "Lightning Greaves" in names
                or "Swiftfoot Boots" in names
            ):
                bonus += 0.8
            if immediate_value < 1.0:
                bonus -= 4.85
                if state.mana_available - action.mana_cost < 1.0 and not (
                    {"Lightning Greaves", "Swiftfoot Boots"} & names
                ):
                    bonus -= 1.0
            protected_window = bool(action.metadata.get("protected_window", False)) or bool(
                {"Lightning Greaves", "Swiftfoot Boots"} & names
            )
            denial_penalty = state.commander_denial_risk * (1.4 + 1.5 * exposure_ratio)
            if protected_window:
                denial_penalty *= 0.35
            bonus -= denial_penalty
            bonus -= (
                state.boardwipe_risk
                * float(action.metadata.get("increases_board_exposure", 0.45))
                * 1.1
            )
        if CardRole.SACRIFICE_OUTLET in action.roles:
            bonus += 0.7 + min(2.0, sacrifice_material * 0.3)
            if korvold_online:
                bonus += 1.0
        if CardRole.TOKEN_SOURCE in action.roles:
            bonus += 0.45 + outlets * 0.25 + (0.6 if korvold_online else 0.0)
        if CardRole.LAND_SYNERGY in action.roles:
            bonus += 0.35 + min(1.4, land_package * 0.18)
            if action.card_name in {"Splendid Reclamation", "Aftermath Analyst"}:
                bonus += min(2.2, state.graveyard_size * 0.11)
        if CardRole.PROTECTION in action.roles and korvold_online:
            bonus += 1.1 + max(0.0, (commander.power - 4.0) * 0.12 if commander else 0.0)
        if action.action_kind == "protection":
            protected_value = float(action.metadata.get("protected_permanent_value", 4.0))
            protecting_commander = bool(action.metadata.get("protecting_commander", False))
            if protecting_commander:
                bonus += 1.0 + min(1.5, protected_value * 0.08)
            elif protected_value <= 2.0:
                bonus -= 6.2 + state.uncertainty_pressure * 1.2
            elif protected_value < 4.0:
                bonus -= 1.6
        if CardRole.GRAVEYARD_HATE in action.roles:
            bonus += min(1.8, state.max_graveyard_pressure * 0.12)
        if CardRole.ENGINE in action.roles and not korvold_online:
            bonus += action.floor_value * 0.45
        if CardRole.RECURSION in action.roles:
            bonus += min(1.6, state.graveyard_size * 0.09)
        if StructuralMechanic.SACRIFICE_PAYOFF in action.mechanic_tags:
            bonus += min(1.3, sacrifice_material * 0.16 + outlets * 0.18)
        if "sacrifice_material_quality" in action.metadata:
            bonus += float(action.metadata["sacrifice_material_quality"]) * 0.65
        if StructuralMechanic.REBUILD in action.mechanic_tags and state.board_power <= 4.0:
            bonus += 0.75 + min(1.0, state.graveyard_size * 0.05)
        if StructuralMechanic.COMMANDER_INDEPENDENT in action.mechanic_tags and not korvold_online:
            bonus += 0.45
        if StructuralMechanic.TABLE_DAMAGE in action.mechanic_tags:
            bonus += max(0, state.pod_size - 3) * 0.32
        if action.card_name in {
            "Mirkwood Bats",
            "Exsanguinate",
            "Massacre Wurm",
            "Hearthhull, the Worldseed",
        }:
            bonus += 0.9 + max(0, state.pod_size - 3) * 0.35
        expected_lethals = int(action.metadata.get("expected_lethal_opponents", 0))
        if expected_lethals:
            bonus += min(3.0, expected_lethals * 0.85)
        if (
            CardRole.FINISHER in action.roles
            and expected_lethals == 0
            and float(action.metadata.get("finish_probability", 1.0)) < 0.2
        ):
            bonus -= 2.0
        if (CardRole.COMBAT_PAYOFF in action.roles or action.base_power >= 5) and korvold_online:
            bonus += 0.4
        all_in_exposure = float(action.metadata.get("all_in_exposure", 0.0))
        if all_in_exposure >= 0.65 and state.uncertainty_pressure >= 0.6 and exposure_ratio >= 0.75:
            bonus -= all_in_exposure * (3.3 + state.uncertainty_pressure * 1.2)
        if (
            action.action_kind == "commander"
            and all_in_exposure >= 0.75
            and state.commander_denial_risk >= 0.6
        ):
            bonus -= 1.8 + state.commander_denial_risk * exposure_ratio * 1.8
        if action.action_kind == "combat_target":
            pressure = float(action.metadata.get("commander_damage_pressure", 0.0))
            bonus += pressure * 0.28
        return bonus


class RogShaiPilot(BasePilot):
    pilot_name = "RogShaiPilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = _GENERIC_WEIGHTS[strength].model_dump()
        base.update(
            interaction_reserve=base["interaction_reserve"] + 0.35,
            commander_value=base["commander_value"] + 0.3,
            win_progress=base["win_progress"] + 0.25,
            tempo=base["tempo"] + 0.1,
        )
        return PilotUtilityWeights(**base)

    def opening_hand_specialist_bonus(
        self,
        cards: list[PilotActionView],
        commander_names: tuple[str, ...],
    ) -> float:
        del commander_names
        cheap_noncreature = sum(
            card.mana_cost <= 2
            and not bool(card.metadata.get("is_creature", False))
            and not bool(card.metadata.get("is_land", False))
            for card in cards
        )
        protection = sum(card.strength(CardRole.PROTECTION) for card in cards)
        counters = sum(card.strength(CardRole.COUNTER) for card in cards)
        combat_draw = sum(
            card.card_name in {"Combat Research", "Curiosity", "Staggering Insight"}
            for card in cards
        )
        bonus = min(1.3, cheap_noncreature * 0.22)
        bonus += min(0.9, (protection + counters) * 0.3)
        if combat_draw and not (protection or counters):
            bonus -= 0.35
        return bonus

    def opening_card_value(
        self,
        card: PilotActionView,
        commander_names: tuple[str, ...],
    ) -> float:
        value = super().opening_card_value(card, commander_names)
        if card.mana_cost <= 2 and not bool(card.metadata.get("is_land", False)):
            value += 0.3
        value += card.strength(CardRole.COUNTER) * 0.3
        value += card.strength(CardRole.PROTECTION) * 0.35
        value += card.strength(CardRole.SELECTION) * 0.25
        if card.card_name in {"Combat Research", "Curiosity", "Staggering Insight"}:
            value -= 0.2
        return value

    def specialist_bonus(
        self,
        state: PilotStateView,
        action: PilotActionView,
        components: dict[str, float],
    ) -> float:
        del components
        names = set(state.battlefield_names)
        ishai = next(
            (item for item in state.commanders if item.name == "Ishai, Ojutai Dragonspeaker"), None
        )
        rograkh = next(
            (item for item in state.commanders if item.name == "Rograkh, Son of Rohgahh"), None
        )
        ishai_online = bool(ishai and ishai.on_battlefield)
        rograkh_online = bool(rograkh and rograkh.on_battlefield)
        reserve_after = action.remaining_mana
        has_protection = state.role_counts.get(CardRole.PROTECTION, 0) > 0
        has_counter = state.role_counts.get(CardRole.COUNTER, 0) > 0
        spellslinger_online = bool(
            {"Kykar, Wind's Fury", "Whirlwind of Thought", "Storm-Kiln Artist", "Guttersnipe"}
            & names
        )
        bonus = 0.0
        exposure_ratio = state.exposure_before_next_turn / max(1, state.pod_size - 1)

        if action.action_kind == "commander" and action.card_name == "Rograkh, Son of Rohgahh":
            bonus += 1.8
            if state.turn <= 2:
                bonus += 1.0
            if "Springleaf Drum" in state.hand_names or "Relic of Legends" in state.hand_names:
                bonus += 0.8
        if action.action_kind == "commander" and action.card_name == "Ishai, Ojutai Dragonspeaker":
            bonus += 0.55 * max(1, state.pod_size - 1)
            protected_window = reserve_after >= 1.0 and (has_protection or has_counter)
            if protected_window:
                bonus += 1.4
            elif state.max_opponent_threat >= 7.0:
                bonus -= 0.9
            denial_penalty = state.commander_denial_risk * (2.0 + 2.0 * exposure_ratio)
            if protected_window:
                denial_penalty *= 0.35
            bonus -= denial_penalty
            if reserve_after < 1.0 and (has_protection or has_counter):
                bonus -= 1.4 + exposure_ratio * 1.2
            bonus -= (
                state.boardwipe_risk
                * float(action.metadata.get("increases_board_exposure", 0.45))
                * 1.2
            )
            if ishai and ishai.next_cost >= 7.0 and not protected_window:
                bonus -= min(2.5, (ishai.next_cost - 4.0) * 0.45)
        if action.card_name in {"Combat Research", "Curiosity", "Staggering Insight"}:
            if ishai_online:
                bonus += 1.4 + (ishai.power if ishai else 1.0) * 0.08
                if reserve_after >= 1.0 or has_protection:
                    bonus += 0.8
                # Do not expose a combat-draw aura into a developed hostile
                # engine/interaction window when doing so consumes the reserve.
                if state.max_opponent_threat >= 9.0 and reserve_after < 1.0:
                    bonus -= 10.0
                elif state.max_opponent_threat >= 9.0:
                    bonus -= 7.5
                elif state.max_opponent_threat >= 8.0 and reserve_after < 1.0:
                    bonus -= 9.0
                elif (
                    state.max_opponent_threat >= 7.0 and reserve_after < 1.0 and not has_protection
                ):
                    bonus -= 5.0
            else:
                bonus -= 2.0 if rograkh_online else 6.0
        if action.card_name == "Jeska, Thrice Reborn":
            if ishai_online:
                bonus += 1.0 + max(0.0, (ishai.power - 5.0) * 0.22 if ishai else 0.0)
            else:
                bonus -= 1.0
            expected_lethals = int(action.metadata.get("expected_lethal_opponents", 0))
            protected_finish = bool(action.metadata.get("protected_finish_window", False))
            if expected_lethals > 0:
                bonus += 1.6 + min(1.8, expected_lethals * 0.7)
                if protected_finish:
                    bonus += 0.8
            elif (
                "expected_lethal_opponents" in action.metadata
                or "protected_finish_window" in action.metadata
            ) and not protected_finish:
                bonus -= 4.8 + state.uncertainty_pressure * 1.2
        if action.card_name == "Kediss, Emberclaw Familiar":
            if ishai_online:
                bonus += 0.9 + max(0, state.pod_size - 2) * 0.35
            else:
                # Kediss needs a commander that actually connects; Rograkh is
                # not a meaningful substitute for an offline Ishai damage axis.
                bonus -= 2.2
        if StructuralMechanic.COMMANDER_DAMAGE_SUPPORT in action.mechanic_tags:
            bonus += 0.65 + (0.35 if ishai_online else -0.9)
        if StructuralMechanic.TABLE_DAMAGE in action.mechanic_tags and ishai_online:
            bonus += max(0, state.pod_size - 3) * 0.4
        if StructuralMechanic.COMMANDER_INDEPENDENT in action.mechanic_tags and not ishai_online:
            bonus += 0.5
        if action.card_name in {
            "Duelist's Heritage",
            "Psychotic Fury",
            "Boros Charm",
            "Sunhome, Fortress of the Legion",
        }:
            if ishai_online:
                bonus += 0.8 + max(0.0, (ishai.power - 4.0) * 0.12 if ishai else 0.0)
            else:
                bonus -= 0.35
        if CardRole.PROTECTION in action.roles:
            if ishai_online:
                bonus += 1.0 + max(0.0, (ishai.power - 4.0) * 0.1 if ishai else 0.0)
            if action.action_kind == "protection":
                bonus += min(2.0, action.threat_score * 0.2)
                protected_value = float(action.metadata.get("protected_permanent_value", 4.0))
                if bool(action.metadata.get("protecting_commander", False)):
                    bonus += 1.0 + min(1.8, protected_value * 0.1)
                elif protected_value <= 2.0:
                    bonus -= 4.0
                else:
                    bonus -= max(0.0, 4.0 - protected_value) * 0.5
        if CardRole.COUNTER in action.roles:
            if reserve_after < 1.0 and action.action_kind == "card":
                bonus -= 1.0
            if action.action_kind == "counter":
                bonus += min(2.4, action.threat_score * 0.25)
                if bool(action.metadata.get("known_win_attempt", False)):
                    bonus += 1.3
                elif action.threat_score <= 3.0:
                    bonus -= 2.6 + state.uncertainty_pressure * 1.6 + exposure_ratio * 0.55
        if action.action_kind == "pass" and (has_counter or has_protection):
            # In uncertain/high-threat pods, holding flexible interaction is a
            # positive action rather than a zero-value non-action.
            bonus += max(0.0, state.max_opponent_threat - 6.0) * 0.55
        if action.card_name in {
            "Kykar, Wind's Fury",
            "Veyran, Voice of Duality",
            "Whirlwind of Thought",
            "Storm-Kiln Artist",
            "Guttersnipe",
        }:
            bonus += 0.45
            if not ishai_online or spellslinger_online:
                bonus += 0.55
            bonus += state.commander_denial_risk * 1.1
            bonus += state.boardwipe_risk * (
                0.45 if StructuralMechanic.COMMANDER_INDEPENDENT in action.mechanic_tags else 0.0
            )
        if (
            not ishai_online
            and action.roles.intersection({CardRole.ENGINE, CardRole.DRAW})
            and action.floor_value >= 0.7
        ):
            bonus += 0.35
        if rograkh_online and action.card_name in {"Springleaf Drum", "Relic of Legends"}:
            bonus += 0.7
        if action.action_kind == "combat_target":
            pressure = float(action.metadata.get("commander_damage_pressure", 0.0))
            bonus += pressure * 0.42
            if float(action.metadata.get("target_life", 40.0)) <= 12.0:
                bonus += 0.8
            if state.archenemy_player_id and action.target_player_id == state.archenemy_player_id:
                bonus += 0.65
        return bonus


class KorvoldValuePilot(KorvoldPilot):
    pilot_name = "KorvoldValuePilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = super().default_weights(strength).model_dump()
        base.update(
            card_advantage=base["card_advantage"] + 0.35,
            engine_development=base["engine_development"] + 0.30,
        )
        return PilotUtilityWeights(**base)

    def specialist_bonus(
        self, state: PilotStateView, action: PilotActionView, components: dict[str, float]
    ) -> float:
        bonus = super().specialist_bonus(state, action, components)
        if CardRole.DRAW in action.roles or CardRole.ENGINE in action.roles:
            bonus += 0.55 + action.floor_value * 0.25
        if action.action_kind == "commander" and action.immediate_impact < 0.8:
            bonus -= 0.8
        return bonus


class KorvoldSacrificePilot(KorvoldPilot):
    pilot_name = "KorvoldSacrificePilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = super().default_weights(strength).model_dump()
        base.update(
            engine_development=base["engine_development"] + 0.25,
            win_progress=base["win_progress"] + 0.15,
        )
        return PilotUtilityWeights(**base)

    def specialist_bonus(
        self, state: PilotStateView, action: PilotActionView, components: dict[str, float]
    ) -> float:
        bonus = super().specialist_bonus(state, action, components)
        if _package_ids(action) & {
            "korvold-token-sacrifice-material",
            "korvold-free-sacrifice-outlets",
        }:
            bonus += 0.35

        material = state.tokens + state.resources
        if CardRole.SACRIFICE_OUTLET in action.roles:
            bonus += 1.6 + min(1.6, material * 0.22)
        if CardRole.TOKEN_SOURCE in action.roles:
            bonus += 0.55
        if action.metadata.get("sacrifice_value", 0):
            bonus += float(action.metadata["sacrifice_value"]) * 0.35
        return bonus


class KorvoldLandRebuildPilot(KorvoldPilot):
    pilot_name = "KorvoldLandRebuildPilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = super().default_weights(strength).model_dump()
        base.update(
            rebuild_capacity=base["rebuild_capacity"] + 0.55, survival=base["survival"] + 0.15
        )
        return PilotUtilityWeights(**base)

    def specialist_bonus(
        self, state: PilotStateView, action: PilotActionView, components: dict[str, float]
    ) -> float:
        bonus = super().specialist_bonus(state, action, components)
        if _package_ids(action) & {"korvold-land-sacrifice-recursion", "korvold-wipe-rebuild"}:
            bonus += 0.40

        if CardRole.LAND_SYNERGY in action.roles or CardRole.RECURSION in action.roles:
            bonus += 0.65 + min(1.4, state.graveyard_size * 0.08)
        if bool(action.metadata.get("rebuild_line", False)):
            bonus += 1.2
        if bool(action.metadata.get("graveyard_hate_exposed", False)):
            bonus -= 7.0
        return bonus


class KorvoldAggressivePilot(KorvoldPilot):
    pilot_name = "KorvoldAggressivePilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = super().default_weights(strength).model_dump()
        base.update(
            tempo=base["tempo"] + 0.45,
            win_progress=base["win_progress"] + 0.55,
            political_visibility=-0.15,
        )
        return PilotUtilityWeights(**base)

    def specialist_bonus(
        self, state: PilotStateView, action: PilotActionView, components: dict[str, float]
    ) -> float:
        bonus = super().specialist_bonus(state, action, components)
        if _package_ids(action) & {
            "korvold-independent-finishers",
            "korvold-mirkwood-table-damage",
        }:
            bonus += 0.40

        if action.action_kind == "combat_target":
            bonus += 0.75 + float(action.metadata.get("commander_damage_pressure", 0.0)) * 0.20
        if action.card_name in {"Mirkwood Bats", "Exsanguinate", "Massacre Wurm", "Mayhem Devil"}:
            bonus += 0.75
        if action.action_kind == "commander" and action.immediate_impact >= 0.7:
            bonus += 0.45
        return bonus


class KorvoldConservativePilot(KorvoldPilot):
    pilot_name = "KorvoldConservativePilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = super().default_weights(strength).model_dump()
        base.update(
            survival=base["survival"] + 0.45,
            interaction_reserve=base["interaction_reserve"] + 0.35,
            political_visibility=-1.15,
            rebuild_capacity=base["rebuild_capacity"] + 0.30,
        )
        return PilotUtilityWeights(**base)

    def opening_hand_specialist_bonus(
        self, cards: list[PilotActionView], commander_names: tuple[str, ...]
    ) -> float:
        bonus = super().opening_hand_specialist_bonus(cards, commander_names)
        protection = sum(card.strength(CardRole.PROTECTION) for card in cards)
        interaction = sum(card.strength(CardRole.REMOVAL) for card in cards)
        return bonus + min(1.0, (protection + interaction) * 0.25)

    def specialist_bonus(
        self, state: PilotStateView, action: PilotActionView, components: dict[str, float]
    ) -> float:
        bonus = super().specialist_bonus(state, action, components)
        if _package_ids(action) & {"korvold-graveyard-protection", "korvold-wipe-rebuild"}:
            bonus += 0.40

        if CardRole.PROTECTION in action.roles or CardRole.REMOVAL in action.roles:
            bonus += 0.55
        if action.action_kind == "commander" and action.remaining_mana < 1.0:
            bonus -= 1.2
        if action.turn_cycle_risk > 0.65:
            bonus -= 0.45
        return bonus


class RogShaiTempoPilot(RogShaiPilot):
    pilot_name = "RogShaiTempoPilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = super().default_weights(strength).model_dump()
        base.update(
            tempo=base["tempo"] + 0.55, interaction_reserve=base["interaction_reserve"] + 0.25
        )
        return PilotUtilityWeights(**base)

    def specialist_bonus(
        self, state: PilotStateView, action: PilotActionView, components: dict[str, float]
    ) -> float:
        bonus = super().specialist_bonus(state, action, components)
        if _package_ids(action) & {"rogshai-protection-counter", "rogshai-rograkh-resource"}:
            bonus += 0.35

        if action.mana_cost <= 2 and action.roles.intersection(
            {CardRole.COUNTER, CardRole.REMOVAL, CardRole.SELECTION}
        ):
            bonus += 0.55
        if (
            action.action_kind == "commander"
            and action.card_name == "Ishai, Ojutai Dragonspeaker"
            and action.remaining_mana >= 1
        ):
            bonus += 0.45
        return bonus


class RogShaiVoltronPilot(RogShaiPilot):
    pilot_name = "RogShaiVoltronPilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = super().default_weights(strength).model_dump()
        base.update(
            commander_value=base["commander_value"] + 0.50,
            win_progress=base["win_progress"] + 0.55,
            political_visibility=-0.20,
        )
        return PilotUtilityWeights(**base)

    def specialist_bonus(
        self, state: PilotStateView, action: PilotActionView, components: dict[str, float]
    ) -> float:
        bonus = super().specialist_bonus(state, action, components)
        if _package_ids(action) & {
            "rogshai-combat-draw",
            "rogshai-commander-damage",
            "rogshai-double-strike",
            "rogshai-jeska-finish",
            "rogshai-kediss-table-damage",
        }:
            bonus += 0.40

        if action.card_name in {
            "Combat Research",
            "Curiosity",
            "Staggering Insight",
            "Duelist's Heritage",
            "Psychotic Fury",
            "Boros Charm",
            "Sunhome, Fortress of the Legion",
        }:
            bonus += 0.75
        if action.action_kind == "combat_target":
            bonus += float(action.metadata.get("commander_damage_pressure", 0.0)) * 0.35
        return bonus


class RogShaiSpellslingerPilot(RogShaiPilot):
    pilot_name = "RogShaiSpellslingerPilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = super().default_weights(strength).model_dump()
        base.update(
            card_advantage=base["card_advantage"] + 0.35,
            engine_development=base["engine_development"] + 0.50,
            commander_value=base["commander_value"] - 0.20,
        )
        return PilotUtilityWeights(**base)

    def specialist_bonus(
        self, state: PilotStateView, action: PilotActionView, components: dict[str, float]
    ) -> float:
        bonus = super().specialist_bonus(state, action, components)
        if _package_ids(action) & {"rogshai-independent-spellslinger", "rogshai-independent-draw"}:
            bonus += 0.45

        if action.card_name in {
            "Kykar, Wind's Fury",
            "Veyran, Voice of Duality",
            "Storm-Kiln Artist",
            "Guttersnipe",
            "Whirlwind of Thought",
            "Archmage Emeritus",
        }:
            bonus += 1.0
        if CardRole.ENGINE in action.roles or CardRole.DRAW in action.roles:
            bonus += 0.35
        return bonus


class RogShaiControlPilot(RogShaiPilot):
    pilot_name = "RogShaiControlPilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = super().default_weights(strength).model_dump()
        base.update(
            survival=base["survival"] + 0.35,
            interaction_reserve=base["interaction_reserve"] + 0.65,
            threat_reduction=base["threat_reduction"] + 0.45,
            win_progress=base["win_progress"] - 0.15,
        )
        return PilotUtilityWeights(**base)

    def specialist_bonus(
        self, state: PilotStateView, action: PilotActionView, components: dict[str, float]
    ) -> float:
        bonus = super().specialist_bonus(state, action, components)
        if _package_ids(action) & {"rogshai-protection-counter", "rogshai-wipe-protection"}:
            bonus += 0.40

        if action.action_kind == "counter":
            bonus += max(0.0, action.threat_score - 4.0) * 0.20
            if action.threat_score < 4.0:
                bonus -= 1.1
        if (
            action.action_kind == "card"
            and CardRole.COUNTER in action.roles
            and action.remaining_mana < 1.0
        ):
            bonus -= 0.9
        return bonus


class RogShaiProtectedFinishPilot(RogShaiPilot):
    pilot_name = "RogShaiProtectedFinishPilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = super().default_weights(strength).model_dump()
        base.update(
            survival=base["survival"] + 0.25,
            interaction_reserve=base["interaction_reserve"] + 0.45,
            win_progress=base["win_progress"] + 0.35,
        )
        return PilotUtilityWeights(**base)

    def specialist_bonus(
        self, state: PilotStateView, action: PilotActionView, components: dict[str, float]
    ) -> float:
        bonus = super().specialist_bonus(state, action, components)
        if _package_ids(action) & {
            "rogshai-jeska-finish",
            "rogshai-commander-damage",
            "rogshai-protection-counter",
        }:
            bonus += 0.45

        protected_window = (
            bool(action.metadata.get("protected_finish_window", False))
            or action.remaining_mana >= 1.0
        )
        if action.card_name in {
            "Jeska, Thrice Reborn",
            "Silence",
            "Psychotic Fury",
            "Duelist's Heritage",
        }:
            bonus += 1.2 if protected_window else -1.4
        if CardRole.PROTECTION in action.roles:
            bonus += 0.75
        return bonus


class AggroPilot(BasePilot):
    pilot_name = "AggroPilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = _GENERIC_WEIGHTS[strength].model_dump()
        base.update(
            tempo=base["tempo"] + 0.35,
            win_progress=base["win_progress"] + 0.45,
            political_visibility=-0.2,
        )
        return PilotUtilityWeights(**base)


class ControlPilot(BasePilot):
    pilot_name = "ControlPilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = _GENERIC_WEIGHTS[strength].model_dump()
        base.update(
            survival=base["survival"] + 0.3,
            interaction_reserve=base["interaction_reserve"] + 0.5,
            threat_reduction=base["threat_reduction"] + 0.35,
        )
        return PilotUtilityWeights(**base)


class EnginePilot(BasePilot):
    pilot_name = "EnginePilot"

    def default_weights(self, strength: PilotStrength) -> PilotUtilityWeights:
        base = _GENERIC_WEIGHTS[strength].model_dump()
        base.update(
            engine_development=base["engine_development"] + 0.45,
            card_advantage=base["card_advantage"] + 0.25,
            rebuild_capacity=base["rebuild_capacity"] + 0.2,
        )
        return PilotUtilityWeights(**base)


class GraveyardPilot(EnginePilot):
    pilot_name = "GraveyardPilot"


class ArtifactPilot(EnginePilot):
    pilot_name = "ArtifactPilot"


class GenericCommanderPilot(BasePilot):
    pilot_name = "GenericCommanderPilot"


class KaervekOpponentPilot(GenericCommanderPilot):
    """Visible-state structural policy for the verified Kaervek opponent snapshot.

    It biases toward mana development, board-control timing and independent value before
    exposing the seven-mana commander. It does not inspect hidden information.
    """

    pilot_name = "KaervekOpponentPilot"

    def opening_hand_specialist_bonus(self, cards, commander_names):  # type: ignore[no-untyped-def]
        del commander_names
        early_ramp = sum(card.strength(CardRole.RAMP) for card in cards if card.mana_cost <= 3)
        early_draw = sum(
            (card.strength(CardRole.DRAW) + card.strength(CardRole.SELECTION))
            for card in cards
            if card.mana_cost <= 3
        )
        early_removal = sum(
            card.strength(CardRole.REMOVAL) for card in cards if card.mana_cost <= 3
        )
        expensive = sum(card.mana_cost >= 6 for card in cards)
        return (
            min(1.2, early_ramp * 0.3)
            + min(0.6, early_draw * 0.2)
            + min(0.5, early_removal * 0.15)
            - max(0, expensive - 1) * 0.25
        )

    def specialist_bonus(self, state, action, components):  # type: ignore[no-untyped-def]
        del components
        name = action.card_name or ""
        bonus = 0.0
        if name == "Kaervek the Merciless":
            # Avoid blind early exposure; reward the commander once mana/turn development is mature.
            bonus += 1.0 if state.turn >= 6 else -1.0
            bonus += min(0.5, action.remaining_mana * 0.12)
        elif name == "Tor Wauki the Younger":
            bonus += 0.55
        elif name in {"Sorin Markov", "Chandra Nalaar"}:
            bonus += 0.25
        elif CardRole.WIPE in action.roles:
            bonus += min(0.8, max(0.0, state.enemy_board_total - state.board_power) * 0.08)
        elif CardRole.GRAVEYARD_HATE in action.roles:
            bonus += min(0.6, state.max_graveyard_pressure * 0.06)
        return bonus


_PILOT_TYPES: dict[str, type[BasePilot]] = {
    "korvoldpilot": KorvoldPilot,
    "rogshaipilot": RogShaiPilot,
    "aggropilot": AggroPilot,
    "controlpilot": ControlPilot,
    "enginepilot": EnginePilot,
    "graveyardpilot": GraveyardPilot,
    "artifactpilot": ArtifactPilot,
    "genericcommanderpilot": GenericCommanderPilot,
    "kaervekopponentpilot": KaervekOpponentPilot,
    "korvoldvaluepilot": KorvoldValuePilot,
    "korvoldsacrificepilot": KorvoldSacrificePilot,
    "korvoldlandrebuildpilot": KorvoldLandRebuildPilot,
    "korvoldaggressivepilot": KorvoldAggressivePilot,
    "korvoldconservativepilot": KorvoldConservativePilot,
    "rogshaitempopilot": RogShaiTempoPilot,
    "rogshaivoltronpilot": RogShaiVoltronPilot,
    "rogshaispellslingerpilot": RogShaiSpellslingerPilot,
    "rogshaicontrolpilot": RogShaiControlPilot,
    "rogshaiprotectedfinishpilot": RogShaiProtectedFinishPilot,
}


def auto_pilot_name(strategy: str) -> str:
    normalized = strategy.casefold()
    if normalized == "korvold":
        return "KorvoldPilot"
    if normalized in {"rogshai", "ishai_rograkh"}:
        return "RogShaiPilot"
    if normalized in {"kaervek", "punisher_control_reanimation"}:
        return "KaervekOpponentPilot"

    # Current opponent structural profiles carry explicit strategy labels rather than the
    # generic pilot names. Resolve those labels to the closest existing public-information
    # archetype pilot so opponent turns are not systematically evaluated by the weakest
    # catch-all policy. This is an archetype-routing boundary, not a hidden-information or
    # card-list inference.
    if normalized == "aggro" or "aggro" in normalized or "combat" in normalized:
        return "AggroPilot"
    if normalized == "control" or "control" in normalized:
        return "ControlPilot"
    if normalized == "artifact" or "artifact" in normalized or "equipment" in normalized:
        return "ArtifactPilot"
    if normalized == "graveyard" or "recursion" in normalized or "reanimation" in normalized:
        return "GraveyardPilot"
    if normalized == "engine" or "engine" in normalized or "etb" in normalized:
        return "EnginePilot"
    return "GenericCommanderPilot"


def build_pilot(config: PilotConfig, *, strategy: str) -> BasePilot:
    requested = (
        auto_pilot_name(strategy) if config.pilot_name.casefold() == "auto" else config.pilot_name
    )
    pilot_type = _PILOT_TYPES.get(requested.casefold())
    if pilot_type is None:
        raise ValueError(f"unknown pilot: {requested}")
    resolved = config.model_copy(update={"pilot_name": requested})
    return pilot_type(resolved)


__all__ = [
    "AggroPilot",
    "ArtifactPilot",
    "BasePilot",
    "ControlPilot",
    "EnginePilot",
    "GenericCommanderPilot",
    "GraveyardPilot",
    "KaervekOpponentPilot",
    "KorvoldAggressivePilot",
    "KorvoldConservativePilot",
    "KorvoldLandRebuildPilot",
    "KorvoldPilot",
    "KorvoldSacrificePilot",
    "KorvoldValuePilot",
    "RogShaiControlPilot",
    "RogShaiPilot",
    "RogShaiProtectedFinishPilot",
    "RogShaiSpellslingerPilot",
    "RogShaiTempoPilot",
    "RogShaiVoltronPilot",
    "auto_pilot_name",
    "build_pilot",
]
