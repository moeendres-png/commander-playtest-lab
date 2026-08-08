from .batch import aggregate_structural_results, derive_match_seed
from .fixtures import build_synthetic_deck_profile
from .profiles import (
    StructuralProfileCatalog,
    build_default_profile,
    build_structural_deck_profile,
    generate_project_profiles,
    role_counts,
)
from .project import load_project_structural_decks
from .scheduling import effective_worker_count, run_structural_batch
from .simulator import (
    ENGINE_VERSION,
    StructuralSimulator,
    commander_cast_cost,
    commander_damage_is_lethal,
)
from .triggers import AbstractTrigger, order_simultaneous_triggers, trigger_resolution_order
from .validation import VALIDATION_SCENARIOS, run_phase3_validation

__all__ = [
    "ENGINE_VERSION",
    "VALIDATION_SCENARIOS",
    "AbstractTrigger",
    "StructuralProfileCatalog",
    "StructuralSimulator",
    "aggregate_structural_results",
    "build_default_profile",
    "build_structural_deck_profile",
    "build_synthetic_deck_profile",
    "commander_cast_cost",
    "commander_damage_is_lethal",
    "derive_match_seed",
    "effective_worker_count",
    "generate_project_profiles",
    "load_project_structural_decks",
    "order_simultaneous_triggers",
    "role_counts",
    "run_phase3_validation",
    "run_structural_batch",
    "trigger_resolution_order",
]
