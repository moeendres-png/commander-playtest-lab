from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from commander_lab.decision_statistics import paired_bootstrap_interval

SEQUENTIAL_POLICY_VERSION = "bonferroni-staged-1.0.0"


@dataclass(frozen=True, slots=True)
class SequentialPlan:
    total_looks: int
    familywise_alpha: float = 0.05
    policy_version: str = SEQUENTIAL_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.total_looks < 1:
            raise ValueError("total_looks must be positive")
        if not 0.0 < self.familywise_alpha < 1.0:
            raise ValueError("familywise_alpha must be between zero and one")

    @property
    def alpha_per_look(self) -> float:
        return self.familywise_alpha / self.total_looks

    @property
    def controlled_confidence(self) -> float:
        return 1.0 - self.alpha_per_look

    @property
    def allocated_alpha(self) -> float:
        return self.alpha_per_look * self.total_looks

    def validate_look(self, look_index: int) -> None:
        if look_index < 1 or look_index > self.total_looks:
            raise ValueError("look_index is outside the preregistered sequential plan")


def sequential_bootstrap_interval(
    values: Sequence[float],
    *,
    look_index: int,
    total_looks: int,
    familywise_alpha: float = 0.05,
    iterations: int = 4_000,
    seed: int = 0,
) -> tuple[float, float]:
    """Return a per-look bootstrap interval under a preregistered Bonferroni plan.

    This is a conservative v1 optional-stopping safeguard for a fixed, known number of cumulative
    looks. It controls repeated looks for one candidate. Search-wide multiplicity is handled by
    fresh confirmatory/final-validation partitions rather than by treating exploratory results as
    final evidence.
    """

    plan = SequentialPlan(total_looks=total_looks, familywise_alpha=familywise_alpha)
    plan.validate_look(look_index)
    return paired_bootstrap_interval(
        values,
        confidence=plan.controlled_confidence,
        iterations=iterations,
        seed=seed,
    )


__all__ = [
    "SEQUENTIAL_POLICY_VERSION",
    "SequentialPlan",
    "sequential_bootstrap_interval",
]
