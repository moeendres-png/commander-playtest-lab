"""Read-only repositories for canonical project data.

Domain and workflow code may depend on this package. Public tool adapters must not be a data
source for domain services.
"""

from .candidates import (
    BASIC_LANDS,
    canonical_feature_fusion_summary,
    inventory_rows,
    load_candidate_profiles,
    load_canonical_inventory_quantities,
    load_current_candidate_eligibility,
    load_current_optimization_availability,
)
from .opponents import CurrentOpponentRecord, CurrentOpponentRepository

__all__ = [
    "BASIC_LANDS",
    "CurrentOpponentRecord",
    "CurrentOpponentRepository",
    "canonical_feature_fusion_summary",
    "inventory_rows",
    "load_candidate_profiles",
    "load_canonical_inventory_quantities",
    "load_current_candidate_eligibility",
    "load_current_optimization_availability",
]
