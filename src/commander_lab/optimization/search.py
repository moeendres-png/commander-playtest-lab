from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import fmean

from commander_lab.models import (
    CandidateProfile,
    CardRole,
    ConstraintReport,
    ObjectiveVector,
    OptimizationConstraints,
    OptimizationVariant,
    StructuralCardProfile,
    StructuralDeckProfile,
    VariantSwap,
)
from commander_lab.storage import sha256_value

from .constraints import evaluate_constraints, role_counts
from .experiments import PairedMetrics, profile_score, variant_deck


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    variant: StructuralDeckProfile
    swaps: tuple[VariantSwap, ...]
    additions: tuple[CandidateProfile, ...]
    constraint_report: ConstraintReport
    screening_score: float
    rationale: tuple[str, ...]
    affected_matchups: tuple[str, ...]
    parent_variant_id: str | None = None


def default_constraints(
    deck_id: str,
    supplied: OptimizationConstraints | None,
    defaults: dict[str, OptimizationConstraints],
) -> OptimizationConstraints:
    if supplied is not None:
        return supplied
    try:
        return defaults[deck_id]
    except KeyError as exc:
        raise ValueError(f"no default optimization constraints for {deck_id}") from exc


def card_matchup_tags(card: StructuralCardProfile) -> set[str]:
    tags: set[str] = set()
    roles = card.roles
    if CardRole.WIPE in roles or CardRole.REMOVAL in roles:
        tags.update({"wide_boards", "creature_engines"})
    if CardRole.COUNTER in roles:
        tags.update({"stack_engines", "commander_casts"})
    if CardRole.GRAVEYARD_HATE in roles:
        tags.add("graveyard_recursion")
    if CardRole.PROTECTION in roles:
        tags.update({"control", "commander_denial"})
    if roles & {CardRole.DRAW, CardRole.ENGINE, CardRole.RECURSION}:
        tags.update({"grindy_pods", "post_wipe_rebuild"})
    if roles & {CardRole.FINISHER, CardRole.PAYOFF, CardRole.COMBAT_PAYOFF}:
        tags.update({"table_closure", "large_pods"})
    if roles & {CardRole.SACRIFICE_OUTLET, CardRole.LAND_SYNERGY}:
        tags.add("korvold_synergy")
    if CardRole.COMBAT_PAYOFF in roles:
        tags.add("commander_damage")
    return tags


def structural_rationale(
    remove: StructuralCardProfile, add: StructuralCardProfile
) -> tuple[str, ...]:
    gained = sorted(role.value for role in add.roles - remove.roles)
    lost = sorted(role.value for role in remove.roles - add.roles)
    reasons = [
        f"Profile score changes from {profile_score(remove):.3f} to {profile_score(add):.3f}.",
        f"Mana value changes from {remove.mana_value:.1f} to {add.mana_value:.1f}.",
        (f"Gains roles: {', '.join(gained)}." if gained else "No new structural role is added."),
        (f"Loses roles: {', '.join(lost)}." if lost else "No structural role is lost."),
        (
            f"Immediate impact {remove.immediate_impact:.2f} → {add.immediate_impact:.2f}; "
            f"turn-cycle risk {remove.turn_cycle_risk:.2f} → {add.turn_cycle_risk:.2f}."
        ),
    ]
    return tuple(reasons)


def screening_delta(remove: StructuralCardProfile, add: StructuralCardProfile) -> float:
    overlap = add.roles & remove.roles
    lost = remove.roles - add.roles
    critical = {
        CardRole.GRAVEYARD_HATE,
        CardRole.REMOVAL,
        CardRole.COUNTER,
        CardRole.PROTECTION,
        CardRole.WIPE,
        CardRole.RECURSION,
    }
    return (
        profile_score(add)
        - profile_score(remove)
        + 0.45 * len(overlap)
        - 0.35 * len(lost)
        - 1.5 * len(lost & critical)
    )


