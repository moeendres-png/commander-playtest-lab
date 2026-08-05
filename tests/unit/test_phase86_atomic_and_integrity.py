from __future__ import annotations

import json
from pathlib import Path

from commander_lab.storage import atomic_write_json, create_run_manifest, verify_run


def test_atomic_json_write_replaces_complete_document(tmp_path: Path) -> None:
    target = tmp_path / "record.json"
    atomic_write_json(target, {"value": 1})
    atomic_write_json(target, {"value": 2, "nested": [1, 2, 3]})
    assert json.loads(target.read_text(encoding="utf-8")) == {"value": 2, "nested": [1, 2, 3]}
    assert not list(tmp_path.glob(".record.json.*"))


def test_run_manifest_detects_corruption_and_incomplete_runs(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "result.json").write_text('{"ok":true}', encoding="utf-8")
    create_run_manifest(run, run_id="r1", status="completed", metadata={"seed": 1})
    assert verify_run(run).valid
    (run / "result.json").write_text('{"ok":false}', encoding="utf-8")
    verification = verify_run(run)
    assert not verification.valid
    assert any("mismatch" in error for error in verification.errors)


def test_missing_manifest_is_incomplete(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    result = verify_run(run)
    assert result.status == "incomplete"
    assert not result.valid
