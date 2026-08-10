from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from commander_lab import __version__
from commander_lab.evals.golden import load_golden_cases
from commander_lab.models import InspectDeckInput, SwapMatrixInput, ToolStatus
from commander_lab.models.run_identity import CanonicalInputStatus, IdentityStatus, RunIdentity
from commander_lab.storage.run_identity import normalize_run_paths, sha256_run_value
from commander_lab.tools import CommanderToolService
from commander_lab.tools.service import ToolExecutionError


def test_canonical_run_hash_is_mapping_order_and_unicode_stable(tmp_path: Path) -> None:
    left = {"b": 2, "a": "e\u0301", "nested": {"y": -0.0, "x": 1.25}}
    right = {"nested": {"x": 1.25, "y": 0.0}, "a": "é", "b": 2}
    assert sha256_run_value(left, root=tmp_path) == sha256_run_value(right, root=tmp_path)


def test_semantic_change_changes_run_hash(tmp_path: Path) -> None:
    baseline = {"seed": 7, "deck_hashes": {"korvold/current": "a" * 64}}
    variant = {"seed": 8, "deck_hashes": {"korvold/current": "a" * 64}}
    assert sha256_run_value(baseline, root=tmp_path) != sha256_run_value(variant, root=tmp_path)


def test_project_paths_normalize_across_absolute_and_relative_forms(repo_root: Path) -> None:
    relative = {"scenario_path": "data/evals/golden/pilot_decisions_g.json"}
    absolute = {"scenario_path": str(repo_root / "data/evals/golden/pilot_decisions_g.json")}
    assert normalize_run_paths(relative, root=repo_root) == normalize_run_paths(
        absolute, root=repo_root
    )


def test_missing_required_identity_component_fails_closed() -> None:
    with pytest.raises(ValidationError, match="missing required components"):
        RunIdentity(
            component_status={"inventory_hash": IdentityStatus.MISSING_REQUIRED},
            run_identity_hash="0" * 64,
        )


def test_j_holdout_is_schema_valid_frozen_and_independently_consumed(
    repo_root: Path,
) -> None:
    holdout_path = repo_root / "data/evals/holdout/pilot_decisions_j_v1.json"
    registry = json.loads(
        (repo_root / "data/evals/j_eval_registry.json").read_text(encoding="utf-8")
    )
    cases = load_golden_cases(holdout_path)
    holdout = registry["sets"]["UNTOUCHED_HOLDOUT"]

    assert len(cases) == 12
    assert {case.strategy for case in cases} == {"korvold", "rogshai"}
    assert {case.state.pod_size for case in cases} == {3, 4, 5}
    assert all(case.scenario_group == "holdout" for case in cases)
    assert holdout["id"] == "J_HOLDOUT_v1"
    assert holdout["hash"] == "724e84f1ea34bea9ec6b37929d945724c77c408a464b3a9dd05235738a00d5d6"
    assert holdout["members"] == [
        {
            "path": "data/evals/holdout/pilot_decisions_j_v1.json",
            "sha256": "a5875cd1a8edf6bbf79248b3e4ba26151579f628eaeefd4ef2369abb309da8d1",
        }
    ]
    assert holdout["mutable"] is False
    assert holdout["used_for_tuning"] is False
    assert holdout["first_evaluation_timestamp"] == "2026-08-10T08:06:01Z"
    assert registry["holdout_policy"]["no_tuning_on_holdout"] is True
    assert (
        registry["holdout_policy"][
            "phase_reopen_after_holdout_requires_new_version_or_loss_of_independence"
        ]
        is True
    )


def test_runtime_version_matches_declared_package_version(repo_root: Path) -> None:
    declared = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    assert __version__ == declared


