from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from commander_lab.first_run_preparation import (
    EXPECTED_DECK_HASH,
    FirstRunPreparationError,
    authorize_official_run,
    build_official_run_spec,
    usage_marker_path,
    validate_official_run_spec,
)

ROOT = Path(__file__).resolve().parents[2]


def test_official_spec_is_ready_not_started_and_binds_exact_shortlist() -> None:
    spec = build_official_run_spec(ROOT)

    assert spec["execution_status"] == "not_started"
    assert spec["official_run_started"] is False
    assert spec["authorization_required"] is True
    assert spec["identity"]["rogshai_hash"] == EXPECTED_DECK_HASH
    assert spec["preliminary_run"]["classification"] == (
        "preliminary_noncanonical_decision_support"
    )
    assert spec["preliminary_run"]["official_first_run"] is False
    assert {row["label"] for row in spec["shortlist"]} == {
        "rootborn_for_flare",
        "opt_for_preordain",
        "into_the_roil_for_prismari_charm",
    }
    assert all(row["physical_availability"] == "verified" for row in spec["shortlist"])
    assert all(row["commander_legality"] == "verified" for row in spec["shortlist"])
    assert all(row["constraint_status"] == "PASS" for row in spec["shortlist"])
    assert all(row["role_coverage_sufficient"] is True for row in spec["shortlist"])
    assert all(row["resource_requirements_sufficient"] is True for row in spec["shortlist"])
    assert all(row["color_requirements"] for row in spec["shortlist"])
    assert len(spec["seed_plan"]["variants_max_128"]["rootborn_for_flare"]) == 128
    assert len(spec["seed_plan"]["baseline_primary"]["exact_seeds"]) == 256
    assert all(
        len(seeds) == 64
        for seeds in spec["seed_plan"]["baseline_primary"]["by_starting_seat"].values()
    )
    assert all(len(seeds) == 32 for seeds in spec["seed_plan"]["denial_exact_seeds"].values())
    assert all(
        len(seeds) == 32 for seeds in spec["seed_plan"]["card_ablation_exact_seeds"].values()
    )
    assert all(
        len(seeds) == 32 for seeds in spec["seed_plan"]["package_ablation_exact_seeds"].values()
    )
    assert all(
        len(pod_seeds) == 32
        for variant in spec["seed_plan"]["sensitivity_variant_exact_seeds"].values()
        for pod_seeds in variant.values()
    )
    assert len(spec["seed_plan"]["full_seed_set_hash"]) == 64
    assert validate_official_run_spec(ROOT, spec) == spec


def test_official_spec_tampering_fails_closed() -> None:
    spec = build_official_run_spec(ROOT)
    spec["budgets"]["workers"] = 3

    with pytest.raises(FirstRunPreparationError, match="modified after preparation"):
        validate_official_run_spec(ROOT, spec)


def test_authorization_is_explicit_and_spec_is_single_use(tmp_path: Path) -> None:
    spec_path = tmp_path / "official.json"
    spec_path.write_text(
        json.dumps(build_official_run_spec(ROOT), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(FirstRunPreparationError, match="authorization is required"):
        authorize_official_run(ROOT, spec_path, authorized=False)

    spec, marker = authorize_official_run(ROOT, spec_path, authorized=True)
    assert marker == usage_marker_path(spec_path)
    assert marker.is_file()
    assert spec["official_run_started"] is False

    with pytest.raises(FirstRunPreparationError, match="already been consumed"):
        authorize_official_run(ROOT, spec_path, authorized=True)


def test_full_runner_requires_a_prepared_spec_before_execution(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_rogshai_first_serious_experiment.py"),
            "--output-dir",
            str(tmp_path / "run"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "--spec" in completed.stderr
    assert not (tmp_path / "run").exists()
