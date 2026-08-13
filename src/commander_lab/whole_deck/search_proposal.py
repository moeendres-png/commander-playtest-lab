from __future__ import annotations

import random

from .search_land_dispatch import land_proposal
from .search_mana_package import mana_package_proposal
from .search_package_dispatch import package_proposal
from .search_models import WholeDeckNeighborhood


class _ProposalMixin:
    def propose(self, mainboard: tuple[str, ...], neighborhood: WholeDeckNeighborhood, rng: random.Random):
        n = rng.randint(self.config.minimum_neighborhood_changes, self.config.maximum_neighborhood_changes)
        result = package_proposal(self, mainboard, neighborhood.value, rng, n)
        if result is None:
            result = mana_package_proposal(self, mainboard, neighborhood.value, rng, n)
        if result is None:
            result = land_proposal(self, mainboard, neighborhood.value, rng, n)
        if result is None:
            raise ValueError(f"unsupported neighborhood: {neighborhood}")
        return result
