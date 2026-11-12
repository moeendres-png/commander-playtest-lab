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

from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import pairwise
from typing import TypedDict

from ._coerce import iterate, to_float, to_int
from .universe import InclusionResult


class TierParamsDict(TypedDict):
    """The serialized form of ``TierParams``."""

    min_universe: int
    cuts: list[list[str | float]]
    fallback_tier: str


class CardTier(TypedDict):
    """One computed tier with the exact inputs it was computed from."""

    card_name: str
    tier: str
    reason: str
    hits: int
    denominator: int
    share: float | None
    universe_snapshot: str
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    params: TierParamsDict
    data_class: str


@dataclass(frozen=True)
class TierParams:
    """Owner-set parameters of the tier function (defaults are placeholders)."""

    min_universe: int = 30
    # Descending (tier, minimum inclusion share) cuts; the first cut a card reaches wins.
    cuts: tuple[tuple[str, float], ...] = field(
        default_factory=lambda: (("S", 0.50), ("A", 0.35), ("B", 0.20), ("C", 0.10))
    )
    fallback_tier: str = "D"

    def __post_init__(self) -> None:
        if self.min_universe < 1:
            raise ValueError("tier parameter min_universe must be at least 1")
        labels = [tier for tier, _ in self.cuts]
        if any(not label for label in labels) or not self.fallback_tier:
            raise ValueError("tier labels must not be empty")
        if len(set(labels)) != len(labels):
            raise ValueError("tier labels in cuts must be unique")
        shares = [cut for _, cut in self.cuts]
        if any(not 0 < share <= 1 for share in shares):
            raise ValueError("every tier cut share must be in (0, 1]")
        if any(later >= earlier for earlier, later in pairwise(shares)):
            raise ValueError("tier cuts must be strictly descending by share")

    def to_dict(self) -> TierParamsDict:
        return {
            "min_universe": self.min_universe,
            "cuts": [[tier, cut] for tier, cut in self.cuts],
            "fallback_tier": self.fallback_tier,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> TierParams:
        # An explicitly empty cuts list is an owner setting (every counted card lands
        # in the fallback tier), not a missing value: only an absent key defaults.
        cuts = tuple(_cut(item) for item in iterate(raw["cuts"])) if "cuts" in raw else cls().cuts
        return cls(
            min_universe=to_int(raw.get("min_universe", 30)),
            cuts=cuts,
            fallback_tier=str(raw.get("fallback_tier", "D")),
        )


def _cut(item: object) -> tuple[str, float]:
    pair = list(iterate(item))
    if len(pair) != 2:
        raise ValueError(f"a tier cut must be a (tier, share) pair, got {len(pair)} values")
    return str(pair[0]), to_float(pair[1])


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
    denominator_by_platform: Mapping[str, int] | None = None,
    denominator_by_bracket: Mapping[str, int] | None = None,
) -> CardTier:
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
        "denominator_by_platform": dict(denominator_by_platform or {}),
        "denominator_by_bracket": dict(denominator_by_bracket or {}),
        "params": params.to_dict(),
        "data_class": "DERIVED_DESCRIPTIVE",
    }


def tiers_for_universe(
    inclusion_result: InclusionResult, *, universe_snapshot: str, params: TierParams
) -> list[CardTier]:
    """Tiers for every row of a ``universe.inclusion`` result, in the same order."""
    return [
        card_tier(
            card_name=str(row["card_name"]),
            hits=int(row["hits"]),
            denominator=int(row["denominator"]),
            universe_snapshot=universe_snapshot,
            params=params,
            denominator_by_platform=inclusion_result["denominator_by_platform"],
            denominator_by_bracket=inclusion_result["denominator_by_bracket"],
        )
        for row in inclusion_result["rows"]
    ]
