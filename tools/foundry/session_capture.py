"""Exact-session OpenCode telemetry capture (WS199).

One bounded canonical capture operation: given an EXACT OpenCode session ID,
export that session with the pinned CLI, aggregate immediately via
``session_stats.summarize`` (never duplicating its parser), and append ONLY
allowlisted aggregate fields to ``metrics.jsonl`` with AUTOCAPTURED
provenance.

Attribution rule (parallel-safe): the caller must supply the exact OpenCode
session ID. This module never lists sessions, never picks "newest", and never
infers identity from chronology. A missing/ambiguous identity is
TELEMETRY_PENDING, never another session's data.

Privacy (LOCAL_ONLY): raw ``opencode export`` JSON contains session content
(prompts, commands, outputs, patches, reasoning). Raw files live ONLY under
the caller-owned run directory (outside any Git worktree), are never
committed, and their content is never printed to stdout/stderr and never
copied into metrics/evidence. Only aggregate counts leave this module.

Telemetry is observational: capture failure never blocks engineering. CLI
exit 0 means CAPTURED; exit 2 means PENDING/FAILED (diagnostic only); exit 1
means usage error. The launcher preserves the engineering child exit code
regardless of this result.

Pinned CLI 1.18.30 (DIRECTLY_VERIFIED via ``opencode export --help``):
``opencode export [sessionID]`` with optional ``--sanitize``. Sanitize is
used when the binary advertises it (reduces exposure) but is never a
correctness dependency; sanitized exports remain LOCAL_ONLY.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:  # package import (tests) vs script CWD (tools/foundry)
    from foundry import metrics as metrics_mod
    from foundry import session_stats as session_stats_mod
except ImportError:  # pragma: no cover - script-relative fallback
    import metrics as metrics_mod  # type: ignore[no-redef]
    import session_stats as session_stats_mod  # type: ignore[no-redef]

OPENCODE_BIN_ENV = "FOUNDRY_OPENCODE_BIN"
SESSION_ID_ENV = "FOUNDRY_OPENCODE_SESSION_ID"
SESSION_ID_FILE = "opencode-session-id"
STATUS_FILE = "telemetry-status.json"

# Exact session IDs are opaque CLI-issued tokens (observed: ``ses_<hex>``).
# Accept a conservative token shape; reject paths, whitespace, traversal.
_SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,127}$")

# Export aggregate key -> metrics.jsonl field. Exact allowlist: nothing else
# may be persisted. ``compaction_count`` is deliberately absent (no marker in
# the pinned export format; UNAVAILABLE_FROM_PINNED_CLI, never inferred).
EXPORT_TO_METRICS = {
    "session_id": "session_id",
    "agent": "agent",
    "model": "model",
    "provider": "provider",
    "variant": "variant",
    "cli_version": "cli_version",
    "model_turns": "model_turns",
    "tool_calls": "tool_calls",
    "tool_calls_by_tool": "tool_calls_by_tool",
    "tool_errors": "tool_errors",
    "tokens_input": "tokens_input",
    "tokens_output": "tokens_output",
    "tokens_reasoning": "tokens_reasoning",
    "tokens_cache_read": "tokens_cache_read",
    "tokens_cache_write": "tokens_cache_write",
    "cost_usd": "cost_usd",
    "patch_count": "patch_count",
    "started_utc": "started_utc",
    "ended_utc": "ended_utc",
    "elapsed_seconds": "elapsed_seconds",
}


def validate_session_id(session_id: str) -> str:
    """Return the stripped ID or raise ValueError (never guess, never fix)."""
    candidate = (session_id or "").strip()
    if not candidate:
        raise ValueError("exact OpenCode session ID is required (no auto-select)")
    if not _SESSION_RE.match(candidate):
        raise ValueError(f"refusing malformed session ID {candidate!r}")
    return candidate


def resolve_binary(explicit: str | None) -> str:
    """Explicit flag wins, then FOUNDRY_OPENCODE_BIN, then PATH ``opencode``."""
    if explicit:
        return explicit
    return os.environ.get(OPENCODE_BIN_ENV, "opencode")


def read_exact_session_id(
    run_dir: str, explicit: str | None = None
) -> str | None:
    """Return the exact OpenCode session ID when unambiguously available.

    Precedence: explicit argument > ``FOUNDRY_OPENCODE_SESSION_ID`` env >
    ``<run_dir>/opencode-session-id`` file. Empty/whitespace-only values are
    treated as absent. Malformed values are treated as absent here (the
    capture entry point re-validates strictly and reports the reason);
    this function never raises for identity problems and never lists
    sessions.
    """
    if explicit and explicit.strip() and _SESSION_RE.match(explicit.strip()):
        return explicit.strip()
    env_value = os.environ.get(SESSION_ID_ENV, "")
    if env_value.strip() and _SESSION_RE.match(env_value.strip()):
        return env_value.strip()
    try:
        text = Path(run_dir, SESSION_ID_FILE).read_text(encoding="utf-8")
    except OSError:
        return None
    candidate = text.strip().splitlines()[0].strip() if text.strip() else ""
    if candidate and _SESSION_RE.match(candidate):
        return candidate
    return None


def supports_sanitize(binary: str, timeout: int = 15) -> bool:
    """True when ``<bin> export --help`` advertises ``--sanitize``.

    Fail-open False on any error: sanitize reduces exposure but is never a
    correctness dependency, and sanitized exports remain LOCAL_ONLY.
    """
    try:
        proc = subprocess.run(
            [binary, "export", "--help"],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    blob = f"{proc.stdout}\n{proc.stderr}"
    return "--sanitize" in blob


def _is_inside_git_worktree(path: str) -> bool:
    """True when ``path`` resolves inside a Git worktree (read-only check)."""
    try:
        parent = str(Path(path).expanduser().resolve().parent)
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=parent,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _raw_inside_worktree(raw_path: str, worktree: str | None) -> bool:
    try:
        raw = Path(raw_path).expanduser().resolve()
    except OSError:
        return True  # fail closed: unresolvable raw location is refused
    if worktree:
        try:
            root = Path(worktree).expanduser().resolve()
            if raw == root or root in raw.parents:
                return True
        except OSError:
            return True
    return _is_inside_git_worktree(str(raw))


def read_launch_context(run_dir: str) -> dict:
    """Read ``<run_dir>/launch-context.json`` when present ({} otherwise)."""
    try:
        data = json.loads(Path(run_dir, "launch-context.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def format_hint(run_dir: str, session_note: str = "<sessionID>") -> str:
    """Exact operator follow-up command (no manual JSON/YAML editing)."""
    return (
        f"python3 tools/foundry/session_capture.py --run-dir {run_dir} "
        f"--session-id {session_note}"
    )


def _write_status(run_dir: str, payload: dict) -> str:
    path = Path(run_dir, STATUS_FILE)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass
    return str(path)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def capture(
    *,
    run_dir: str,
    session_id: str,
    metrics_path: str | None = None,
    opencode_bin: str | None = None,
    task_id: str | None = None,
    worktree: str | None = None,
    timeout: int = 60,
    delete_raw: bool = False,
    raw_path: str | None = None,
) -> dict:
    """Capture one exact session into metrics.jsonl (fail-open telemetry).

    Returns a status dict with at least ``status`` (CAPTURED/PENDING/FAILED)
    and ``reason``. Appends to metrics only on exact attribution success.
    Never raises for telemetry problems; raises ValueError only for
    malformed caller identity (exact-ID rule) before any subprocess runs.
    Never prints raw session content (callers format the returned status).
    """
    requested = validate_session_id(session_id)
    run_path = Path(run_dir)
    try:
        run_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"status": "FAILED", "reason": f"run_dir not writable: {exc}", "session_id": requested}
    metrics_file = metrics_path or str(run_path / "metrics.jsonl")
    binary = resolve_binary(opencode_bin)
    raw_file = raw_path or str(run_path / f"raw-export-{requested}.json")
    if _raw_inside_worktree(raw_file, worktree):
        payload = {
            "status": "FAILED",
            "reason": "RAW_INSIDE_WORKTREE",
            "session_id": requested,
            "metrics_path": metrics_file,
            "recorded_utc": _utc_now(),
        }
        _write_status(str(run_path), payload)
        return payload

    context = read_launch_context(str(run_path))
    context_workstream = context.get("workstream") if isinstance(context, dict) else None
    explicit_task = (task_id or "").strip() or None
    if explicit_task and context_workstream and explicit_task != context_workstream:
        payload = {
            "status": "FAILED",
            "reason": "OWNERSHIP_MISMATCH",
            "session_id": requested,
            "metrics_path": metrics_file,
            "recorded_utc": _utc_now(),
        }
        _write_status(str(run_path), payload)
        return payload
    effective_task = explicit_task or (
        context_workstream if isinstance(context_workstream, str) and context_workstream else None
    )
    task_provenance = "CALLER_SUPPLIED" if explicit_task else "AUTOCAPTURED"

    sanitized = supports_sanitize(binary)
    argv = [binary, "export"]
    if sanitized:
        argv.append("--sanitize")
    argv.append(requested)
    try:
        proc = subprocess.run(argv, capture_output=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        payload = {
            "status": "PENDING",
            "reason": "EXPORT_TIMEOUT",
            "session_id": requested,
            "metrics_path": metrics_file,
            "sanitized": sanitized,
            "recorded_utc": _utc_now(),
        }
        _write_status(str(run_path), payload)
        return payload
    except OSError as exc:
        payload = {
            "status": "PENDING",
            "reason": f"EXPORT_SPAWN_FAILED: {exc}",
            "session_id": requested,
            "metrics_path": metrics_file,
            "sanitized": sanitized,
            "recorded_utc": _utc_now(),
        }
        _write_status(str(run_path), payload)
        return payload
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")[:500].lower()
        reason = "SESSION_NOT_FOUND" if ("not found" in err or "no session" in err) else "EXPORT_FAILED"
        payload = {
            "status": "PENDING",
            "reason": reason,
            "session_id": requested,
            "metrics_path": metrics_file,
            "sanitized": sanitized,
            "recorded_utc": _utc_now(),
        }
        _write_status(str(run_path), payload)
        return payload

    try:
        Path(raw_file).write_bytes(proc.stdout)
    except OSError as exc:
        payload = {
            "status": "FAILED",
            "reason": f"RAW_WRITE_FAILED: {exc}",
            "session_id": requested,
            "metrics_path": metrics_file,
            "sanitized": sanitized,
            "recorded_utc": _utc_now(),
        }
        _write_status(str(run_path), payload)
        return payload

    try:
        summary = session_stats_mod.summarize(raw_file)
    except ValueError as exc:
        payload = {
            "status": "FAILED",
            "reason": f"INVALID_EXPORT: {exc}",
            "session_id": requested,
            "metrics_path": metrics_file,
            "sanitized": sanitized,
            "recorded_utc": _utc_now(),
        }
        _write_status(str(run_path), payload)
        return payload

    exported_id = summary.get("session_id")
    if not isinstance(exported_id, str) or exported_id != requested:
        payload = {
            "status": "FAILED",
            "reason": "ATTRIBUTION_MISMATCH",
            "session_id": requested,
            "metrics_path": metrics_file,
            "sanitized": sanitized,
            "recorded_utc": _utc_now(),
        }
        _write_status(str(run_path), payload)
        return payload

    fields: dict = {}
    for export_key, metric_field in EXPORT_TO_METRICS.items():
        value = summary.get(export_key)
        if value is None:
            continue  # absent stays absent; never synthesize zero/null numerics
        fields[metric_field] = value
    provenance = {field: "AUTOCAPTURED" for field in fields}
    kwargs: dict = dict(fields)
    if effective_task is not None:
        kwargs["task_id"] = effective_task
        provenance["task_id"] = task_provenance
    kwargs["task_class"] = "session-telemetry"
    provenance["task_class"] = "AUTOCAPTURED"
    try:
        metrics_mod.record(metrics_file, _provenance=provenance, **kwargs)
    except (OSError, ValueError) as exc:
        payload = {
            "status": "FAILED",
            "reason": f"METRICS_APPEND_FAILED: {exc}",
            "session_id": requested,
            "metrics_path": metrics_file,
            "sanitized": sanitized,
            "recorded_utc": _utc_now(),
        }
        _write_status(str(run_path), payload)
        return payload

    if delete_raw:
        with contextlib.suppress(OSError):
            Path(raw_file).unlink()
    payload = {
        "status": "CAPTURED",
        "reason": "OK",
        "session_id": requested,
        "metrics_path": metrics_file,
        "sanitized": sanitized,
        "fields": sorted(fields),
        "recorded_utc": _utc_now(),
    }
    _write_status(str(run_path), payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture one exact OpenCode session export into metrics.jsonl "
        "(aggregate-only, LOCAL_ONLY raw, fail-open telemetry)."
    )
    parser.add_argument("--run-dir", required=True, help="Foundry run directory (raw + status live here).")
    parser.add_argument("--session-id", required=True, help="Exact OpenCode session ID (never auto-selected).")
    parser.add_argument("--metrics", default=None, help="metrics.jsonl path (default: <run-dir>/metrics.jsonl).")
    parser.add_argument("--task-id", default=None, help="Workstream/task identity (default: run-dir context).")
    parser.add_argument("--opencode-bin", default=None, help="Exact OpenCode binary.")
    parser.add_argument("--worktree", default=None, help="Git worktree raw exports must stay outside of.")
    parser.add_argument("--timeout", type=int, default=60, help="Export subprocess timeout seconds.")
    parser.add_argument("--delete-raw", action="store_true", help="Remove raw export after aggregation.")
    parser.add_argument("--raw-path", default=None, help="Override raw export path (must stay LOCAL_ONLY).")
    args = parser.parse_args(argv)

    try:
        result = capture(
            run_dir=args.run_dir,
            session_id=args.session_id,
            metrics_path=args.metrics,
            opencode_bin=args.opencode_bin,
            task_id=args.task_id,
            worktree=args.worktree,
            timeout=args.timeout,
            delete_raw=args.delete_raw,
            raw_path=args.raw_path,
        )
    except ValueError as exc:
        print(f"TELEMETRY_PENDING: {exc}", file=sys.stderr)
        print(f"TELEMETRY_HINT: {format_hint(args.run_dir)}", file=sys.stderr)
        return 1
    if result.get("status") == "CAPTURED":
        # Aggregate identity only; never raw content, prompts, commands,
        # outputs, patches, or reasoning text.
        print(
            f"TELEMETRY_CAPTURED: session={result.get('session_id')} "
            f"metrics={result.get('metrics_path')} "
            f"fields={len(result.get('fields', []))} "
            f"sanitized={result.get('sanitized')}",
        )
        return 0
    print(
        f"TELEMETRY_PENDING: {result.get('reason')} session={result.get('session_id')}",
        file=sys.stderr,
    )
    print(f"TELEMETRY_HINT: {format_hint(args.run_dir)}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
