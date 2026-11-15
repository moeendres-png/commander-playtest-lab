from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def cyclic_run(tmp_path: Path) -> Path:
    first, second = tmp_path / "private-loop-a", tmp_path / "private-loop-b"
    for link, target in ((first, second), (second, first)):
        if os.name == "nt":
            subprocess.run(
                ["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                check=True,
            )
        else:
            link.symlink_to(target, target_is_directory=True)
    return first
