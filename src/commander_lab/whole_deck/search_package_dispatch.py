from __future__ import annotations

import random

from commander_lab.models import CardRole

from .search_base import MaybeProposal, SearchEngineBase
from .search_context import ENGINE_ROLES, FINISH_ROLES, INTERACTION_ROLES


def package_proposal(
    engine: SearchEngineBase,
    mainboard: tuple[str, ...],
    value: str,
    rng: random.Random,
    n: int,
) -> MaybeProposal:
    if value == "role_package":
        role = rng.choice(list(CardRole))
        return engine._generic_role_proposal(mainboard, rng, frozenset({role}), n)
    if value == "engine_package":
        return engine._package_proposal(mainboard, rng, ENGINE_ROLES, n)
    if value == "finish_package":
        return engine._package_proposal(mainboard, rng, FINISH_ROLES, n)
    if value == "interaction_package":
        return engine._package_proposal(mainboard, rng, INTERACTION_ROLES, n)
    if value == "curve_band":
        return engine._curve_proposal(mainboard, rng, n)
    return None
