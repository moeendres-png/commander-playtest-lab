from __future__ import annotations

import random


def land_proposal(engine, mainboard, value: str, rng: random.Random, n: int):
    if value == "land_nonland_balance":
        return engine._land_balance_proposal(mainboard, rng, n)
    if value == "basic_nonbasic_mix":
        return engine._basic_mix_proposal(mainboard, rng, n)
    return None
