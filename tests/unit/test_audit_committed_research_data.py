"""Unit tests for the committed research data consistency audit."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.audit_committed_research_data import main, run_audit


def test_run_audit_against_repo() -> None:
    repo_root = Path(".")
    rows, markdown_text = run_audit(repo_root)

    assert len(rows) == 9
    results_by_check = {r.check_name: r for r in rows}

    # 1.1 Parseability
    assert results_by_check["1.1 Parsebarkeit der 5 Datendateien"].result == "OK"
    assert results_by_check["1.1 Parsebarkeit der 5 Datendateien"].count == 0

    # 2.1 Gap matrix vs PCK
    r21 = results_by_check["2.1 Gap-Matrix-Karten ohne Eintrag in pilot_card_knowledge"]
    assert r21.result == "ABWEICHUNG"
    assert r21.count == 123

    # 2.2 Inclusion CSV vs Gap Matrix
    r22 = results_by_check[
        "2.2 Inclusion-CSV-Karten ohne Gap-Matrix-Eintrag (Universum vs. Chulane-Pool)"
    ]
    assert r22.result == "ABWEICHUNG"
    assert r22.count == 6084

    # 2.3 Duplicates
    assert results_by_check["2.3 Dubletten je Datei"].result == "OK"
    assert results_by_check["2.3 Dubletten je Datei"].count == 0

    # 3.1 Constant cohort denominators
    assert results_by_check["3.1 Inclusion-CSV: Kohorten-Nenner konstant"].result == "OK"
    assert results_by_check["3.1 Inclusion-CSV: Kohorten-Nenner konstant"].count == 0

    # 3.2 Value ranges
    r32 = results_by_check[
        "3.2 Inclusion-CSV: Wertebereiche (0 <= decks <= universe_decks; 0.0 <= share <= 1.0)"
    ]
    assert r32.result == "OK"
    assert r32.count == 0

    # 3.3 Empty fields
    assert results_by_check["3.3 Inclusion-CSV: Leere Pflichtfelder"].result == "OK"
    assert results_by_check["3.3 Inclusion-CSV: Leere Pflichtfelder"].count == 0

    # 3.4 Summary counts
    assert results_by_check["3.4 Gap-Matrix: summary_counts Nachrechnung"].result == "OK"
    assert results_by_check["3.4 Gap-Matrix: summary_counts Nachrechnung"].count == 0

    # 4.1 Game Changer vs Banned
    r41 = results_by_check["4.1 commander_flags.json: Game Changer vs. Banned Überschneidung"]
    assert r41.result == "OK"
    assert r41.count == 0

    # Markdown checks
    assert "# Daten-Konsistenz-Audit der committed Research- und Kartendaten" in markdown_text
    assert "Spellbook Seeker // Careful Study" in markdown_text
    assert "Gesamt-Tabelle aller Prüfungen" in markdown_text


def test_main_cli_execution(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_file = tmp_path / "test_audit.md"
    ret = main(["--repo-root", ".", "--out", str(out_file)])
    assert ret == 0
    assert out_file.is_file()
    captured = capsys.readouterr().out
    assert "Wrote audit report to" in captured
