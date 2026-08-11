from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from commander_lab.engine.structural.project import (
    _merge_unique_structural_profiles,
    _validate_structural_profile_ids,
)
from commander_lab.models import StructuralDeckProfile

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "tools/project_invariant_audit.py"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _run_audit(root: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(AUDIT), "--root", str(root)],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed, json.loads(completed.stdout)


def _failed_check_ids(report: dict[str, object]) -> set[str]:
    checks = cast(list[dict[str, object]], report["checks"])
    return {str(check["id"]) for check in checks if check["status"] == "FAIL"}


def test_structural_profile_config_rejects_duplicate_deck_ids(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    _write_json(
        path,
        {
            "profiles": [
                {"deck_id": "opponent/duplicate"},
                {"deck_id": "opponent/duplicate"},
            ]
        },
    )

    with pytest.raises(ValueError, match="duplicate structural deck_id"):
        _validate_structural_profile_ids(path)


def test_structural_profile_merge_rejects_cross_source_collision() -> None:
    profile = cast(StructuralDeckProfile, object())
    target = {"opponent/duplicate": profile}
    incoming = {"opponent/duplicate": profile}

    with pytest.raises(ValueError, match="structural deck_id collision"):
        _merge_unique_structural_profiles(target, incoming, source="supplemental.json")


def test_project_invariant_auditor_passes_current_repo() -> None:
    completed, report = _run_audit(ROOT)
    checks = cast(list[dict[str, object]], report["checks"])
    summary = cast(dict[str, int], report["summary"])
    statuses = {str(check["id"]): str(check["status"]) for check in checks}

    assert completed.returncode == 0
    assert summary["fail"] == 0
    assert statuses["unique_structural_profile_ids"] == "PASS"
    assert statuses["official_precon_integrity"] == "PASS"
    assert statuses["structural_evidence_boundaries"] == "PASS"
    assert statuses["opponent_registry_referential_integrity"] == "PASS"
    assert statuses["opponent_alias_referential_integrity"] == "PASS"
    assert statuses["kaervek_frozen_reference_present"] == "PASS"


def test_project_invariant_auditor_fails_closed_on_broken_fixture(tmp_path: Path) -> None:
    opponent_dir = tmp_path / "data/opponents"
    _write_json(
        opponent_dir / "current_structural_profiles.json",
        {
            "profiles": [
                {"deck_id": "opponent/duplicate"},
                {"deck_id": "opponent/duplicate"},
            ]
        },
    )
    _write_json(
        opponent_dir / "opponent_registry.json",
        {
            "current": {"duplicate/current": "opponent/duplicate"},
            "aliases": {"broken/alias": {"redirect": "opponent/missing"}},
        },
    )

    completed, report = _run_audit(tmp_path)

    assert completed.returncode == 1
    failures = _failed_check_ids(report)
    assert "unique_structural_profile_ids" in failures
    assert "opponent_alias_referential_integrity" in failures


def test_project_invariant_auditor_rejects_invalid_official_precon_quantity(
    tmp_path: Path,
) -> None:
    opponent_dir = tmp_path / "data/opponents"
    _write_json(opponent_dir / "current_structural_profiles.json", {"profiles": []})
    _write_json(
        opponent_dir / "broken_precon.json",
        {
            "profile_id": "opponent/broken-precon",
            "list_status": "official_precon",
            "deck": {"cards": [{"oracle_name": "Test Card", "quantity": 99}]},
        },
    )
    _write_json(
        opponent_dir / "opponent_registry.json",
        {
            "current": {
                "broken/precon": "opponent/broken-precon",
                "kaervek/current": "kaervek/current",
            },
            "aliases": {},
            "kaervek_deck_hash": "frozen-test-hash",
        },
    )

    completed, report = _run_audit(tmp_path)

    assert completed.returncode == 1
    assert "official_precon_integrity" in _failed_check_ids(report)


def test_project_invariant_auditor_rejects_structural_evidence_promotion(
    tmp_path: Path,
) -> None:
    opponent_dir = tmp_path / "data/opponents"
    _write_json(
        opponent_dir / "current_structural_profiles.json",
        {
            "profiles": [
                {
                    "deck_id": "opponent/evidence-bad",
                    "evidence_kinds": ["synthetic_completion", "directly_observed"],
                    "source_status": "external_rules_engine",
                }
            ]
        },
    )
    _write_json(
        opponent_dir / "opponent_registry.json",
        {
            "current": {
                "evidence/bad": "opponent/evidence-bad",
                "kaervek/current": "kaervek/current",
            },
            "aliases": {},
            "kaervek_deck_hash": "frozen-test-hash",
        },
    )

    completed, report = _run_audit(tmp_path)

    assert completed.returncode == 1
    assert "structural_evidence_boundaries" in _failed_check_ids(report)
