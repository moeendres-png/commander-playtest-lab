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
    _write_json(path, {"profiles": [{"deck_id": "opponent/duplicate"}] * 2})
    with pytest.raises(ValueError, match="duplicate structural deck_id"):
        _validate_structural_profile_ids(path)


def test_structural_profile_merge_rejects_cross_source_collision() -> None:
    profile = cast(StructuralDeckProfile, object())
    with pytest.raises(ValueError, match="structural deck_id collision"):
        _merge_unique_structural_profiles(
            {"opponent/duplicate": profile},
            {"opponent/duplicate": profile},
            source="supplemental.json",
        )


def test_project_invariant_auditor_passes_current_repo() -> None:
    completed, report = _run_audit(ROOT)
    statuses = {
        str(check["id"]): str(check["status"])
        for check in cast(list[dict[str, object]], report["checks"])
    }
    assert completed.returncode == 0
    assert report["error_code"] is None
    assert statuses["unique_structural_profile_ids"] == "PASS"
    assert statuses["official_precon_integrity"] == "PASS"
    assert statuses["structural_evidence_boundaries"] == "PASS"
    assert statuses["opponent_registry_referential_integrity"] == "PASS"
    assert statuses["opponent_alias_referential_integrity"] == "PASS"
    assert statuses["kaervek_frozen_semantics"] == "PASS"


def _minimal_registry(target: str = "opponent/fixture") -> dict[str, object]:
    return {
        "current": {"fixture/current": target, "kaervek/current": "kaervek/current"},
        "aliases": {},
        "kaervek_deck_hash": "a" * 64,
    }


def test_auditor_rejects_duplicate_ids_within_and_between_sources(tmp_path: Path) -> None:
    opponent_dir = tmp_path / "data/opponents"
    _write_json(
        opponent_dir / "current_structural_profiles.json",
        {"profiles": [{"deck_id": "opponent/fixture"}] * 2},
    )
    _write_json(
        opponent_dir / "supplemental_structural_profile.json",
        {"profiles": [{"deck_id": "opponent/fixture"}]},
    )
    _write_json(opponent_dir / "opponent_registry.json", _minimal_registry())
    completed, report = _run_audit(tmp_path)
    assert completed.returncode == 1
    assert report["error_code"] == "PROJECT_INVARIANT_VIOLATION"
    assert "unique_structural_profile_ids" in _failed_check_ids(report)


def test_auditor_rejects_broken_alias_and_registry_target(tmp_path: Path) -> None:
    opponent_dir = tmp_path / "data/opponents"
    _write_json(opponent_dir / "current_structural_profiles.json", {"profiles": []})
    registry = _minimal_registry("opponent/missing")
    cast(dict[str, object], registry["aliases"])["broken/alias"] = {
        "redirect": "opponent/also-missing"
    }
    _write_json(opponent_dir / "opponent_registry.json", registry)
    completed, report = _run_audit(tmp_path)
    assert completed.returncode == 1
    failures = _failed_check_ids(report)
    assert "opponent_alias_referential_integrity" in failures
    assert "opponent_registry_referential_integrity" in failures


def test_auditor_rejects_invalid_precon_quantity_and_evidence_promotion(tmp_path: Path) -> None:
    opponent_dir = tmp_path / "data/opponents"
    _write_json(
        opponent_dir / "current_structural_profiles.json",
        {
            "profiles": [
                {
                    "deck_id": "opponent/fixture",
                    "evidence_kinds": ["synthetic_completion", "directly_observed"],
                    "source_status": "external_rules_engine",
                }
            ]
        },
    )
    _write_json(
        opponent_dir / "fixture_precon.json",
        {
            "profile_id": "opponent/precon",
            "list_status": "official_precon",
            "deck": {"cards": [{"oracle_name": "Fixture", "quantity": 99}]},
        },
    )
    _write_json(opponent_dir / "opponent_registry.json", _minimal_registry())
    completed, report = _run_audit(tmp_path)
    assert completed.returncode == 1
    failures = _failed_check_ids(report)
    assert "official_precon_integrity" in failures
    assert "structural_evidence_boundaries" in failures


def test_auditor_rejects_kaervek_freeze_hash_mismatch(tmp_path: Path) -> None:
    opponent_dir = tmp_path / "data/opponents"
    _write_json(
        opponent_dir / "current_structural_profiles.json",
        {"profiles": [{"deck_id": "kaervek/current", "deck_hash": "b" * 64}]},
    )
    _write_json(opponent_dir / "opponent_registry.json", _minimal_registry("kaervek/current"))
    _write_json(
        tmp_path / "data/decks/opponents/kaervek/current/deck.json",
        {
            "verified_full_list": True,
            "deck_hash": "a" * 64,
            "cards": [{"oracle_name": "Kaervek", "quantity": 100}],
        },
    )
    completed, report = _run_audit(tmp_path)
    assert completed.returncode == 1
    assert "kaervek_frozen_semantics" in _failed_check_ids(report)
