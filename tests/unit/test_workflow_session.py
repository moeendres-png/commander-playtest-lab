from pathlib import Path

from commander_lab.tools.service import CommanderToolService
from commander_lab.workflow_session import WorkflowSession

ROOT = Path(__file__).resolve().parents[2]


def test_workflow_session_is_deterministic_and_verified_at_close() -> None:
    service = CommanderToolService(ROOT)
    first = WorkflowSession.open(ROOT, service=service)
    second = WorkflowSession.open(ROOT, service=service)

    assert first.session_hash == second.session_hash
    assert first.context.snapshot_hash == second.context.snapshot_hash
    with first:
        assert first.verified_at_close is False
    assert first.identity()["verified_at_close"] is True
