from __future__ import annotations

import json
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_rules_coverage.py"


def _load_helpers() -> tuple[
    Callable[[Path], tuple[Path, ...]],
    Callable[[Path, dict[str, dict[str, Any]]], None],
]:
    namespace = runpy.run_path(str(SCRIPT))
    return namespace["_current_opponent_deck_paths"], namespace["_load_current_opponents"]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_nested_current_verified_opponent_is_loaded_and_historical_snapshot_is_excluded(
    tmp_path: Path,
) -> None:
    current_paths, load_current_opponents = _load_helpers()
    opponents_root = tmp_path / "data" / "decks" / "opponents"
    current = opponents_root / "kaervek" / "current" / "deck.json"
    historical = opponents_root / "kaervek" / "historical" / "deck.json"

    _write_json(
        current,
        {
            "deck_id": "kaervek/current",
            "verified_full_list": True,
            "cards": [
                {"oracle_name": "Kaervek the Merciless", "quantity": 1},
                {"oracle_name": "Mountain", "quantity": 99},
            ],
        },
    )
    _write_json(
        historical,
        {
            "deck_id": "kaervek/historical",
            "verified_full_list": True,
            "cards": [{"oracle_name": "Stale Historical Card", "quantity": 100}],
        },
    )

    assert current_paths(opponents_root) == (current,)

    records: dict[str, dict[str, Any]] = {}
    load_current_opponents(tmp_path, records)

    assert "Kaervek the Merciless" in records
    assert "Mountain" in records
    assert "Stale Historical Card" not in records
    assert records["Kaervek the Merciless"]["source_status"] == ["verified_full_deck"]
    assert records["Kaervek the Merciless"]["evidence_files"] == [
        "data/decks/opponents/kaervek/current/deck.json"
    ]


def test_candidate_registry_is_read_from_the_private_folder_when_it_is_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    namespace = runpy.run_path(str(SCRIPT))
    load_registry = namespace["_load_current_candidate_registry"]
    relative = "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json"
    repository = tmp_path / "repository"
    private = tmp_path / "private"
    _write_json(
        repository / relative,
        {"eligible_by_deck": {"deck": {"Repository Card": {"physical_available_quantity": 1}}}},
    )
    _write_json(
        private / relative,
        {"eligible_by_deck": {"deck": {"Private Card": {"physical_available_quantity": 2}}}},
    )

    monkeypatch.delenv("COMMANDER_LAB_OWNER_DATA", raising=False)
    from_repository: dict[str, dict[str, Any]] = {}
    load_registry(repository, from_repository)
    assert set(from_repository) == {"Repository Card"}

    monkeypatch.setenv("COMMANDER_LAB_OWNER_DATA", str(private))
    from_private: dict[str, dict[str, Any]] = {}
    load_registry(repository, from_private)
    assert set(from_private) == {"Private Card"}
    # The evidence entry names the repository path, never the private folder.
    assert from_private["Private Card"]["evidence_files"] == [relative]
