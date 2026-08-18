"""Compatibility adapter for candidate repository access.

New domain code must import :mod:`commander_lab.repositories.candidates` directly. This module
contains no loader implementation and performs no import-time mutation.
"""

from commander_lab.repositories.candidates import (
    BASIC_LANDS,
    DECK_COLORS,
    canonical_feature_fusion_summary,
    inventory_rows,
    load_candidate_profiles,
    load_canonical_inventory_quantities,
    load_current_candidate_eligibility,
    load_current_optimization_availability,
    load_current_optimization_availability_by_deck,
)

_inventory_rows = inventory_rows

__all__ = [
    "BASIC_LANDS",
    "DECK_COLORS",
    "canonical_feature_fusion_summary",
    "inventory_rows",
    "load_candidate_profiles",
    "load_canonical_inventory_quantities",
    "load_current_candidate_eligibility",
    "load_current_optimization_availability",
    "load_current_optimization_availability_by_deck",
]
