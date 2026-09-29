from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from commander_lab.storage import run_integrity
from commander_lab.storage.run_integrity import create_run_manifest, verify_run


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


@pytest.mark.parametrize("suffix", ["", "nested/run"])
def test_cyclic_run_path_returns_structured_failure(cyclic_run: Path, suffix: str) -> None:
    result = verify_run(cyclic_run / suffix)
    assert not result.valid
    assert result.status == "corrupt"
    assert result.checked_files == 0
    assert result.errors
    assert "private-loop" not in str(result.errors)


def test_ordinary_missing_run_remains_incomplete(tmp_path: Path) -> None:
    result = verify_run(tmp_path / "missing")
    assert not result.valid
    assert result.status == "incomplete"


def test_unrelated_runtime_error_is_not_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_run_manifest(tmp_path, run_id="control", status="completed", metadata={})

    def broken_inventory(root: Path) -> dict[str, Path]:
        raise RuntimeError("internal inventory failure")

    monkeypatch.setattr(run_integrity, "_artifact_paths", broken_inventory)
    with pytest.raises(RuntimeError, match="internal inventory failure"):
        verify_run(tmp_path)
