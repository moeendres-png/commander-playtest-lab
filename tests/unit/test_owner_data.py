"""The owner's own data is read from the repository by default and from a private folder when set."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from commander_lab.owner_data import (
    OWNER_DATA_ENV,
    OWNER_DATA_PATHS,
    is_owner_data,
    owner_data_path,
    owner_data_root,
)
from commander_lab.project_context import ProjectContextError, load_project_context

ROOT = Path(__file__).resolve().parents[2]
ALLOCATIONS = "data/collections/current_deck_allocations.json"
PUBLIC_NAMES = "data/collections/owner_collection_2026-10-12.txt"


def _copy_owner_data(destination: Path) -> None:
    for entry in OWNER_DATA_PATHS:
        source = ROOT / entry.rstrip("/")
        target = destination / entry.rstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def test_without_the_variable_every_path_stays_in_the_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(OWNER_DATA_ENV, raising=False)
    assert owner_data_root() is None
    assert owner_data_path(ROOT, ALLOCATIONS) == ROOT / ALLOCATIONS
    assert owner_data_path(ROOT, "data/decks/manifest.json") == ROOT / "data/decks/manifest.json"


def test_an_empty_variable_counts_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OWNER_DATA_ENV, "   ")
    assert owner_data_root() is None
    assert owner_data_path(ROOT, ALLOCATIONS) == ROOT / ALLOCATIONS


def test_with_the_variable_only_owner_paths_move(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(OWNER_DATA_ENV, str(tmp_path))
    assert owner_data_path(ROOT, ALLOCATIONS) == tmp_path / ALLOCATIONS
    below = "data/collections/current/rogshai_feature_projection/manifest.json"
    assert owner_data_path(ROOT, below) == tmp_path / below
    # Not owner data: code, decks, the public name list stay in the repository.
    for relative in ("data/decks/manifest.json", PUBLIC_NAMES, "config/protected_cards.json"):
        assert owner_data_path(ROOT, relative) == ROOT / relative


def test_a_missing_private_file_does_not_fall_back_to_the_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(OWNER_DATA_ENV, str(tmp_path))
    resolved = owner_data_path(ROOT, ALLOCATIONS)
    assert not resolved.exists()
    assert (ROOT / ALLOCATIONS).exists()


def test_which_paths_count_as_owner_data() -> None:
    assert is_owner_data("data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json")
    assert is_owner_data("data/collections/current")
    assert is_owner_data("data/canonical_import/2026-08-07/inventory.json")
    assert is_owner_data(ALLOCATIONS)
    assert not is_owner_data(PUBLIC_NAMES)
    assert not is_owner_data("data/collections/current_other.json")
    assert not is_owner_data("data/decks/rogshai_current.json")


def test_every_listed_owner_path_exists_in_the_repository() -> None:
    missing = [entry for entry in OWNER_DATA_PATHS if not (ROOT / entry.rstrip("/")).exists()]
    assert missing == []


def test_project_context_reads_the_private_folder_when_it_is_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(OWNER_DATA_ENV, raising=False)
    from_repository = load_project_context(ROOT)
    _copy_owner_data(tmp_path)
    monkeypatch.setenv(OWNER_DATA_ENV, str(tmp_path))
    from_private_folder = load_project_context(ROOT)
    assert from_private_folder == from_repository
    # Change one private file: only then does the context move, proving it is read from there.
    scope = tmp_path / "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json"
    scope.write_text(scope.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert load_project_context(ROOT) != from_repository


def test_project_context_fails_when_the_private_folder_is_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(OWNER_DATA_ENV, str(tmp_path))
    with pytest.raises(ProjectContextError, match="required project-context input is missing"):
        load_project_context(ROOT)
