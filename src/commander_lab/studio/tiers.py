"""Card tiers as a pure function of counted signals and owner-set parameters.

A tier here is not a judgement stored anywhere: it is computed, on demand, from the
inclusion share of a card in one deck universe (see ``universe.py``) and the parameters
below. The parameter *values* in ``TierParams`` are code defaults so the function can
run; they are settings the owner can change per profile or per call, not findings.
A card lands in tier ``U`` (insufficient data) — never in a guessed tier — when the
universe is smaller than ``min_universe`` decks or the card has no counted denominator.

The breakdown returned with every tier names the exact inputs: hits, denominator,
share, the universe snapshot the count ran over, and the parameter set used, so any
displayed tier can be recomputed and checked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TierParams:
    """Owner-set parameters of the tier function (defaults are placeholders)."""

    min_universe: int = 30
    # Descending (tier, minimum inclusion share) cuts; the first cut a card reaches wins.
    cuts: tuple[tuple[str, float], ...] = field(
        default_factory=lambda: (("S", 0.50), ("A", 0.35), ("B", 0.20), ("C", 0.10))
    )
    fallback_tier: str = "D"

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_universe": self.min_universe,
            "cuts": [[tier, cut] for tier, cut in self.cuts],
            "fallback_tier": self.fallback_tier,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TierParams:
        cuts = tuple((str(tier), float(cut)) for tier, cut in raw.get("cuts", []))
        return cls(
            min_universe=int(raw.get("min_universe", 30)),
            cuts=cuts or cls().cuts,
            fallback_tier=str(raw.get("fallback_tier", "D")),
        )


def tier_for_share(share: float | None, denominator: int, params: TierParams) -> tuple[str, str]:
    """The tier of one counted share, plus the mechanical reason code."""
    if denominator < params.min_universe:
        return "U", "UNIVERSE_TOO_SMALL"
    if share is None:
        return "U", "DENOMINATOR_MISSING"
    for tier, cut in params.cuts:
        if share >= cut:
            return tier, "SHARE_CUT"
    return params.fallback_tier, "BELOW_LOWEST_CUT"


def card_tier(
    *,
    card_name: str,
    hits: int,
    denominator: int,
    universe_snapshot: str,
    params: TierParams,
) -> dict[str, Any]:
    share = hits / denominator if denominator else None
    tier, reason = tier_for_share(share, denominator, params)
    return {
        "card_name": card_name,
        "tier": tier,
        "reason": reason,
        "hits": hits,
        "denominator": denominator,
        "share": share,
        "universe_snapshot": universe_snapshot,
        "params": params.to_dict(),
        "data_class": "DERIVED_DESCRIPTIVE",
    }


def tiers_for_universe(
    inclusion_result: dict[str, Any], *, universe_snapshot: str, params: TierParams
) -> list[dict[str, Any]]:
    """Tiers for every row of a ``universe.inclusion`` result, in the same order."""
    return [
        card_tier(
            card_name=str(row["card_name"]),
            hits=int(row["hits"]),
            denominator=int(row["denominator"]),
            universe_snapshot=universe_snapshot,
            params=params,
        )
        for row in inclusion_result["rows"]
    ]
