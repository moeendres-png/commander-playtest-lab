"""Golden snapshot of the tool API surface.

Guards structural refactors of ``CommanderToolService``: tool schemas for every registry
surface, plus the method names and signatures of the service class, must not drift.
Regenerate deliberately with ``COMMANDER_LAB_UPDATE_GOLDEN=1 pytest <this file>``.
"""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from typing import Any, cast

from commander_lab.tools import CommanderToolService, ToolRegistry

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "tool_api_snapshot.json"


def _members() -> dict[str, dict[str, str]]:
    public: dict[str, str] = {}
    private: dict[str, str] = {}
    for name in sorted(dir(CommanderToolService)):
        if name.startswith("__") and name != "__init__":
            continue
        raw = inspect.getattr_static(CommanderToolService, name)
        if isinstance(raw, property):
            description = "property"
        elif isinstance(raw, staticmethod | classmethod):
            description = f"{type(raw).__name__} {inspect.signature(raw.__func__)}"
        elif callable(raw):
            description = str(inspect.signature(raw))
        else:
            continue
        (private if name.startswith("_") else public)[name] = description
    return {"public": public, "private": private}


def _snapshot() -> dict[str, Any]:
    schemas = {
        surface: ToolRegistry(cast(Any, None), surface=surface).list_schemas()
        for surface in ("public", "expert", "all")
    }
    return {"schemas": schemas, "service": _members()}


def test_tool_api_matches_golden_snapshot() -> None:
    current = json.loads(json.dumps(_snapshot(), sort_keys=True))
    if os.environ.get("COMMANDER_LAB_UPDATE_GOLDEN") == "1":
        GOLDEN.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert current["service"] == golden["service"]
    assert current["schemas"] == golden["schemas"]
