"""Tests fuer das lesende Geruest der Lab UI (Decks + Reports).

Die Tests laufen ohne HTTP-Client: Sie pruefen die reinen Funktionen,
die die API-Endpunkte aufrufen. Kein JVM, keine echten Spiele.
"""

from __future__ import annotations

from pathlib import Path

from commander_lab.api.lab_ui import decks as decks_mod
from commander_lab.api.lab_ui import reports as reports_mod


def test_list_decks_finds_precons_and_no_collection_paths(tmp_path: Path) -> None:
    root = tmp_path
    (root / "data" / "decks" / "precons").mkdir(parents=True)
    (root / "data" / "decks" / "precons" / "2020_test.json").write_text("{}")
    (root / "data" / "decks" / "rogshai_current.json").write_text("{}")
    (root / "data" / "opponents").mkdir(parents=True)
    (root / "data" / "opponents" / "opp.json").write_text("{}")
    found = decks_mod.list_decks(root)
    assert found["precons"] == ["data/decks/precons/2020_test.json"]
    assert found["targets"] == ["data/decks/rogshai_current.json"]
    assert found["opponents"] == ["data/opponents/opp.json"]
    assert not any("collection" in p for group in found.values() for p in group)


def test_find_and_summarize_report(tmp_path: Path) -> None:
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    (run_dir / "COMPARISON_REPORT.json").write_text(
        '{"comparison_id": "c1", "batch": {"completed_cases": 199,'
        ' "failed_cases": 1, "total_cases": 200}, "contenders":'
        ' [{"deck_id": "a", "wins": 10, "games_completed": 100,'
        ' "games_failed": 0, "win_share": 0.1,'
        ' "win_share_interval_95": {"low": 0.05, "high": 0.2},'
        ' "mean_turns": 9.5}], "paired": [{"baseline_deck_id": "a",'
        ' "variant_deck_id": "b", "verdict": "BASELINE_BETTER",'
        ' "win_share_difference": -0.12,'
        ' "win_share_difference_interval_95": {"low": -0.2, "high": -0.04},'
        ' "sign_test_p_value": 0.007, "pairs_completed": 99,'
        ' "pairs_censored": 1}], "seeds": [1], "tested_seats": [1, 2, 3, 4],'
        ' "sequential": {"stopped_early": false},'
        ' "evidence_class": "DIRECTLY_VERIFIED"}'
    )
    found = reports_mod.find_reports(tmp_path)
    assert len(found) == 1
    assert found[0]["id"] == "run1"
    assert found[0]["completed"] == 199
    summary = reports_mod.summarize_report(run_dir / "COMPARISON_REPORT.json")
    assert summary["paired"][0]["verdict"] == "BASELINE_BETTER"
    assert summary["contenders"][0]["win_share"] == 0.1
    assert reports_mod.find_reports(tmp_path / "fehlt") == []
    html = reports_mod.render_report_html(summary)
    assert "BASELINE_BETTER" in html
    assert "win_share" not in html or "0.1" in html
    assert "<table" in html
