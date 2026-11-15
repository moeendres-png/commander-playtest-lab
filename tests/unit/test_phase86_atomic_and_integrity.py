from __future__ import annotations

import json
from pathlib import Path

from commander_lab.storage import atomic_write_json


def test_atomic_json_write_replaces_complete_document(tmp_path: Path) -> None:
    target = tmp_path / "record.json"
    atomic_write_json(target, {"value": 1})
    atomic_write_json(target, {"value": 2, "nested": [1, 2, 3]})
    assert json.loads(target.read_text(encoding="utf-8")) == {"value": 2, "nested": [1, 2, 3]}
    assert not list(tmp_path.glob(".record.json.*"))