def test_tool_metadata_contains_universal_run_identity(repo_root: Path) -> None:
    service = CommanderToolService(repo_root)
    response = service.inspect_deck(InspectDeckInput(deck_id="korvold/current"))

    assert response.status == ToolStatus.COMPLETED
    identity = response.metadata.run_identity
    assert identity.software_commit == service.git_commit
    assert identity.software_tree == service.git_tree
    assert identity.package_version == __version__
    assert identity.inventory_source_id
    assert identity.inventory_hash
    assert identity.commander_configuration_hash
    assert identity.data_source_manifest_hash
    assert identity.canonical_input_status == CanonicalInputStatus.CURRENT
    assert identity.component_status["software_tree"] == IdentityStatus.PRESENT
    assert response.metadata.run_identity_hash == identity.run_identity_hash


def test_stale_deck_fails_canonical_run_but_historical_replay_is_explicit(repo_root: Path) -> None:
    service = CommanderToolService(repo_root)
    current = service.decks["korvold/current"]
    service.decks["korvold/current"] = current.model_copy(update={"deck_hash": "0" * 64})

    with pytest.raises(ToolExecutionError, match="stale canonical inputs rejected"):
        service.build_run_identity(
            {"deck_id": "korvold/current", "canonical_inputs_required": True},
            ("korvold/current",),
            tool_name="inspect_deck",
        )

    replay = service.build_run_identity(
        {
            "deck_id": "korvold/current",
            "canonical_inputs_required": True,
            "historical_replay": True,
        },
        ("korvold/current",),
        tool_name="inspect_deck",
    )
    assert replay.historical_replay is True
    assert replay.canonical_input_status == CanonicalInputStatus.HISTORICAL_REPLAY
    assert replay.stale_reasons


def test_tactical_and_external_engine_identity_are_not_conflated(repo_root: Path) -> None:
    service = CommanderToolService(repo_root)
    tactical = service.build_run_identity(
        {"canonical_inputs_required": True},
        tool_name="run_tactical_fixture",
        estimate_type="tactical_oracle_results",
    )
    external = service.build_run_identity(
        {"canonical_inputs_required": True, "provider": "xmage"},
        tool_name="run_engine_backed_matchup",
        estimate_type="external_rules_engine_results",
    )

    assert tactical.engine_mode == "tactical_oracle"
    assert tactical.engine_provider == "tactical_oracle"
    assert external.engine_mode == "external"
    assert external.engine_provider == "xmage"
    assert external.component_status["engine_provider_version_or_pin"] == IdentityStatus.UNKNOWN
    assert external.component_status["engine_capability_hash"] == IdentityStatus.UNKNOWN


def test_optimizer_tool_response_carries_source_identity(repo_root: Path) -> None:
    service = CommanderToolService(repo_root)
    response = service.generate_swap_matrix(
        SwapMatrixInput(
            deck_id="korvold/current",
            remove_cards=("Aftermath Analyst",),
            add_candidate_ids=("korvold/mazirek-smoke",),
            simulate_valid_cells=False,
            iterations_per_cell=1,
        )
    )

    assert response.status == ToolStatus.COMPLETED
    identity = response.metadata.run_identity
    assert identity.deck_hashes["korvold/current"] == service.decks["korvold/current"].deck_hash
    assert identity.inventory_hash
    assert identity.policy_hash
    assert identity.data_source_manifest_hash


def test_pilot_ensemble_id_is_not_treated_as_opponent_ensemble(repo_root: Path) -> None:
    from commander_lab.models import RunPilotEnsembleInput

    service = CommanderToolService(repo_root)
    identity = service.build_run_identity(
        RunPilotEnsembleInput(
            deck_id="rogshai/current",
            ensemble_id="rogshai.equal.v1",
            iterations=1,
            seed=731,
            max_turns=8,
        ),
        ("rogshai/current",),
        tool_name="run_pilot_ensemble",
    )
    assert identity.opponent_ensemble_hash is None
    assert identity.component_status["opponent_ensemble_hash"] == IdentityStatus.NOT_APPLICABLE