def build_search_candidate(
    baseline: StructuralDeckProfile,
    swaps: Sequence[VariantSwap],
    candidates: dict[str, CandidateProfile],
    constraints: OptimizationConstraints,
    *,
    inventory: dict[str, int],
    verified_physical_names: set[str],
    parent_variant_id: str | None = None,
) -> SearchCandidate:
    removals: list[str] = []
    additions: list[StructuralCardProfile] = []
    candidate_rows: list[CandidateProfile] = []
    rationales: list[str] = []
    matchup_tags: set[str] = set()
    total_screening = 0.0
    for swap in swaps:
        candidate = candidates[swap.add_candidate_id]
        original = next((card for card in baseline.cards if card.oracle_name == swap.remove), None)
        if original is None:
            raise ValueError(f"card not found in variant parent: {swap.remove}")
        if candidate.card.oracle_name in {
            card.oracle_name for card in baseline.cards if card.oracle_name != swap.remove
        }:
            raise ValueError(f"candidate would violate singleton: {candidate.card.oracle_name}")
        removals.append(swap.remove)
        additions.append(candidate.card)
        candidate_rows.append(candidate)
        rationales.extend(structural_rationale(original, candidate.card))
        matchup_tags.update(card_matchup_tags(original) | card_matchup_tags(candidate.card))
        total_screening += screening_delta(original, candidate.card)
    variant_id = (
        f"{baseline.deck_id}/search/{sha256_value([s.model_dump(mode='json') for s in swaps])[:12]}"
    )
    variant = variant_deck(
        baseline,
        variant_id=variant_id,
        removals=removals,
        additions=additions,
    )
    report = evaluate_constraints(
        variant,
        constraints,
        candidate_inventory=inventory,
        added_card_names=tuple(card.oracle_name for card in additions),
        verified_physical_names=verified_physical_names,
    )
    return SearchCandidate(
        variant=variant,
        swaps=tuple(swaps),
        additions=tuple(candidate_rows),
        constraint_report=report,
        screening_score=total_screening,
        rationale=tuple(rationales),
        affected_matchups=tuple(sorted(matchup_tags)),
        parent_variant_id=parent_variant_id,
    )


def all_legal_single_swaps(
    deck: StructuralDeckProfile,
    candidates: dict[str, CandidateProfile],
    candidate_ids: Iterable[str],
    constraints: OptimizationConstraints,
    *,
    inventory: dict[str, int],
    verified_physical_names: set[str],
    protected: set[str] = frozenset(),
) -> list[SearchCandidate]:
    results: list[SearchCandidate] = []
    cuts = list(
        {
            card.oracle_name: card
            for card in deck.cards
            if card.oracle_name not in deck.commander_names
            and card.oracle_name not in protected
            and not card.is_land
        }.values()
    )
    for cut in cuts:
        for candidate_id in candidate_ids:
            candidate = candidates[candidate_id]
            if candidate.allowed_deck_ids and deck.deck_id not in candidate.allowed_deck_ids:
                continue
            try:
                result = build_search_candidate(
                    deck,
                    (VariantSwap(remove=cut.oracle_name, add_candidate_id=candidate_id),),
                    candidates,
                    constraints,
                    inventory=inventory,
                    verified_physical_names=verified_physical_names,
                )
            except ValueError:
                continue
            if result.constraint_report.valid:
                results.append(result)
    results.sort(key=lambda item: (item.screening_score, item.variant.deck_hash), reverse=True)
    return results


def profile_rebuild_score(deck: StructuralDeckProfile) -> float:
    counts = role_counts(deck)
    raw = (
        counts[CardRole.DRAW] * 0.20
        + counts[CardRole.RECURSION] * 0.35
        + counts[CardRole.ENGINE] * 0.10
        + counts[CardRole.TOKEN_SOURCE] * 0.08
        + counts[CardRole.PROTECTION] * 0.08
    )
    return min(1.0, raw / 5.0)


def profile_closing_score(deck: StructuralDeckProfile) -> float:
    finishers = [
        card
        for card in deck.cards
        if card.roles & {CardRole.FINISHER, CardRole.PAYOFF, CardRole.COMBAT_PAYOFF}
    ]
    if not finishers:
        return 0.0
    raw = sum(
        0.6 * card.strength(CardRole.FINISHER)
        + 0.25 * card.strength(CardRole.PAYOFF)
        + 0.2 * card.strength(CardRole.COMBAT_PAYOFF)
        + 0.25 * max(0.0, card.multiplayer_scaling)
        + 0.15 * card.immediate_impact
        for card in finishers
    )
    return min(1.0, raw / 8.0)


