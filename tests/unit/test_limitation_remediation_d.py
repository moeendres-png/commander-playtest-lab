from __future__ import annotations

from pathlib import Path
from types import MethodType

import pytest
from pydantic import ValidationError

from commander_lab.models import (
    CounterfactualAction,
    CounterfactualBranchpoint,
    CounterfactualEngineMode,
    InspectDeckInput,
    RunPolicyEvalInput,
    ToolStatus,
)
from commander_lab.models.primer import CompiledPilotPolicy
from commander_lab.tools import CommanderToolService


def test_tool_metadata_binds_complete_run_identity(repo_root: Path) -> None:
    service = CommanderToolService(repo_root)
    response = service.inspect_deck(InspectDeckInput(deck_id="rogshai/current"))

    assert response.status == ToolStatus.COMPLETED
    metadata = response.metadata
    assert len(metadata.inventory_hash) == 64
    assert len(metadata.policy_hash) == 64
    assert len(metadata.meta_snapshot_hash) == 64
    assert len(metadata.opponent_registry_hash) == 64
    assert len(metadata.run_identity_hash) == 64
    assert metadata.deck_hashes["rogshai/current"] == service.decks["rogshai/current"].deck_hash
    assert metadata.pilot_hashes
    assert metadata.pilot_parameter_hashes
    assert "source:inventory" in metadata.data_snapshot_hashes
    assert "source:korvold_rogshai_decks" in metadata.data_snapshot_hashes
    assert "source:opponent_baselines" in metadata.data_snapshot_hashes


def test_invoke_rejects_run_identity_drift(repo_root: Path) -> None:
    service = CommanderToolService(repo_root)
    real_identity = service._run_identity({"deck_id": "rogshai/current"}, ("rogshai/current",))
    changed = dict(real_identity)
    changed["run_identity_hash"] = "0" * 64
    calls = iter((real_identity, changed))

    def fake_identity(
        self: CommanderToolService,
        scenario: object,
        deck_ids: tuple[str, ...],
        **_: object,
    ):
        return next(calls)

    service._run_identity = MethodType(fake_identity, service)  # type: ignore[method-assign]
    response = service._invoke(
        "inspect_deck",
        InspectDeckInput(deck_id="rogshai/current"),
        lambda: {"ok": True},
        deck_ids=("rogshai/current",),
    )
    assert response.status == ToolStatus.FAILED
    assert any("run identity drift detected" in error for error in response.errors)


def test_policy_eval_rejects_policy_for_different_current_deck(
    repo_root: Path, tmp_path: Path
) -> None:
    service = CommanderToolService(repo_root)
    original = CompiledPilotPolicy.model_validate_json(
        (repo_root / "data/primer_rules/policies/rogshai_current_policy-1.0.1.json").read_text(
            encoding="utf-8"
        )
    )
    wrong_rules = tuple(rule.model_copy(update={"deck_hash": "0" * 64}) for rule in original.rules)
    wrong = original.model_copy(update={"deck_hash": "0" * 64, "rules": wrong_rules})
    policy_path = tmp_path / "wrong-policy.json"
    policy_path.write_text(wrong.model_dump_json(), encoding="utf-8")
    scenario_path = repo_root / "data/primer_rules/evals/golden_scenarios.json"
    real_project_path = service._project_path

    def mapped_project_path(self: CommanderToolService, relative: str) -> Path:
        if relative == "wrong-policy.json":
            return policy_path
        if relative == "golden_scenarios.json":
            return scenario_path
        return real_project_path(relative)

    service._project_path = MethodType(mapped_project_path, service)  # type: ignore[method-assign]
    response = service.run_policy_eval(
        RunPolicyEvalInput(
            policy_path="wrong-policy.json",
            scenario_path="golden_scenarios.json",
            deck_id="rogshai/current",
            strategy="rogshai",
            output_name="should-not-exist.json",
        )
    )
    assert response.status == ToolStatus.FAILED
    assert any("does not match current deck" in error for error in response.errors)


def test_counterfactual_branchpoint_validation_level_must_match_engine() -> None:
    with pytest.raises(ValidationError, match="requires validation_level=tactical_oracle"):
        CounterfactualBranchpoint(
            branchpoint_id="b1",
            source_run_id="run",
            source_path="events.jsonl",
            game_id="g1",
            event_offset=0,
            actor_id="p1",
            state_hash="1" * 64,
            replay_prefix_hash="2" * 64,
            available_actions=(CounterfactualAction(action_id="pass"),),
            chosen_action="pass",
            engine_mode=CounterfactualEngineMode.TACTICAL_ORACLE,
            validation_level="structural_model_estimates",
        )
