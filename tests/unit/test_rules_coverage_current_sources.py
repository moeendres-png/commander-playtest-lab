from __future__ import annotations

import json
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any

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
