from __future__ import annotations

from pathlib import Path

from commander_lab.canonical_features import (
    fuse_canonical_features,
    load_canonical_feature_annotations,
)
from commander_lab.models import CandidateProfile

from . import candidates as _legacy_candidates

_legacy_load_candidate_profiles = _legacy_candidates.load_candidate_profiles


def load_candidate_profiles(root: str | Path) -> dict[str, CandidateProfile]:
    """Load existing candidates, then add current canonical RogShai derived facts.

    Existing curated/heuristic numeric values are preserved. The overlay adds only roles, package
    membership, and provenance from the hash-bound current feature projection.
    """

    candidates = _legacy_load_candidate_profiles(root)
    annotations = load_canonical_feature_annotations(root)
    fused: dict[str, CandidateProfile] = {}
    for candidate_id, candidate in candidates.items():
        if "rogshai/current" not in candidate.allowed_deck_ids:
            fused[candidate_id] = candidate
            continue
        annotation = annotations.get(candidate.card.oracle_name)
        card = fuse_canonical_features(candidate.card, annotation)
        fused[candidate_id] = candidate.model_copy(update={"card": card})
    return fused


def canonical_feature_fusion_summary(root: str | Path) -> dict[str, int]:
    candidates = load_candidate_profiles(root)
    rogshai = [
        candidate
        for candidate in candidates.values()
        if "rogshai/current" in candidate.allowed_deck_ids
    ]
    projected = [
        candidate
        for candidate in rogshai
        if any(
            source.source_type == "canonical_drive_derived_projection"
            for source in candidate.card.sources
        )
    ]
    return {
        "rogshai_candidates_loaded": len(rogshai),
        "canonical_overlay_candidates": len(projected),
        "heuristic_or_curated_without_overlay": len(rogshai) - len(projected),
    }


# Compatibility bridge: CommanderToolService historically imports directly from .candidates.
# Package initialization imports this module before service.py, so the existing service receives
# the current loader without a broad service.py rewrite. Remove this bridge if service imports are
# later made explicit during a non-concurrent refactor.
_legacy_candidates.load_candidate_profiles = load_candidate_profiles

__all__ = ["canonical_feature_fusion_summary", "load_candidate_profiles"]
