"""The repository carries stand-ins for the owner's data: one copy per card, no pointers."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DRIVE_ID = re.compile(r"^1[A-Za-z0-9_-]{27,40}$")


def _tool() -> Any:
    spec = importlib.util.spec_from_file_location(
        "project_owner_data", ROOT / "scripts/project_owner_data.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_projection_rules_on_a_small_payload() -> None:
    tool = _tool()
    payload = {
        "source_drive_file_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz012345",
        "source_sha256": "a" * 64,
        "source_drive_ids": [
            "1AbCdEfGhIjKlMnOpQrStUvWxYz012345",
            "1ZyXwVuTsRqPoNmLkJiHgFeDcBa987654",
        ],
        "sources": {
            "state.json": {"drive_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz012345", "sha256": "b" * 64}
        },
        "cards": [
            {
                "oracle_name": "Sol Ring",
                "quantity": 3,
                "printed_name": "Sonnenring",
                "edition": "C21 #1",
            },
            {"oracle_name": "Forest", "quantity": 57, "physical_available_quantity": 6},
            {"oracle_name": "Not Owned", "quantity": 0},
        ],
        "released_allocations": {"Sol Ring": 2, "Arcane Signet": 1},
        "deck_hashes": {"rogshai/current": "c" * 64},
        "flag": True,
    }
    result = tool.project(payload)
    assert result["source_drive_file_id"] == "redacted"
    assert result["source_sha256"] == "0" * 64
    assert result["source_drive_ids"] == ["redacted", "redacted"]
    assert result["sources"]["state.json"] == {"drive_id": "redacted", "sha256": "0" * 64}
    assert result["cards"] == [
        {"oracle_name": "Sol Ring", "quantity": 1},
        {"oracle_name": "Forest", "quantity": 99, "physical_available_quantity": 1},
        {"oracle_name": "Not Owned", "quantity": 0},
    ]
    assert result["released_allocations"] == {"Sol Ring": 1, "Arcane Signet": 1}
    # Deck identities and flags are the project's own facts and stay.
    assert result["deck_hashes"] == {"rogshai/current": "c" * 64}
    assert result["flag"] is True
    assert tool.project(result) == result


def test_the_repository_files_are_already_the_stand_in() -> None:
    """A real inventory or a Drive pointer committed by mistake makes this fail."""
    assert _tool().check_tree(ROOT) == []


def test_no_owner_file_points_at_a_drive_file_or_carries_a_quantity_above_one() -> None:
    tool = _tool()
    pointers: list[str] = []
    counts: list[str] = []

    def walk(value: Any, where: str, key: str | None = None) -> None:
        if isinstance(value, dict):
            for name, item in value.items():
                walk(item, where, name)
        elif isinstance(value, list):
            for item in value:
                walk(item, where, key)
        elif isinstance(value, str) and DRIVE_ID.match(value):
            pointers.append(where)
        elif (
            key in tool.QUANTITY_KEYS
            and isinstance(value, int)
            and value not in (0, 1, tool.BASIC_LAND_STAND_IN)
        ):
            counts.append(where)

    files = tool.owner_files(ROOT)
    assert len(files) >= 25
    for path in files:
        walk(json.loads(path.read_text(encoding="utf-8")), str(path.relative_to(ROOT)))
    assert pointers == []
    assert counts == []
