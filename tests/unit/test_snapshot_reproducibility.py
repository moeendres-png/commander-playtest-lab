from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from commander_lab.tools import build_local_snapshots

_INPUTS = (
    "data/cards/oracle_subset.json",
    "data/cards/structural_role_profiles.json",
    "data/collections/current_deck_allocations.json",
    "data/decks/rogshai_current.txt",
    "data/decks/rogshai_current_card_catalog_overrides.json",
    "data/decks/rogshai_current_structural_overrides.json",
    "data/decks/rogshai_photo_verified_structural_overrides.json",
    "data/decks/rogshai_current_physical_printings.json",
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
    assert "physical_commander_note" not in rogshai["commander"]
    assert "printing_source_path" not in rogshai["source"]
    manifest = json.loads((first_root / "data/decks/manifest.json").read_text())
    assert manifest["data_snapshot_hash"]
    assert manifest["global_active_own_decks"] == ["rogshai/current"]
    assert manifest["runtime_loaded_decks"] == ["rogshai/current"]


def test_local_snapshot_build_is_stable_across_python_hash_seeds(
    repo_root: Path, tmp_path: Path
) -> None:
    sandbox = tmp_path / "hash-seed-root"
    _prepare_snapshot_root(repo_root, sandbox)
    command = [
        sys.executable,
        "-c",
        "from pathlib import Path; from commander_lab.tools import build_local_snapshots; "
        "build_local_snapshots(Path(__import__('sys').argv[1]))",
        str(sandbox),
    ]

    snapshots: list[dict[str, bytes]] = []
    for seed in ("1", "8675309"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        subprocess.run(command, check=True, env=environment)
        snapshots.append(_snapshot_bytes(sandbox))

    assert snapshots[0] == snapshots[1]
