from __future__ import annotations

import random

from commander_lab.models import CardRole

from .search_base import MaybeProposal, SearchEngineBase


def mana_package_proposal(
    engine: SearchEngineBase,
    mainboard: tuple[str, ...],
    value: str,
    rng: random.Random,
    n: int,
) -> MaybeProposal:
    if value != "mana_package":
        return None
    roles = frozenset({CardRole.RAMP, CardRole.SELECTION})
    return engine._generic_role_proposal(mainboard, rng, roles, n)
