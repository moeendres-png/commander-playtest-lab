from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.engine.structural.project import _validate_structural_profile_ids

ROOT = Path(__file__).resolve().parents[2]


def test_structural_profile_duplicate_ids_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps({"profiles": [{"deck_id": "duplicate"}, {"deck_id": "duplicate"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate structural deck_id"):
        _validate_structural_profile_ids(path)
