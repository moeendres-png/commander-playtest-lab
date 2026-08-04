from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def save_model(path: str | Path, model: BaseModel) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    path_obj.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_model(path: str | Path, model_type: type[ModelT]) -> ModelT:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return model_type.model_validate(payload)
