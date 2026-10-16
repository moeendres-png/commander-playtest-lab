"""docs/archive/ holds only unreferenced historical docs; see scripts/classify_docs.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_classify_docs_check_passes() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/classify_docs.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_archive_readme_declares_provenance_only() -> None:
    text = (ROOT / "docs/archive/README.md").read_text(encoding="utf-8")
    assert "provenance only" in text
    assert "not current instruction" in text