def worst_quartile_improvement(pairs: Sequence[dict[str, object]]) -> float:
    if not pairs:
        return 0.0
    deltas = sorted(
        float(row["baseline_placement"]) - float(row["variant_placement"]) for row in pairs
    )
    size = max(1, math.ceil(len(deltas) * 0.25))
    return fmean(deltas[:size])


def objective_vector(
    *,
    metrics: PairedMetrics,
    pairs: Sequence[dict[str, object]],
    variant: StructuralDeckProfile,
    commander_dependency_penalty: float,
    holdout_improvements: Sequence[float],
    physical_valid: bool,
) -> ObjectiveVector:
    robustness = (
        min(holdout_improvements) if holdout_improvements else metrics.placement_improvement
    )
    return ObjectiveVector(
        four_player_performance=metrics.placement_improvement,
        worst_quartile=worst_quartile_improvement(pairs),
        commander_independence=-commander_dependency_penalty,
        rebuild=profile_rebuild_score(variant),
        closing_power=profile_closing_score(variant),
        matchup_robustness=robustness,
        physical_allocation=1.0 if physical_valid else 0.0,
    )


def dominates(a: ObjectiveVector, b: ObjectiveVector, *, epsilon: float = 1e-12) -> bool:
    av = a.as_maximize_dict()
    bv = b.as_maximize_dict()
    return all(av[key] >= bv[key] - epsilon for key in av) and any(
        av[key] > bv[key] + epsilon for key in av
    )


def pareto_front(variants: Sequence[OptimizationVariant]) -> list[OptimizationVariant]:
    eligible = [
        variant
        for variant in variants
        if variant.objectives is not None and variant.constraint_report.valid
    ]
    front = [
        candidate
        for candidate in eligible
        if not any(
            other.variant_id != candidate.variant_id
            and dominates(other.objectives, candidate.objectives)  # type: ignore[arg-type]
            for other in eligible
        )
    ]
    front.sort(
        key=lambda item: (
            item.objectives.four_player_performance if item.objectives else -99,
            item.objectives.matchup_robustness if item.objectives else -99,
            item.deck_hash,
        ),
        reverse=True,
    )
    return front


def approximate_shapley_profile(
    deck: StructuralDeckProfile,
    card_names: Sequence[str],
    *,
    permutations: int,
    seed: int,
) -> dict[str, dict[str, float]]:
    cards = {card.oracle_name: card for card in deck.cards if card.oracle_name in card_names}
    missing = set(card_names) - set(cards)
    if missing:
        raise ValueError(f"cards not found: {sorted(missing)}")
    rng = random.Random(seed)
    marginals: dict[str, list[float]] = {name: [] for name in card_names}

    def coalition_value(names: set[str]) -> float:
        selected = [cards[name] for name in names]
        base = sum(profile_score(card) for card in selected)
        roles = Counter(role for card in selected for role in card.roles)
        synergy = sum(max(0, count - 1) * 0.08 for count in roles.values())
        conditional = sum(len(card.conditional_strength) * 0.05 for card in selected)
        return base + synergy + conditional

    for _ in range(permutations):
        order = list(card_names)
        rng.shuffle(order)
        coalition: set[str] = set()
        before = 0.0
        for name in order:
            coalition.add(name)
            after = coalition_value(coalition)
            marginals[name].append(after - before)
            before = after
    result: dict[str, dict[str, float]] = {}
    for name, values in marginals.items():
        mean = fmean(values)
        variance = fmean((value - mean) ** 2 for value in values) if values else 0.0
        se = math.sqrt(variance / max(1, len(values)))
        result[name] = {
            "shapley_value": mean,
            "standard_error": se,
            "ci95_low": mean - 1.96 * se,
            "ci95_high": mean + 1.96 * se,
        }
    return result
