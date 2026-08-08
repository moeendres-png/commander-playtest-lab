from __future__ import annotations

from pathlib import Path

from commander_lab.acceptance import run_phase10_acceptance
from commander_lab.acceptance.phase10 import _api_demo_passed
from commander_lab.engine.structural import load_project_structural_decks
from commander_lab.storage import verify_run


def test_current_opponent_profiles_are_loaded(project_root: Path = Path.cwd()) -> None:
    decks = load_project_structural_decks(
        project_root,
        include_synthetic_fixtures=True,
        include_current_opponents=True,
    )
    expected = {
        "opponent/morcant-elves",
        "opponent/cosmic-spiderman-midbudget",
        "opponent/blight-curse-precon",
        "kaervek/current",
        "opponent/doom-prevails-precon",
        "opponent/dance-elements-precon",
        "opponent/wakanda-forever-precon",
    }
    assert expected <= set(decks)
    assert all(len(decks[deck_id].cards) == 100 for deck_id in expected)


def test_phase10_smoke_never_claims_external_validation(tmp_path: Path) -> None:
    result = run_phase10_acceptance(
        Path.cwd(),
        iterations=1,
        workers=1,
        output_directory=tmp_path / "phase10",
    )
    assert result["status"] == "passed_with_limitations"
    assert result["external_engine_validation_pending"] is True
    assert result["validated_upgrades"] == []
    assert result["canonical_deck_files_modified"] is False
    assert result["google_drive_files_modified"] is False
    for recommendation in result["final_recommendations"].values():
        assert recommendation["status"] != "validated_upgrade"
        assert recommendation["automatic_application"] is False
    verification = verify_run(tmp_path / "phase10")
    assert verification.valid is True
    assert verification.status == "valid"


def test_api_demo_accepts_versioned_evidence_envelope() -> None:
    evidence = {
        "health": {"status_code": 200, "body": {"status": "ok", "tool_count": 32}},
        "tools": {"status_code": 200, "count": 32, "names": ["validate_deck"]},
        "validate_deck": {
            "status_code": 200,
            "body": {"status": "completed", "result": {"deck_id": "rogshai/current"}},
        },
    }
    assert _api_demo_passed(evidence) is True


def test_api_demo_accepts_in_process_self_test_shape() -> None:
    evidence = {
        "health": {"status": "ok", "tool_count": 32},
        "tool_count": 32,
        "validate_call": {"status": "completed", "result": {"deck_id": "korvold/current"}},
    }
    assert _api_demo_passed(evidence) is True


def test_api_self_test_runs_in_isolated_process() -> None:
    from commander_lab.acceptance.phase10 import _run_api_self_test_isolated

    result = _run_api_self_test_isolated(Path.cwd(), timeout_seconds=30.0)
    assert result["health"]["status"] == "ok"
    assert result["tool_count"] > 0
    assert result["validate_call"]["status"] == "completed"
