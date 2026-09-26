from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from commander_lab.models import OpponentProfile


class OpponentProfileImporter:
    def import_file(self, path: str | Path) -> list[OpponentProfile]:
        path_obj = Path(path)
        text = path_obj.read_text(encoding="utf-8-sig")
        suffix = path_obj.suffix.casefold()
        if suffix in {".yaml", ".yml"}:
            payload: Any = yaml.safe_load(text)
        elif suffix == ".json":
            payload = json.loads(text)
        else:
            raise ValueError(f"unsupported opponent profile format: {path_obj.suffix}")
        if isinstance(payload, dict) and "profiles" in payload:
            payload = payload["profiles"]
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            raise ValueError("opponent profile file must contain an object or list")
        return [OpponentProfile.model_validate(item) for item in payload]
