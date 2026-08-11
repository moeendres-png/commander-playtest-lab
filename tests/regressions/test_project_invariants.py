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
from tools.project_invariant_audit import audit_project

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


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
    report = audit_project(ROOT)
    statuses = {check["id"]: check["status"] for check in report["checks"]}

    assert report["summary"]["fail"] == 0
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

    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools/project_invariant_audit.py"), "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    failures = {check["id"] for check in report["checks"] if check["status"] == "FAIL"}

    assert completed.returncode == 1
    assert "unique_structural_profile_ids" in failures
    assert "opponent_alias_referential_integrity" in failures
