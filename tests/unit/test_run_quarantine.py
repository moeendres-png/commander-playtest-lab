from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from commander_lab.storage import quarantine_run


@pytest.mark.parametrize("relative", [".", ".quarantine", "nested/quarantine"])
def test_quarantine_rejects_destination_inside_run_without_mutation(
    tmp_path: Path, relative: str
) -> None:
    source = tmp_path / "run"
    source.mkdir()
    (source / "evidence.json").write_bytes(b"preserved")
    with pytest.raises(ValueError):
        quarantine_run(source, source / relative)
    assert sorted(p.relative_to(source).as_posix() for p in source.rglob("*")) == ["evidence.json"]
    assert (source / "evidence.json").read_bytes() == b"preserved"


@pytest.mark.parametrize("is_file", [False, True])
def test_invalid_run_source_does_not_create_quarantine(tmp_path: Path, is_file: bool) -> None:
    source = tmp_path / "run"
    if is_file:
        source.write_bytes(b"not a run directory")
    destination = tmp_path / "new-quarantine"
    with pytest.raises((FileNotFoundError, NotADirectoryError)):
        quarantine_run(source, destination)
    assert not destination.exists()
    if is_file:
        assert source.read_bytes() == b"not a run directory"


def test_existing_entries_are_preserved_and_returned_path_is_exact(tmp_path: Path) -> None:
    source = tmp_path / "run"
    source.mkdir()
    (source / "evidence.json").write_bytes(b"new evidence")
    destination = tmp_path / "quarantine"
    (destination / "run").mkdir(parents=True)
    (destination / "run" / "old.json").write_bytes(b"old evidence")
    (destination / "run-2").write_bytes(b"existing file")
    result = quarantine_run(source, destination)
    assert result == destination / "run-3"
    assert (result / "evidence.json").read_bytes() == b"new evidence"
    assert not source.exists()
    assert (destination / "run" / "old.json").read_bytes() == b"old evidence"
    assert (destination / "run-2").read_bytes() == b"existing file"


@pytest.mark.parametrize("link_kind", ["symlink", "junction"])
def test_dangling_link_is_an_occupied_quarantine_name(tmp_path: Path, link_kind: str) -> None:
    source = tmp_path / "run"
    source.mkdir()
    (source / "evidence.json").write_bytes(b"preserved")
    destination = tmp_path / "quarantine"
    destination.mkdir()
    link = destination / "run"
    missing = tmp_path / "missing"
    if link_kind == "junction":
        if os.name != "nt":
            pytest.skip("Windows junction semantics")
        subprocess.run(
            ["cmd", "/d", "/c", "mklink", "/J", str(link), str(missing)],
            capture_output=True,
            check=True,
        )
        assert link.is_junction()
    else:
        try:
            link.symlink_to(missing, target_is_directory=True)
        except OSError as error:
            if os.name == "nt" and getattr(error, "winerror", None) == 1314:
                pytest.skip("Windows symlink privilege unavailable; Linux CI covers this case")
            raise
    before = os.readlink(link)
    assert not link.exists()
    result = quarantine_run(source, destination)
    assert os.path.lexists(link)
    assert os.readlink(link) == before
    assert result == destination / "run-2"
    assert (result / "evidence.json").read_bytes() == b"preserved"
