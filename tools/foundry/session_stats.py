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
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def _ms_to_utc(ms: object) -> str | None:
    if not isinstance(ms, (int, float)):
        return None
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="seconds")


def summarize(export_path: str) -> dict:
    try:
        data = json.loads(Path(export_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read export JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("export JSON must be an object with info/messages")
    info = data.get("info", {})
    messages = data.get("messages", [])
    if not isinstance(info, dict) or not isinstance(messages, list):
        raise ValueError("export JSON lacks info/messages shapes")
    if not info or not messages:
        raise ValueError("export JSON has empty info/messages (not a session export)")

    out: dict = {}
    out["session_id"] = info.get("id")
    out["agent"] = info.get("agent")
    model = info.get("model", {})
    if isinstance(model, dict):
        out["model"] = (
            f"{model.get('providerID')}/{model.get('id')}"
            if model.get("providerID") and model.get("id")
            else model.get("id")
        )
        out["provider"] = model.get("providerID")
        out["variant"] = model.get("variant")
    out["cli_version"] = info.get("version")

    turns = 0
    tool_calls = 0
    by_tool: Counter = Counter()
    tool_errors = 0
    patches = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        for part in message.get("parts", []):
            if not isinstance(part, dict):
                continue
            kind = part.get("type")
            if kind == "step-start":
                turns += 1
            elif kind == "tool":
                tool_calls += 1
                by_tool[str(part.get("tool", "?"))] += 1
                state = part.get("state", {})
                # 'running' appears in live sessions: count errors honestly
                # without equating running with error.
                if isinstance(state, dict) and state.get("status") == "error":
                    tool_errors += 1
            elif kind == "patch":
                patches += 1

    out["model_turns"] = turns
    out["tool_calls"] = tool_calls
    out["tool_calls_by_tool"] = dict(sorted(by_tool.items()))
    out["tool_errors"] = tool_errors
    out["patch_count"] = patches

    tokens = info.get("tokens", {})
    if isinstance(tokens, dict):
        for key in ("input", "output", "reasoning"):
            if isinstance(tokens.get(key), (int, float)):
                out[f"tokens_{key}"] = tokens[key]
        cache = tokens.get("cache", {})
        if isinstance(cache, dict):
            for key in ("read", "write"):
                if isinstance(cache.get(key), (int, float)):
                    out[f"tokens_cache_{key}"] = cache[key]
    cost = info.get("cost")
    if isinstance(cost, (int, float)):
        out["cost_usd"] = cost
    timing = info.get("time", {})
    if isinstance(timing, dict):
        out["started_utc"] = _ms_to_utc(timing.get("created"))
        out["ended_utc"] = _ms_to_utc(timing.get("updated"))
        created = timing.get("created")
        updated = timing.get("updated")
        if isinstance(created, (int, float)) and isinstance(updated, (int, float)):
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
        print(f"SESSION_STATS_INVALID: {exc}")
        return 1
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
