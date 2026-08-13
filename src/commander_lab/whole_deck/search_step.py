from __future__ import annotations

import random

from .search_models import WholeDeckMutation, WholeDeckNeighborhood


def explore_start(engine, current, seed, archive):
    rng = random.Random(seed)
    neighborhoods = tuple(WholeDeckNeighborhood)
    for step in range(engine.config.max_steps_per_start):
        neighborhood = neighborhoods[(step + rng.randrange(len(neighborhoods))) % len(neighborhoods)]
        proposal_board, removed, added = engine.propose(current.mainboard, neighborhood, rng)
        if proposal_board == current.mainboard or not removed or not added:
            continue
        mutation = WholeDeckMutation(
            neighborhood=neighborhood,
            removed=removed,
            added=added,
            changed_slots=max(len(removed), len(added)),
        )
        proposal = engine._evaluate(
            proposal_board,
            seed=seed,
            parent_variant_id=current.variant_id,
            mutation=mutation,
        )
        delta = proposal.objective_prior - current.objective_prior
        accepted = False
        accepted_worse = False
        if proposal.hard_gate.valid:
            accepted, accepted_worse = engine._accept(delta, engine._temperature(step), rng)
        proposal = proposal.model_copy(
            update={
                "mutation": mutation.model_copy(
                    update={
                        "accepted": accepted,
                        "accepted_worse": accepted_worse,
                        "objective_delta": delta,
                    }
                )
            }
        )
        archive.setdefault(proposal.variant_id, proposal)
        if accepted:
            current = proposal
        if len(archive) >= engine.config.archive_limit:
            break
    return current
