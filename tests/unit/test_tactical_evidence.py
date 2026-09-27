from __future__ import annotations

import pytest

from commander_lab.tactical_evidence import (
    TacticalEvidenceExecutionStatus,
    TacticalEvidenceRequest,
    TacticalEvidenceResult,
)


def test_tactical_request_has_content_addressed_fixture_identity() -> None:
    request = TacticalEvidenceRequest(
        question_id="priority-stack-fixture",
        initial_state_hash="a" * 64,
        relevant_cards=("Silence", "Counterspell"),
        rules_question="Which declared actions are legal in the bounded priority window?",
        permitted_action_scope=("cast", "pass_priority"),
    )
    assert len(request.fixture_hash) == 64
    assert request.fixture_hash == request.fixture_hash


def test_external_pass_fails_closed_without_complete_provider_binding() -> None:
    with pytest.raises(ValueError, match="provider/version/commit/fixture"):
        TacticalEvidenceResult(
            question_id="fixture",
            execution_status=TacticalEvidenceExecutionStatus.PASS,
            provider="forge",
        )


def test_not_run_is_not_pass_and_needs_no_fake_provider() -> None:
    result = TacticalEvidenceResult(
        question_id="fixture",
        execution_status=TacticalEvidenceExecutionStatus.NOT_RUN,
    )
    assert result.execution_status != TacticalEvidenceExecutionStatus.PASS
    assert result.provider is None
