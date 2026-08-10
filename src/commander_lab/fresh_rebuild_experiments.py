from __future__ import annotations

from collections.abc import Mapping

from commander_lab.fresh_rebuild import FreshRogShaiUniverse
from commander_lab.models import CandidateProfile, StructuralDeckProfile
from commander_lab.storage import sha256_value


def candidates_for_fresh_baseline(
    universe: FreshRogShaiUniverse,
    baseline: StructuralDeckProfile,
) -> dict[str, CandidateProfile]:
    """Expose scorable candidates to the generic search engine without current-deck priors."""

    return {
        candidate_id: candidate.model_copy(
            update={"allowed_deck_ids": (baseline.deck_id,)}
        )
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
    """Create a deterministic per-commander denial scenario for partner decks.

    Denial is represented conservatively as additional commander tax for the selected
    commander(s).  This keeps Ishai-only, Rograkh-only and both-denied scenarios distinct
    without pretending that the structural model is a full rules engine.
    """

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
    """Return only physical availability; no quality or allocation bonus is encoded."""

    return universe.available_quantities
