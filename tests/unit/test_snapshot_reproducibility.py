from __future__ import annotations

import json
import shutil
from pathlib import Path

from commander_lab.tools import build_local_snapshots

_INPUTS = (
    "data/cards/oracle_subset.json",
    "data/collections/current_deck_allocations.json",
    "data/decks/rogshai_current.txt",
    "data/decks/rogshai_current_card_catalog_overrides.json",
    "data/decks/rogshai_current_structural_overrides.json",
)
_TRACKED = (
    "data/decks/rogshai_current.json",
    "data/decks/manifest.json",
)


def _prepare_snapshot_root(repo_root: Path, sandbox: Path) -> None:
    for relative in _INPUTS:
        source = repo_root / relative
        target = sandbox / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _snapshot_bytes(root: Path) -> dict[str, bytes]:
    return {relative: (root / relative).read_bytes() for relative in _TRACKED}


def test_local_snapshot_build_is_byte_reproducible(repo_root: Path, tmp_path: Path) -> None:
    sandbox = tmp_path / "snapshot-root"
    _prepare_snapshot_root(repo_root, sandbox)

    build_local_snapshots(sandbox)
    first = _snapshot_bytes(sandbox)
    build_local_snapshots(sandbox)
    second = _snapshot_bytes(sandbox)

    assert first == second


def test_local_snapshot_build_is_portable_across_root_paths(
    repo_root: Path, tmp_path: Path
) -> None:
    first_root = tmp_path / "first-root"
    second_root = tmp_path / "different" / "second-root"
    _prepare_snapshot_root(repo_root, first_root)
    _prepare_snapshot_root(repo_root, second_root)

    build_local_snapshots(first_root)
    build_local_snapshots(second_root)

    assert _snapshot_bytes(first_root) == _snapshot_bytes(second_root)

    rogshai = json.loads((first_root / "data/decks/rogshai_current.json").read_text())
    assert rogshai["source"]["source_path"] == "data/decks/rogshai_current.txt"
