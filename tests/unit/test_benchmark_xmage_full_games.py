"""The benchmark launches the bridge by an absolute jar path.

With ``--private-card-repository`` every bridge JVM starts in its own scratch
directory; a relative ``--jar`` then no longer resolved and every game ended at
once with BRIDGE_EXITED.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _module():
    spec = importlib.util.spec_from_file_location(
        "benchmark_xmage_full_games", ROOT / "scripts/benchmark_xmage_full_games.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_relative_jar_is_launched_by_its_absolute_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    command = _module().bridge_command(Path("bridge.jar"), ["-Xmx2g"])
    assert command == ("java", "-Xmx2g", "-jar", str(tmp_path / "bridge.jar"), "full-game")
    assert os.path.isabs(command[3])
