"""Old top-level module paths must stay aliases of the relocated modules."""

from __future__ import annotations

import importlib

import pytest

MOVED = [
    ("commander_lab.decision_bundle", "commander_lab.decision.bundle"),
    ("commander_lab.decision_context", "commander_lab.decision.context"),
    ("commander_lab.decision_information", "commander_lab.decision.information"),
    ("commander_lab.decision_quality", "commander_lab.decision.quality"),
    ("commander_lab.advancement", "commander_lab.candidate_workflow.advancement"),
    ("commander_lab.candidate_evaluation", "commander_lab.candidate_workflow.evaluation"),
    ("commander_lab.candidate_screening", "commander_lab.candidate_workflow.screening"),
    ("commander_lab.cut_frontier", "commander_lab.candidate_workflow.cut_frontier"),
    ("commander_lab.variant_identity", "commander_lab.identity.variant"),
    ("commander_lab.workflow_identity", "commander_lab.identity.workflow"),
    ("commander_lab.fresh_rebuild_experiments", "commander_lab.rogshai.experiments"),
    ("commander_lab.rogshai_mvp_acceptance", "commander_lab.rogshai.mvp_acceptance"),
    ("commander_lab.first_run_preparation", "commander_lab.rogshai.first_run_preparation"),
]


@pytest.mark.parametrize(("old", "new"), MOVED)
def test_old_path_is_same_module_object(old: str, new: str) -> None:
    assert importlib.import_module(old) is importlib.import_module(new)


@pytest.mark.parametrize(("old", "new"), MOVED)
def test_monkeypatch_through_old_name_reaches_new_module(
    old: str, new: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_module = importlib.import_module(old)
    new_module = importlib.import_module(new)
    monkeypatch.setattr(old_module, "_alias_probe", 1, raising=False)
    assert new_module._alias_probe == 1  # type: ignore[attr-defined]
