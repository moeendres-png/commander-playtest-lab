from __future__ import annotations

import tomllib
from pathlib import Path

from commander_lab import __version__


def test_runtime_version_matches_declared_package_version(repo_root: Path) -> None:
    declared = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    assert __version__ == declared
