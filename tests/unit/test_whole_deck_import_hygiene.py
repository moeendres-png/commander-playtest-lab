from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_whole_deck_lab_context_import_is_order_independent() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import commander_lab.whole_deck.lab_context"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
