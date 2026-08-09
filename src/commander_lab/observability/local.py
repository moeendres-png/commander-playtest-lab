from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from commander_lab.storage.atomic import atomic_write_json

SENSITIVE_KEYS = frozenset({"api_key", "authorization", "token", "secret", "password", "openai_api_key"})


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if key.lower() in SENSITIVE_KEYS else _redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class MetricsRegistry:
    def __init__(self) -> None:
        self._values: dict[str, int | float] = {}
        self._lock = threading.Lock()

    def increment(self, name: str, value: int | float = 1) -> None:
        with self._lock:
            self._values[name] = self._values.get(name, 0) + value

    def snapshot(self) -> dict[str, int | float]:
        with self._lock:
            return dict(self._values)

    def write(self, path: str | Path) -> Path:
        return atomic_write_json(path, self.snapshot())


class StructuredLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, *, level: str, event: str, **fields: Any) -> None:
        record = _redact({
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "event": event,
            **fields,
        })
        line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
            handle.flush()
