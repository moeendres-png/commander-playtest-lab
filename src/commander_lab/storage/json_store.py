from __future__ import annotations

import json
from pathlib import Path
from pydantic import BaseModel

from .atomic import atomic_write_text


def save_model(path: str | Path, model: BaseModel) -> None:
    path_obj = Path(path)
    atomic_write_text(
        path_obj,
        json.dumps(model.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
    )


def load_model[ModelT: BaseModel](path: str | Path, model_type: type[ModelT]) -> ModelT:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return model_type.model_validate(payload)
