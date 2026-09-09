"""Minimal per-task/session metric records (JSONL).

Captures only values supplied explicitly or read from Git. Token usage,
tool-call counts, and elapsed time are recorded only when provided by the
caller (for example from OpenCode session stats) — never invented.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

FIELDS = [
    "task_id",
    "task_class",
    "reasoning_effort",
    "source_sha",
    "final_sha",
    "completed",
    "human_interventions",
    "build_attempts",
    "test_attempts",
    "tool_calls",
    "token_usage",
    "elapsed_seconds",
    "reverts",
    "scope_violations",
    "failure_class",
    "evidence_status",
]


def record(path: str, **kwargs: object) -> dict:
    entry = {"recorded_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    for field in FIELDS:
        if field in kwargs and kwargs[field] is not None:
            entry[field] = kwargs[field]
    unknown = sorted(set(kwargs) - set(FIELDS))
    if unknown:
        raise ValueError(f"unknown metric fields: {unknown}")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append one JSONL metric record.")
    parser.add_argument("--metrics", required=True, help="JSONL file to append to.")
    parser.add_argument("--set", action="append", default=[], help="KEY=JSON_VALUE pairs.")
    args = parser.parse_args(argv)
    kwargs: dict[str, object] = {}
    for item in args.set:
        key, _, raw = item.partition("=")
        if not key or not raw:
            raise SystemExit(f"bad --set item: {item!r} (want KEY=JSON_VALUE)")
        kwargs[key] = json.loads(raw)
    entry = record(args.metrics, **kwargs)
    print(json.dumps(entry, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
