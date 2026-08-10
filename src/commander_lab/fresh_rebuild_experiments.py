from __future__ import annotations

from collections.abc import Mapping

from commander_lab.fresh_rebuild import FreshRogShaiUniverse
from commander_lab.models import (
    CandidateProfile,
    Color,
    OptimizationConstraints,
    StructuralDeckProfile,
)
from commander_lab.storage import sha256_value


def fresh_hard_constraints() -> OptimizationConstraints:
    """Fresh-rebuild hard constraints only; no Phase-7 role/curve architecture priors."""

    return OptimizationConstraints(
        exact_card_count=100,
        singleton=True,
        allowed_colors=frozenset({Color.WHITE, Color.BLUE, Color.RED}),
        role_minima={},
        minimum_lands=0,
        maximum_lands=100,
        minimum_colored_sources={},
        maximum_average_nonland_mana_value=20.0,
        maximum_high_mana_value_cards=100,
        high_mana_value_threshold=5.0,
        require_verified_inventory=True,
        simultaneous_deck_ids=("korvold/current",),
    )


def candidates_for_fresh_baseline(
    universe: FreshRogShaiUniverse,
    baseline: StructuralDeckProfile,
) -> dict[str, CandidateProfile]:
    """Expose all currently scorable fresh candidates without current-deck quality priors."""

    return {
        candidate_id: candidate.model_copy(update={"allowed_deck_ids": (baseline.deck_id,)})
        for candidate_id, candidate in universe.candidates.items()
        if universe.available_quantities.get(candidate.card.oracle_name, 0) > 0
        and candidate.card.oracle_name not in baseline.commander_names
    }


def commander_denial_variant(
    baseline: StructuralDeckProfile,
    denied_commanders: tuple[str, ...],
    *,
    additional_tax: int = 6,
) -> StructuralDeckProfile:
    """Create a deterministic structural per-commander denial scenario for a partner deck."""

    if additional_tax < 0:
        raise ValueError("additional_tax must be nonnegative")
    denied = tuple(dict.fromkeys(denied_commanders))
    unknown = sorted(set(denied) - set(baseline.commander_names))
    if unknown:
        raise ValueError(f"denial references non-commanders: {unknown}")
    if not denied:
        raise ValueError("at least one commander must be denied")

    costs = dict(baseline.commander_base_costs)
    for name in denied:
        costs[name] = costs[name] + additional_tax
    identity = sha256_value(
        {
            "baseline": baseline.deck_hash,
            "denied_commanders": denied,
            "additional_tax": additional_tax,
            "estimate_type": "structural_model_estimates",
        }
    )
    return baseline.model_copy(
        update={
            "deck_id": f"{baseline.deck_id}/denial/{identity[:12]}",
            "deck_hash": identity,
            "commander_base_costs": costs,
        }
    )


def fresh_physical_inventory_for_search(
    universe: FreshRogShaiUniverse,
) -> Mapping[str, int]:
    """Return physical feasibility only; no quality or allocation bonus is encoded."""

    return universe.available_quantities
