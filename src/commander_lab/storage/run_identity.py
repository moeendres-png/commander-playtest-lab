from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel

RUN_CANONICAL_JSON_VERSION = 1


def _normalized_text(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _canonicalize_run(value: Any, *, root: Path | None = None) -> Any:
    if isinstance(value, BaseModel):
        return _canonicalize_run(value.model_dump(mode="python", exclude_none=False), root=root)
    if is_dataclass(value):
        return _canonicalize_run(asdict(value), root=root)
    if isinstance(value, dict):
        return {
            _normalized_text(str(key)): _canonicalize_run(item, root=root)
            for key, item in sorted(value.items(), key=lambda pair: _normalized_text(str(pair[0])))
        }
    if isinstance(value, (set, frozenset)):
        rows = [_canonicalize_run(item, root=root) for item in value]
        return sorted(
            rows,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
        )
    if isinstance(value, (list, tuple)):
        return [_canonicalize_run(item, root=root) for item in value]
    if isinstance(value, Enum):
        return _canonicalize_run(value.value, root=root)
    if isinstance(value, Path):
        path = value
        if root is not None:
            try:
                relative = path.resolve().relative_to(root.resolve())
                return f"project://{relative.as_posix()}"
            except (OSError, ValueError):
                pass
        return _normalized_text(path.as_posix())
    if isinstance(value, str):
        return _normalized_text(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("run identity cannot hash NaN or infinite floats")
        normalized = 0.0 if value == 0.0 else value
        return {"$float_hex": normalized.hex()}
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def canonical_run_json_bytes(value: Any, *, root: str | Path | None = None) -> bytes:
    root_path = Path(root).resolve() if root is not None else None
    envelope = {
        "canonical_run_json_version": RUN_CANONICAL_JSON_VERSION,
        "payload": _canonicalize_run(value, root=root_path),
    }
    return json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_run_value(value: Any, *, root: str | Path | None = None) -> str:
    return hashlib.sha256(canonical_run_json_bytes(value, root=root)).hexdigest()


def normalize_run_paths(value: Any, *, root: str | Path) -> Any:
    """Normalize project-local path-like values before semantic run hashing.

    Only keys whose names clearly denote paths/files/directories are rewritten. Other strings are
    preserved verbatim so card names, IDs and free text cannot accidentally be path-normalized.
    """

    root_path = Path(root).resolve()
    path_tokens = ("path", "file", "directory", "output", "root")

    def visit(item: Any, key: str | None = None) -> Any:
        if isinstance(item, BaseModel):
            return visit(item.model_dump(mode="python", exclude_none=False), key)
        if isinstance(item, dict):
            return {str(k): visit(v, str(k)) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [visit(v, key) for v in item]
        if isinstance(item, str) and key is not None and any(token in key.casefold() for token in path_tokens):
            candidate = Path(item)
            if candidate.is_absolute():
                try:
                    return f"project://{candidate.resolve().relative_to(root_path).as_posix()}"
                except (OSError, ValueError):
                    return candidate.as_posix()
            normalized = Path(item).as_posix().removeprefix("./")
            return f"project://{normalized}"
        return item

    return visit(value)
