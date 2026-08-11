from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class AdaptiveBudgetPolicy:
    """Small deterministic racing policy; statistical effects remain model-internal."""

    small_batch: int = 8
    full_budget: int = 24
    minimum_simulation_reduction: float = 0.30

    def __post_init__(self) -> None:
        if self.small_batch < 1:
            raise ValueError("small_batch must be positive")
        if self.full_budget <= self.small_batch:
            raise ValueError("full_budget must exceed small_batch")
        if not 0.0 < self.minimum_simulation_reduction < 1.0:
            raise ValueError("minimum_simulation_reduction must be between zero and one")

    def select_small_batch(self, screen_buckets: Mapping[str, str]) -> tuple[str, ...]:
        return tuple(
            sorted(
                candidate_id
                for candidate_id, bucket in screen_buckets.items()
                if bucket in {"advance", "explore"}
            )
        )

    def select_finalists(
        self,
        *,
        screen_buckets: Mapping[str, str],
        placement_improvement: Mapping[str, float],
        monte_carlo_standard_error: Mapping[str, float],
    ) -> tuple[str, ...]:
        tested = self.select_small_batch(screen_buckets)
        if not tested:
            return ()
        advance = [candidate_id for candidate_id in tested if screen_buckets[candidate_id] == "advance"]
        if advance:
            finalists = set(advance)
            leader = max(advance, key=lambda candidate_id: placement_improvement[candidate_id])
        else:
            leader = max(tested, key=lambda candidate_id: placement_improvement[candidate_id])
            finalists = {leader}

        leader_effect = placement_improvement[leader]
        leader_mcse = max(0.0, monte_carlo_standard_error[leader])
        for candidate_id in tested:
            if candidate_id in finalists:
                continue
            effect = placement_improvement[candidate_id]
            mcse = max(0.0, monte_carlo_standard_error[candidate_id])
            # Promote unresolved candidates whose simple uncertainty bands still overlap the best
            # advance candidate. This is a deterministic racing heuristic, not a significance test.
            uncertainty_margin = 1.96 * (leader_mcse + mcse)
            if effect + uncertainty_margin >= leader_effect:
                finalists.add(candidate_id)
        return tuple(sorted(finalists))

    def simulation_reduction(
        self,
        *,
        full_control_candidates: int,
        small_batch_candidates: int,
        finalists: int,
    ) -> float:
        full = full_control_candidates * self.full_budget
        if full <= 0:
            return 0.0
        raced = small_batch_candidates * self.small_batch + finalists * self.full_budget
        return 1.0 - raced / full


__all__ = ["AdaptiveBudgetPolicy"]
