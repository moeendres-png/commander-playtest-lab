from __future__ import annotations

import random

from .search_base import MaybeProposal, SearchEngineBase


def land_proposal(
    engine: SearchEngineBase,
    mainboard: tuple[str, ...],
    value: str,
    rng: random.Random,
    n: int,
) -> MaybeProposal:
    if value == "land_nonland_balance":
        return engine._land_balance_proposal(mainboard, rng, n)
    if value == "basic_nonbasic_mix":
        return engine._basic_mix_proposal(mainboard, rng, n)
    return None
