"""External complete-deck candidate contracts and lossless gameplay handoff."""

from .contracts import (
    CANDIDATE_PIPELINE_RUNTIME_VERSION,
    DECK_CANDIDATE_SET_SCHEMA_VERSION,
    STRUCTURAL_SIMULATION_DECISION_AUTHORITY,
    TACTICAL_DECISION_AUTHORITY,
    XMAGE_TARGET_RULES_AUTHORITY,
)
from .io import load_candidate_set, write_json
from .models import (
    CandidateValidationReport,
    DeckCandidate,
    DeckCandidateSet,
    FutureXmageScenario,
    PreSimulationInvariantReport,
    SimulationCandidateQueue,
)
from .normalization import canonical_deck_hash, normalize_candidate_set
from .pipeline import build_simulation_queue

__all__ = [
    "CANDIDATE_PIPELINE_RUNTIME_VERSION",
    "DECK_CANDIDATE_SET_SCHEMA_VERSION",
    "STRUCTURAL_SIMULATION_DECISION_AUTHORITY",
    "TACTICAL_DECISION_AUTHORITY",
    "XMAGE_TARGET_RULES_AUTHORITY",
    "CandidateValidationReport",
    "DeckCandidate",
    "DeckCandidateSet",
    "FutureXmageScenario",
    "PreSimulationInvariantReport",
    "SimulationCandidateQueue",
    "build_simulation_queue",
    "canonical_deck_hash",
    "load_candidate_set",
    "normalize_candidate_set",
    "write_json",
]
