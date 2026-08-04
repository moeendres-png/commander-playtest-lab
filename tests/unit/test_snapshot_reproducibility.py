from __future__ import annotations

from pathlib import Path

from commander_lab.tools import build_local_snapshots


def test_local_snapshot_build_is_byte_reproducible(repo_root: Path) -> None:
    tracked = [
        repo_root / "data/decks/korvold_current.json",
        repo_root / "data/decks/rogshai_current.json",
        repo_root / "data/decks/manifest.json",
    ]
    build_local_snapshots(repo_root)
    first = {path.name: path.read_bytes() for path in tracked}
    build_local_snapshots(repo_root)
    second = {path.name: path.read_bytes() for path in tracked}
    assert first == second
