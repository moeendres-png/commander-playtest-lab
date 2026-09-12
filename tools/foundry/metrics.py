"""Per-task/session metric records (JSONL) with provenance classification.

Captures only values supplied explicitly or read from Git/CLI artifacts.
Every field SHOULD carry provenance in the parallel ``provenance`` mapping:

- AUTOCAPTURED: read deterministically by project tooling (launcher,
  safe_push, session_stats) from an authoritative source;
- CALLER_SUPPLIED: provided by a human/operator (e.g. intervention counts);
- UNAVAILABLE_FROM_PINNED_CLI: the pinned CLI exposes no such signal
  (recorded by omission or explicit null, never estimated);
- UNKNOWN: provenance not established.

Token usage, tool-call counts, and timings are recorded only when provided
from an authoritative source (opencode export/stats) — never invented.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

FIELDS = [
    "task_id",
    "task_class",
    "repo_profile",
    "model",
    "reasoning_effort",
    "source_sha",
    "final_sha",
    "started_utc",
    "ended_utc",
    "elapsed_seconds",
    "exit_status",
    "completed",
    "human_interventions",
    "model_turns",
    "tool_calls",
    "tool_calls_by_tool",
    "tool_errors",
    "token_usage",
    "tokens_input",
    "tokens_output",
    "tokens_reasoning",
    "tokens_cache_read",
    "tokens_cache_write",
    "cost_usd",
    "patch_count",
    "build_attempts",
    "test_attempts",
    "checkpoint_commit_count",
    "safe_push_count",
    "failed_safe_push_count",
    "push_result",
    "reject_reason",
    "state_validation_failures",
    "writer_lock_conflicts",
    "reverts",
    "scope_violations",
    "failure_class",
    "evidence_status",
    "provenance",
]

PROVENANCE_VALUES = {
    "AUTOCAPTURED",
    "CALLER_SUPPLIED",
    "UNAVAILABLE_FROM_PINNED_CLI",
    "UNKNOWN",
}


def record(path: str, _provenance: dict | None = None, **kwargs: object) -> dict:
    entry = {"recorded_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    for field in FIELDS:
        if field in kwargs and kwargs[field] is not None:
            entry[field] = kwargs[field]
    unknown = sorted(set(kwargs) - set(FIELDS))
    if unknown:
        raise ValueError(f"unknown metric fields: {unknown}")
    provenance = dict(_provenance or {})
    bad = {k: v for k, v in provenance.items() if v not in PROVENANCE_VALUES}
    if bad:
        raise ValueError(f"bad provenance values: {bad}")
    for field in provenance:
        if field not in FIELDS:
            raise ValueError(f"provenance for unknown field: {field!r}")
    if provenance:
        entry["provenance"] = provenance
    # WS75: the caller-owned parent (e.g. the launcher run_dir outside the
    # Git worktree) is created automatically; a missing parent is a
    # diagnostic warning at the call site, never a dirty-tree workaround.
    parent = Path(path).parent
    if str(parent) and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append one JSONL metric record.")
    parser.add_argument("--metrics", required=True, help="JSONL file to append to.")
    parser.add_argument("--set", action="append", default=[], help="KEY=JSON_VALUE pairs.")
    parser.add_argument(
        "--provenance",
        action="append",
        default=[],
        help="FIELD=CLASS pairs (CLASS in AUTOCAPTURED|CALLER_SUPPLIED|UNAVAILABLE_FROM_PINNED_CLI|UNKNOWN).",
    )
    args = parser.parse_args(argv)
    kwargs: dict[str, object] = {}
    for item in args.set:
        key, _, raw = item.partition("=")
        if not key or not raw:
            raise SystemExit(f"bad --set item: {item!r} (want KEY=JSON_VALUE)")
        kwargs[key] = json.loads(raw)
    provenance: dict[str, str] = {}
    for item in args.provenance:
        field, _, klass = item.partition("=")
        if not field or klass not in PROVENANCE_VALUES:
            raise SystemExit(f"bad --provenance item: {item!r}")
        provenance[field] = klass
    entry = record(args.metrics, _provenance=provenance, **kwargs)
    print(json.dumps(entry, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
