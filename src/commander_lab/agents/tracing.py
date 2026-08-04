from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


class LocalAgentTraceRecorder:
    """Append-only OpenAI workflow trace, kept apart from deterministic game logs."""

    def __init__(self, trace_directory: str | Path, workflow_id: str) -> None:
        directory = Path(trace_directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{workflow_id}.jsonl"
        self._lock = Lock()

    def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "payload": payload or {},
            "log_class": "openai_agent_trace",
        }
        with self._lock, self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
