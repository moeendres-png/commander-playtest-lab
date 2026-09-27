from __future__ import annotations

import pytest

from commander_lab.whole_deck.optimizer_v2_decision_runtime import (
    _require_uncensored_decision_evidence,
)


def test_decision_boundary_accepts_complete_structural_pairs() -> None:
    _require_uncensored_decision_evidence(
        {
            "decision_evidence_eligible": True,
            "censored_pair_count": 0,
        },
        evidence_context="confirmatory",
    )


def test_decision_boundary_rejects_aborted_structural_pairs() -> None:
    with pytest.raises(RuntimeError, match="censored_pair_count=2"):
        _require_uncensored_decision_evidence(
            {
                "decision_evidence_eligible": False,
                "censored_pair_count": 2,
            },
            evidence_context="confirmatory",
        )


def test_missing_censoring_contract_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="censored_pair_count=unknown"):
        _require_uncensored_decision_evidence({}, evidence_context="holdout")
