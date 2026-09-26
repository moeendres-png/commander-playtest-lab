"""Compatibility exports for the canonical candidate repository.

The former import-time monkeypatch was removed in 1.20. Candidate fusion is now explicit in the
repository loader itself.
"""

from commander_lab.repositories.candidates import (
    canonical_feature_fusion_summary,
    load_candidate_profiles,
)

__all__ = ["canonical_feature_fusion_summary", "load_candidate_profiles"]
