from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import fmean

from commander_lab.models import (
    CardRole,
    Color,
    ConstraintIssue,
    ConstraintReport,
    OptimizationConstraints,
    StructuralDeckProfile,
)

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


DEFAULT_CONSTRAINTS: dict[str, OptimizationConstraints] = {
    "rogshai/current": OptimizationConstraints(
        allowed_colors=frozenset({Color.WHITE, Color.BLUE, Color.RED}),
        role_minima={
            CardRole.RAMP: 9,
            CardRole.DRAW: 6,
            CardRole.REMOVAL: 9,
            CardRole.COUNTER: 6,
            CardRole.PROTECTION: 6,
            CardRole.WIPE: 3,
            CardRole.GRAVEYARD_HATE: 2,
            CardRole.FINISHER: 2,
            CardRole.COMBAT_PAYOFF: 7,
        },
        minimum_lands=36,
        maximum_lands=38,
        minimum_colored_sources={Color.WHITE: 16, Color.BLUE: 17, Color.RED: 13},
        maximum_average_nonland_mana_value=2.80,
        maximum_high_mana_value_cards=9,
        high_mana_value_threshold=5.0,
        simultaneous_deck_ids=(),
        required_commanders=("Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"),
        require_partner_configuration=True,
        locked_cards=(),
    ),
}


def load_candidate_inventory(root: str | Path) -> dict[str, int]:
    path = Path(root) / "data/collections/phase7_optimization_pool.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["oracle_name"]): int(row["available_quantity"]) for row in payload["cards"]}


def role_counts(deck: StructuralDeckProfile) -> Counter[CardRole]:
    counts: Counter[CardRole] = Counter()
    for card in deck.cards:
        counts.update(card.roles)
    return counts


