"""Review findings on the import-all run: step guard, unknown commander, names, web report."""

from __future__ import annotations

import gzip
import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, import_all, research_import
from commander_lab.studio.__main__ import main
from commander_lab.studio.web import create_app
from tests.unit.test_studio_import_all import COMMANDER, _delivery, _run

HEADERS = {"host": "127.0.0.1"}


def test_truncated_gzip_stops_the_run_with_a_report(tmp_path: Path) -> None:
    files = _delivery(tmp_path)
    raw = gzip.compress(b'{"a": 1}\n' * 2000)
    broken = tmp_path / "cut.jsonl.gz"
    broken.write_bytes(raw[: len(raw) // 2])
    report = _run(StudioStore.in_memory(), files, scryfall=broken)
    assert isinstance(report["stopped_at"], str) and "EOFError" in report["stopped_at"]
    unused = report["unused_files"]
    assert isinstance(unused, list) and unused
    assert all(group["reason"] == import_all.NOT_READ for group in unused)


def test_non_xlsx_collection_stops_the_run_with_a_report(tmp_path: Path) -> None:
    files = _delivery(tmp_path)
    files["collection"].write_bytes(b"not a workbook")
    report = _run(StudioStore.in_memory(), files)
    assert isinstance(report["stopped_at"], str) and "inventory" in report["stopped_at"]


def test_any_error_of_an_optional_step_is_recorded_and_the_run_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> dict[str, object]:
        raise RuntimeError("kaputt")

    monkeypatch.setattr(research_import, "import_tagger_roles", boom)
    report = _run(StudioStore.in_memory(), _delivery(tmp_path))
    steps = report["steps"]
    assert isinstance(steps, list)
    failed = [s for s in steps if s["status"] == import_all.STEP_FAILED]
    assert failed and "RuntimeError: kaputt" in failed[0]["message"]
    assert report["stopped_at"] is None
    assert any(s["step"] == "rulings" and s["status"] == import_all.STEP_OK for s in steps)


def test_unknown_commander_stops_before_a_report_and_lists_commanders(tmp_path: Path) -> None:
    files = _delivery(tmp_path)
    with pytest.raises(import_all.ImportAllError, match="Nobody At All") as raised:
        _run(StudioStore.in_memory(), files, commander="Nobody At All")
    assert "Test Commander" in str(raised.value)
    code = main(
        [
            "--data", str(tmp_path / "d"), "import-all",
            "--collection", str(files["collection"]),
            "--scryfall", str(files["scryfall"]),
            "--research", str(files["research"]),
            "--commander", "Nobody At All",
        ]
    )  # fmt: skip
    assert code == 1
    assert not (tmp_path / "d" / "import_report.json").exists()


def test_report_json_holds_counts_not_card_names(tmp_path: Path) -> None:
    files = _delivery(tmp_path)
    report = _run(StudioStore.in_memory(), files)
    text = json.dumps(report, ensure_ascii=False)
    for name in ("Unknown Card", "Filler 01", "Forest"):
        assert name not in text
    steps = report["steps"]
    assert isinstance(steps, list)
    deck_step = next(s for s in steps if s["step"].startswith("decklists"))
    assert deck_step["result"]["corpus_unresolved_names_count"] == 1
    scry = next(s for s in steps if s["step"] == "public_card_facts")
    assert isinstance(scry["result"]["unlinked_count"], int)
    assert isinstance(scry["result"]["fact_differences_count"], int)


def test_web_report_states_when_it_was_written_and_warns_on_later_changes(tmp_path: Path) -> None:
    files = _delivery(tmp_path)
    data = tmp_path / "data"
    store = StudioStore.open(data)
    from commander_lab.studio import completeness

    completeness.write_report(data, _run(store, files))
    store.close()
    client = TestClient(create_app(data), headers=HEADERS)
    fresh = client.get("/api/import-report").json()
    assert fresh["written_at"] and fresh["store_modified_after_report"] is False
    later = time.time() + 60
    os.utime(data / "studio.sqlite3", (later, later))
    stale = client.get("/api/import-report").json()
    assert stale["store_modified_after_report"] is True and stale["warning"]
    assert COMMANDER in json.dumps(stale)
