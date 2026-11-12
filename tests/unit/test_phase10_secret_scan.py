"""Regression tests for the Phase 10 repository secret scan.

The scan must keep catching real API keys (standalone tokens) while no longer
flagging hyphenated slugs in published research data — the card slug
"zask-skittering-swarmlord" contains "sk-" glued to a preceding word
character and is not a secret. That false positive failed both the CI
secret-pattern step and the Phase 10 acceptance criterion
``repository_secret_scan_passed`` on data-only PR #1246.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from commander_lab.acceptance.phase10 import _repository_secret_scan

# Built by concatenation so this test file itself never contains a literal
# standalone token for the scan to find.
FAKE_KEY = "s" + "k-" + "A1b2C3d4E5f6G7h8I9j0K1L2"
FAKE_PROJ_KEY = "s" + "k-proj-" + "Z9y8X7w6V5u4T3s2R1q0P9o8"

ZASK_CSV_LINE = (
    '"Uurg, Spawn of Turg",uurg-spawn-of-turg,4,optimized,Creatures,creatures,'
    '"Zask, Skittering Swarmlord",zask-skittering-swarmlord,'
    "4eafc507-973a-4aec-91b9-c29d70b0e25d,0.2282,28.0789,1,4,0.0,"
    "uurg-spawn-of-turg_optimized.json"
)


def _tracked_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git is required to build the tracked-file fixture")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    return tmp_path


def test_slug_in_research_csv_is_not_a_finding(tmp_path: Path) -> None:
    root = _tracked_repo(tmp_path, {"data/research/signals.csv": ZASK_CSV_LINE + "\n"})
    result = _repository_secret_scan(root)
    assert result["passed"] is True
    assert result["findings"] == []


def test_standalone_keys_are_findings(tmp_path: Path) -> None:
    root = _tracked_repo(
        tmp_path,
        {
            "config.py": f'API_TOKEN = "{FAKE_KEY}"\n',
            "notes.txt": f"prefix {FAKE_PROJ_KEY} suffix\n",
        },
    )
    result = _repository_secret_scan(root)
    assert result["passed"] is False
    flagged_files = {finding.split(":", 1)[0] for finding in result["findings"]}
    assert flagged_files == {"config.py", "notes.txt"}


def test_key_at_line_start_is_a_finding(tmp_path: Path) -> None:
    root = _tracked_repo(tmp_path, {"leak.txt": FAKE_KEY + "\n"})
    result = _repository_secret_scan(root)
    assert result["passed"] is False
    assert {finding.split(":", 1)[0] for finding in result["findings"]} == {"leak.txt"}
