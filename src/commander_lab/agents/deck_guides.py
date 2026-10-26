"""Deck guides (data/deck_guides) as parameters for the pilot.

A guide is a set of hypotheses about one deck, derived from its list (FORMAT.md in the data
directory). This module only reads them; whether a guide makes a pilot play better is decided by
paired real-game runs, so nothing here is switched on by default.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..models.pilots import PilotStrength, PilotUtilityWeights
from .pilots import generic_weights

_GUIDES = Path(__file__).resolve().parents[3] / "data/deck_guides/guides"
_WEIGHT_NAMES = frozenset(PilotUtilityWeights.model_fields)


@dataclass(frozen=True, slots=True)
class DeckGuide:
    deck_id: str
    commanders: frozenset[str]
    utility_deltas: Mapping[str, float]


def _front_face(name: str) -> str:
    return name.split(" // ")[0]


@lru_cache(maxsize=1)
def _all_guides() -> tuple[DeckGuide, ...]:
    guides: list[DeckGuide] = []
    for path in sorted(_GUIDES.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        deltas = {
            name: float(value)
            for name, value in raw["utility_deltas"].items()
            if name in _WEIGHT_NAMES and isinstance(value, int | float)
        }
        guides.append(
            DeckGuide(
                deck_id=str(raw["deck_id"]),
                commanders=frozenset(_front_face(name) for name in raw["commander"]),
                utility_deltas=deltas,
            )
        )
    return tuple(guides)


def find_guide(deck_id: str, commander_names: Sequence[str]) -> DeckGuide | None:
    """The guide of a deck: by its id, else by its commanders when exactly one guide matches.

    Decks outside the precon pool carry their own ids (the Owner's list, the opposing precons of
    the real pod); their commanders name the guide, but only if that is unambiguous.
    """
    guides = _all_guides()
    for guide in guides:
        if guide.deck_id == deck_id:
            return guide
    wanted = frozenset(_front_face(name) for name in commander_names)
    matches = [guide for guide in guides if guide.commanders == wanted]
    return matches[0] if len(matches) == 1 else None


def guided_weights(guide: DeckGuide, strength: PilotStrength) -> PilotUtilityWeights:
    """The generic weights of a strength with the guide's deltas added (kept inside the bounds)."""
    base = generic_weights(strength).as_dict()
    low, high = -5.0, 5.0
    return PilotUtilityWeights(
        **{
            name: min(high, max(low, value + guide.utility_deltas.get(name, 0.0)))
            for name, value in base.items()
        }
    )


__all__ = ["DeckGuide", "find_guide", "guided_weights"]
