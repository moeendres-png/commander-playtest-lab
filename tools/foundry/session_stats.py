"""Aggregate counts from an `opencode export <session>` JSON file.

Emits ONLY aggregates (turns, tool counts, token totals, cost, errors) —
never session content (commands, outputs, patches, text). Raw export files
are LOCAL_ONLY: never commit them, never paste them into evidence. Counts are
safe to record via tools/foundry/metrics.py with AUTOCAPTURED provenance.

Verified against CLI 1.18.30 export shape: top-level {info, messages};
info carries id/agent/model{providerID,id,variant}/version/cost/tokens/time;
messages carry parts typed tool/step-start/step-finish/reasoning/patch/text.
Absent keys stay absent — nothing is estimated. Compaction count has no marker
in this format and is reported as unavailable, never inferred.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def _object(parent: dict, key: str) -> dict:
    value = parent.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"invalid {key} object")
    return value


def _label(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError(f"invalid {field} identifier")
    return value


def _number(value: object, field: str, *, count: bool = False) -> int | float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or value < 0:
        raise ValueError(f"invalid {field} measurement")
    if isinstance(value, float) and (
        not math.isfinite(value) or (count and not value.is_integer())
    ):
        raise ValueError(f"invalid {field} measurement")
    return value


def _ms_to_utc(ms: int | float | None) -> str | None:
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("timestamp outside supported range") from exc


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("non-finite JSON constant")


def summarize(export_path: str) -> dict:
    try:
        data = json.loads(
            Path(export_path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except (OSError, ValueError, RecursionError) as exc:
        # Decoder/OS exceptions can contain raw export bytes or private paths.
        raise ValueError("cannot read valid export JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("export JSON must be an object with info/messages")
    info = data.get("info", {})
    messages = data.get("messages", [])
    if not isinstance(info, dict) or not isinstance(messages, list):
        raise ValueError("export JSON lacks info/messages shapes")
    if not info or not messages:
        raise ValueError("export JSON has empty info/messages (not a session export)")

    out: dict = {}
    out["session_id"] = _label(info.get("id"), "session")
    if out["session_id"] is None:
        raise ValueError("missing session identifier")
    out["agent"] = _label(info.get("agent"), "agent")
    model = _object(info, "model")
    provider = _label(model.get("providerID"), "provider")
    model_id = _label(model.get("id"), "model")
    out["model"] = f"{provider}/{model_id}" if provider and model_id else model_id
    out["provider"] = provider
    out["variant"] = _label(model.get("variant"), "variant")
    out["cli_version"] = _label(info.get("version"), "version")

    turns = 0
    tool_calls = 0
    by_tool: Counter = Counter()
    tool_errors = 0
    patches = 0
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("invalid message object")
        parts = message.get("parts")
        if not isinstance(parts, list):
            raise ValueError("missing or invalid message parts")
        for part in parts:
            if not isinstance(part, dict):
                raise ValueError("invalid part object")
            kind = _label(part.get("type"), "part type")
            if kind is None:
                raise ValueError("missing part type")
            if kind == "step-start":
                turns += 1
            elif kind == "tool":
                tool_calls += 1
                tool = _label(part.get("tool"), "tool")
                if tool is None:
                    raise ValueError("missing tool identifier")
                by_tool[tool] += 1
                state = _object(part, "state")
                # 'running' appears in live sessions: count errors honestly
                # without equating running with error.
                status = state.get("status")
                if not isinstance(status, str) or status not in {
                    "pending",
                    "running",
                    "completed",
                    "error",
                }:
                    raise ValueError("missing or unsupported tool status")
                if status == "error":
                    tool_errors += 1
            elif kind == "patch":
                patches += 1

    out["model_turns"] = turns
    out["tool_calls"] = tool_calls
    out["tool_calls_by_tool"] = dict(sorted(by_tool.items()))
    out["tool_errors"] = tool_errors
    out["patch_count"] = patches

    tokens = _object(info, "tokens")
    for key in ("input", "output", "reasoning"):
        out[f"tokens_{key}"] = _number(tokens.get(key), "token", count=True)
    cache = _object(tokens, "cache")
    for key in ("read", "write"):
        out[f"tokens_cache_{key}"] = _number(cache.get(key), "cache token", count=True)
    out["cost_usd"] = _number(info.get("cost"), "cost")
    timing = _object(info, "time")
    created = _number(timing.get("created"), "timestamp")
    updated = _number(timing.get("updated"), "timestamp")
    out["started_utc"] = _ms_to_utc(created)
    out["ended_utc"] = _ms_to_utc(updated)
    if created is not None and updated is not None:
        if updated < created:
            raise ValueError("session timestamps are reversed")
        out["elapsed_seconds"] = round((updated - created) / 1000, 1)
    out["compaction_count"] = None  # no marker in export format: unavailable
    return {k: v for k, v in out.items() if v is not None or k == "compaction_count"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate opencode session export counts.")
    parser.add_argument("--export", required=True, help="Path to export JSON file.")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    try:
        summary = summarize(args.export)
    except ValueError as exc:
        print(f"SESSION_STATS_INVALID: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(summary, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        temporary: str | None = None
        try:
            target = Path(args.output)
            if target.exists() and target.samefile(args.export):
                print("SESSION_STATS_INVALID: output aliases the raw export", file=sys.stderr)
                return 1
            # Publish a complete summary or retain the previous file. Raw exports
            # must never be destroyed by choosing the input as output.
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=target.parent,
                prefix=".session-stats-",
                delete=False,
            ) as stream:
                temporary = stream.name
                stream.write(text + "\n")
            os.replace(temporary, target)
        except OSError:
            print("SESSION_STATS_INVALID: cannot publish summary output", file=sys.stderr)
            return 1
        finally:
            if temporary is not None:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    # Do not mask the publication result or disclose local paths.
                    print("SESSION_STATS_WARNING: temporary-file cleanup failed", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
