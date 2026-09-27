from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .models import DeckCandidateSet


def load_candidate_set(path: str | Path) -> DeckCandidateSet:
    source = Path(path)
    payload: Any = json.loads(source.read_text(encoding="utf-8"))
    return DeckCandidateSet.model_validate(payload)


def write_json(path: str | Path, payload: object) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    data: object = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    destination.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


__all__ = ["load_candidate_set", "write_json"]
