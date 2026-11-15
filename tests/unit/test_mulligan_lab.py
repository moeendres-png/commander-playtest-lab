from __future__ import annotations

from commander_lab.models import (
    MulliganContext,
    MulliganGamePlan,
)


def context(deck, *, ensemble=None, seed=7):
    return MulliganContext(
        deck_id=deck.deck_id,
        deck_hash=deck.deck_hash,
        opponent_ensemble_id=ensemble,
        seat_position=1,
        starting_player=False,
        pod_size=4,
        pilot_profile_id="test-pilot",
        pilot_version="1",
        game_plan=MulliganGamePlan.BALANCED,
        seed=seed,
    )


def names(deck, wanted):
    pool = {}
    for card in deck.cards:
        if card.oracle_name not in deck.commander_names:
            pool.setdefault(card.oracle_name, []).append(card)
    result = []
    used = {}
    for name in wanted:
        i = used.get(name, 0)
        result.append(pool[name][i])
        used[name] = i + 1
    return tuple(result)