def evaluate_constraints(
    deck: StructuralDeckProfile,
    constraints: OptimizationConstraints,
    *,
    candidate_inventory: dict[str, int] | None = None,
    added_card_names: tuple[str, ...] = (),
    verified_physical_names: set[str] | None = None,
) -> ConstraintReport:
    issues: list[ConstraintIssue] = []
    metrics: dict[str, object] = {}
    candidate_inventory = candidate_inventory or {}
    verified_physical_names = verified_physical_names or set()

    if len(deck.cards) != constraints.exact_card_count:
        issues.append(
            ConstraintIssue(
                code="card_count",
                message=f"variant contains {len(deck.cards)} cards, expected {constraints.exact_card_count}",
                context={"actual": len(deck.cards), "expected": constraints.exact_card_count},
            )
        )

    if constraints.required_commanders and tuple(deck.commander_names) != tuple(
        constraints.required_commanders
    ):
        issues.append(
            ConstraintIssue(
                code="commander_identity",
                message="variant commander/partner configuration differs from the canonical optimization target",
                context={
                    "actual": list(deck.commander_names),
                    "required": list(constraints.required_commanders),
                },
            )
        )
    if constraints.require_partner_configuration is not None:
        actual_partner = len(deck.commander_names) == 2
        if actual_partner != constraints.require_partner_configuration:
            issues.append(
                ConstraintIssue(
                    code="partner_configuration",
                    message="variant partner configuration differs from current policy",
                    context={
                        "actual": actual_partner,
                        "required": constraints.require_partner_configuration,
                    },
                )
            )

    names = Counter(card.oracle_name for card in deck.cards)
    missing_locked = [name for name in constraints.locked_cards if names.get(name, 0) < 1]
    if missing_locked:
        issues.append(
            ConstraintIssue(
                code="locked_card",
                message="variant removes current locked/must-play cards",
                context={"missing": sorted(missing_locked)},
            )
        )
    if constraints.singleton:
        for name, quantity in names.items():
            if quantity > 1 and name not in BASIC_LANDS:
                issues.append(
                    ConstraintIssue(
                        code="singleton",
                        message=f"{name} appears {quantity} times",
                        context={"card": name, "quantity": quantity},
                    )
                )

    for card in deck.cards:
        card_colors = set(card.color_identity) or set(card.color_requirements)
        illegal = card_colors - set(constraints.allowed_colors)
        if illegal:
            issues.append(
                ConstraintIssue(
                    code="color_identity",
                    message=f"{card.oracle_name} requires colors outside the Commander identity",
                    context={"illegal_colors": sorted(color.value for color in illegal)},
                )
            )

    lands = sum(card.is_land for card in deck.cards)
    nonlands = [card for card in deck.cards if not card.is_land]
    average_mv = fmean(card.mana_value for card in nonlands) if nonlands else 0.0
    high_mv = sum(card.mana_value >= constraints.high_mana_value_threshold for card in nonlands)
    metrics.update(
        {"lands": lands, "average_nonland_mana_value": average_mv, "high_mana_value_cards": high_mv}
    )
    if not constraints.minimum_lands <= lands <= constraints.maximum_lands:
        issues.append(
            ConstraintIssue(
                code="land_count",
                message=f"land count {lands} outside {constraints.minimum_lands}-{constraints.maximum_lands}",
            )
        )
    if average_mv > constraints.maximum_average_nonland_mana_value:
        issues.append(
            ConstraintIssue(
                code="mana_curve_average",
                message=(
                    f"average nonland mana value {average_mv:.3f} exceeds "
                    f"{constraints.maximum_average_nonland_mana_value:.3f}"
                ),
            )
        )
    if high_mv > constraints.maximum_high_mana_value_cards:
        issues.append(
            ConstraintIssue(
                code="mana_curve_top_end",
                message=f"{high_mv} high-mana cards exceed maximum {constraints.maximum_high_mana_value_cards}",
            )
        )

    counts = role_counts(deck)
    metrics["role_counts"] = {role.value: counts[role] for role in CardRole}
    for role, minimum in constraints.role_minima.items():
        if counts[role] < minimum:
            issues.append(
                ConstraintIssue(
                    code="role_minimum",
                    message=f"role {role.value} has {counts[role]}, minimum is {minimum}",
                    context={"role": role.value, "actual": counts[role], "minimum": minimum},
                )
            )

    sources: Counter[Color] = Counter()
    for card in deck.cards:
        if card.is_land or CardRole.MANA_SOURCE in card.roles or CardRole.RAMP in card.roles:
            for color in card.produces_colors:
                if color in constraints.allowed_colors:
                    sources[color] += 1
    metrics["colored_sources"] = {
        color.value: sources[color] for color in constraints.allowed_colors
    }
    for color, minimum in constraints.minimum_colored_sources.items():
        if sources[color] < minimum:
            issues.append(
                ConstraintIssue(
                    code="colored_sources",
                    message=f"{color.value} sources {sources[color]} below minimum {minimum}",
                    context={"color": color.value, "actual": sources[color], "minimum": minimum},
                )
            )

    if constraints.require_verified_inventory:
        added_counts = Counter(added_card_names)
        for name, quantity in added_counts.items():
            available = candidate_inventory.get(name, 0)
            if available < quantity:
                issues.append(
                    ConstraintIssue(
                        code="physical_inventory",
                        message=f"{name}: requires {quantity}, verified optimization pool has {available}",
                        context={"card": name, "required": quantity, "available": available},
                    )
                )
            if name not in verified_physical_names:
                issues.append(
                    ConstraintIssue(
                        code="physical_verification",
                        message=f"{name} is not marked locally verified for optimization",
                        context={"card": name},
                    )
                )

    return ConstraintReport(
        valid=not any(issue.severity == "error" for issue in issues),
        issues=tuple(issues),
        metrics=metrics,
    )


def evaluate_simultaneous_allocation(
    additions_by_deck: dict[str, tuple[str, ...]],
    candidate_inventory: dict[str, int],
) -> ConstraintReport:
    required: Counter[str] = Counter()
    for names in additions_by_deck.values():
        required.update(names)
    issues: list[ConstraintIssue] = []
    for name, quantity in sorted(required.items()):
        available = candidate_inventory.get(name, 0)
        if quantity > available:
            issues.append(
                ConstraintIssue(
                    code="simultaneous_physical_allocation",
                    message=f"{name}: {quantity} simultaneous copies required, {available} available",
                    context={"card": name, "required": quantity, "available": available},
                )
            )
    return ConstraintReport(
        valid=not issues,
        issues=tuple(issues),
        metrics={
            "decks": sorted(additions_by_deck),
            "required": dict(required),
            "available": {name: candidate_inventory.get(name, 0) for name in required},
        },
    )
