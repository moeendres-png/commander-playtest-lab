from __future__ import annotations

import shutil
from pathlib import Path

from commander_lab.tools import build_local_snapshots


def test_local_snapshot_build_is_byte_reproducible(
    repo_root: Path, tmp_path: Path
) -> None:
    sandbox = tmp_path / "snapshot-root"
    for relative in (
        "data/cards/oracle_subset.json",
        "data/collections/current_deck_allocations.json",
        "data/decks/korvold_current.txt",
        "data/decks/rogshai_current.txt",
    ):
        source = repo_root / relative
        target = sandbox / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    tracked = [
        sandbox / "data/decks/korvold_current.json",
        sandbox / "data/decks/rogshai_current.json",
        sandbox / "data/decks/manifest.json",
    ]
    build_local_snapshots(sandbox)
    first = {path.name: path.read_bytes() for path in tracked}
    build_local_snapshots(sandbox)
    second = {path.name: path.read_bytes() for path in tracked}
    assert first == second
