from __future__ import annotations

import random

from .models import PolicyId
from .search_base import SearchEngineBase, SearchStart


def build_starts(
    engine: SearchEngineBase, current_control: tuple[str, ...] | None
) -> list[SearchStart]:
    master = random.Random(engine.config.seed)
    starts: list[SearchStart] = []
    constructive_seed = master.randrange(0, 2**31)
    starts.append(("policy_constructive", engine.constructive_start(), constructive_seed))
    for index in range(engine.config.diversified_starts):
        seed = master.randrange(0, 2**31)
        starts.append(
            (
                f"diversified_{index}",
                engine.constructive_start(rng=random.Random(seed), diversified=True),
                seed,
            )
        )
    if engine.policy.policy_id == PolicyId.CURRENT_CONTROL and current_control is not None:
        starts.append(("current_control_search_start", current_control, engine.config.seed))
    return starts
