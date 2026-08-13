from __future__ import annotations

import random

from commander_lab.models import CardRole


def mana_package_proposal(engine, mainboard, value: str, rng: random.Random, n: int):
    if value != "mana_package":
        return None
    roles = frozenset({CardRole.RAMP, CardRole.SELECTION})
    return engine._generic_role_proposal(mainboard, rng, roles, n)
