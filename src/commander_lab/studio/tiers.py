"""Model parameters of the counted spread ("Verbreitung (gezählt)") of one deck universe.

The spread itself is ``hits`` of ``denominator`` decks with its origin (``universe_view.py``); it
measures how often a card is played in the chosen decks, never how strong it is. Since Q1-b5
(#1680, decision E2) it has no level letters any more: the only scale with letters on the tier
page is the strength index S to D. What stays here is the parameter set the spread is read with:
``min_universe``, the smallest denominator whose share is still shown (a smaller universe is
"unbekannt", never 0), and the cut set of ``MODEL_VERSION``, which only still names the reason
code of a counted share (``SHARE_CUT`` / ``BELOW_LOWEST_CUT``) and is reported with every answer
so a figure can be checked. The cut *values* are model constants, not settings: the only
owner-set value a universe profile carries is ``min_universe``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import pairwise
from typing import TypedDict

from ._coerce import iterate, to_float, to_int

#: Version of the counted-spread model: the cut set and fallback of ``TierParams``.
#: Bump it whenever the cuts change; views cite it next to the thresholds they show.
MODEL_VERSION = "counted-spread-1"


class TierParamsDict(TypedDict):
    """The serialized form of ``TierParams``."""

    min_universe: int
    cuts: list[list[str | float]]
    fallback_tier: str


@dataclass(frozen=True)
class TierParams:
    """Parameters of the tier function. The cuts and the fallback tier are model
    constants (``MODEL_VERSION``); ``min_universe`` is the one value a universe
    profile may set, everything else stays at the model default."""

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


def spread_reason(share: float | None, denominator: int, params: TierParams) -> str:
    """The mechanical reason code of one counted share; never a level letter. A denominator
    below ``min_universe`` and a missing share are unknown (the view shows no share), a counted
    share names whether it reaches the lowest model cut."""
    if denominator < params.min_universe:
        return "UNIVERSE_TOO_SMALL"
    if share is None:
        return "DENOMINATOR_MISSING"
    if any(share >= cut for _, cut in params.cuts):
        return "SHARE_CUT"
    return "BELOW_LOWEST_CUT"
