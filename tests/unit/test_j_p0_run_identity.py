from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from commander_lab import __version__
from commander_lab.evals.golden import load_golden_cases
from commander_lab.models.run_identity import IdentityStatus, RunIdentity
from commander_lab.storage.run_identity import normalize_run_paths, sha256_run_value


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
