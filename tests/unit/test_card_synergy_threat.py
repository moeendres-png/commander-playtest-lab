"""Tests for card_synergy_report.py and threat_report.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def run_script(script: str, report_data: dict, *args: str) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(report_data, f)
        path = f.name
    try:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), path, *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        Path(path).unlink(missing_ok=True)


def test_synergy_finds_pair():
    report = {
        "games": [
            {
                "status": "ok",
                "winner_seat": 0,
                "per_card": [
                    {"seat": 0, "card_name": "Bolt"},
                    {"seat": 0, "card_name": "Guide"},
                ],
            },
            {
                "status": "ok",
                "winner_seat": 0,
                "per_card": [
                    {"seat": 0, "card_name": "Bolt"},
                    {"seat": 0, "card_name": "Guide"},
                ],
            },
        ]
    }
    result = run_script("card_synergy_report.py", report, "--min-games", "1")
    assert result.returncode == 0
    assert "Bolt" in result.stdout
    assert "Guide" in result.stdout


def test_synergy_ignores_low_count():
    report = {
        "games": [
            {
                "status": "ok",
                "winner_seat": 0,
                "per_card": [{"seat": 0, "card_name": "Bolt"}],
            },
        ]
    }
    result = run_script("card_synergy_report.py", report, "--min-games", "5")
    assert result.returncode == 0
    assert "No pairs" in result.stdout


def test_threat_finds_card():
    report = {
        "games": [
            {
                "status": "ok",
                "winner_seat": 1,  # Pilot (seat 0) lost
                "per_card": [
                    {"seat": 1, "card_name": "Wrath of God"},
                    {"seat": 0, "card_name": "Grizzly Bears"},
                ],
            },
            {
                "status": "ok",
                "winner_seat": 1,
                "per_card": [
                    {"seat": 1, "card_name": "Wrath of God"},
                ],
            },
            {
                "status": "ok",
                "winner_seat": 0,  # Pilot won
                "per_card": [
                    {"seat": 0, "card_name": "Grizzly Bears"},
                ],
            },
        ]
    }
    result = run_script("threat_report.py", report, "--min-games", "1")
    assert result.returncode == 0
    assert "Wrath of God" in result.stdout


def test_threat_empty_report():
    report = {"games": []}
    result = run_script("threat_report.py", report)
    assert result.returncode == 1
    assert "No valid games" in result.stderr
