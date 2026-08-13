from __future__ import annotations

import math
import random

from .search_base import SearchEngineBase


class _AcceptanceMixin(SearchEngineBase):
    def _temperature(self, step: int) -> float:
        if self.config.max_steps_per_start <= 1:
            return self.config.final_temperature
        fraction = step / (self.config.max_steps_per_start - 1)
        return (
            self.config.initial_temperature * (1.0 - fraction)
            + self.config.final_temperature * fraction
        )

    def _accept(
        self, delta: float, temperature: float, rng: random.Random
    ) -> tuple[bool, bool]:
        if delta >= 0.0:
            return True, False
        probability = math.exp(max(-50.0, delta / max(temperature, 1e-9)))
        accepted = rng.random() < probability
        return accepted, accepted
