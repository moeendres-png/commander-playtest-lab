"""Stop an OpenCode run promptly when the provider refuses it for quota.

The pinned CLI (``opencode github run`` 1.18.30) does not exit when every model
call is refused with HTTP 429 ``GoUsageLimitError``: it prints the error, retries,
prints ``AI_RetryError`` and then hangs until the workflow's 55-minute step
timeout (runs 37981118028, 37981119802, 37981121170, 37986520394, 38012159229
and 38012694554 all died this way, each needing a manual cancel). A quota
refusal is not retryable inside one run, so waiting only burns runner time and
hides the real cause behind a generic timeout.

Usage (the workflow runs a copy taken from the triggering commit)::

    python3 -I quota_watchdog.py [--log FILE] -- opencode github run

``--log FILE`` also copies the output to FILE, so a later step can audit the
run's own runtime records (``review_runtime_identity.py audit``).

The watchdog runs the command in its own process group and copies its combined
stdout/stderr through unchanged. It stops the group, and exits with
``EXIT_BLOCKED_SERVICE``, only on the provider's own error record: a
``statusCode: 429`` line followed within a few lines by a ``responseBody`` whose
JSON has ``error.type == "GoUsageLimitError"``. Then:

- ``limitName`` in ``NON_RETRYABLE_LIMITS`` (monthly, weekly) stops at once;
- any other limit stops once the CLI reports ``AI_RetryError`` (its own
  retries are spent and it would only hang).

Prose that merely mentions the error (an issue comment quoting it, a prompt)
never matches, because only the parsed provider response counts. Every other
outcome returns the command's own exit code. The result is ``BLOCKED_SERVICE``,
never PASS: no agent work happened, and the rescue steps still run.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import signal
import subprocess
import sys
from collections import deque
from dataclasses import dataclass
from typing import IO

EXIT_BLOCKED_SERVICE = 75  # EX_TEMPFAIL
NON_RETRYABLE_LIMITS = frozenset({"monthly", "weekly"})
QUOTA_ERROR_TYPE = "GoUsageLimitError"
# How many lines may separate ``statusCode: 429`` from its ``responseBody``
# (``responseHeaders`` sits between them in the CLI's error record).
STATUS_WINDOW = 6
TERMINATE_GRACE_SECONDS = 10.0

_STATUS_429 = re.compile(r"^\s*statusCode:\s*429,?\s*$")
_RESPONSE_BODY = re.compile(r'^\s*responseBody:\s*"(?P<body>.*)",?\s*$')
_RETRY_EXHAUSTED = re.compile(r"^\s*AI_RetryError\b")


@dataclass(frozen=True)
class QuotaRefusal:
    """A provider quota refusal that ends the run."""

    limit_name: str

    def message(self) -> str:
        return (
            f"OpenCode Go usage limit reached (HTTP 429 {QUOTA_ERROR_TYPE}, "
            f"limitName={self.limit_name}). Not retryable inside this run: stopped the CLI "
            "instead of waiting for the step timeout. BLOCKED_SERVICE, not PASS; restoring "
            "the quota is an Owner decision."
        )


def _quota_limit(body_literal: str) -> str | None:
    """The ``limitName`` of a GoUsageLimitError response body, else None."""
    try:
        body = json.loads(json.loads(f'"{body_literal}"'))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    if not isinstance(error, dict) or error.get("type") != QUOTA_ERROR_TYPE:
        return None
    metadata = body.get("metadata")
    limit = metadata.get("limitName") if isinstance(metadata, dict) else None
    return limit if isinstance(limit, str) and limit else "unknown"


class QuotaScanner:
    """Feed output lines; ``feed`` returns the refusal that ends the run, if any."""

    def __init__(self) -> None:
        self._recent: deque[str] = deque(maxlen=STATUS_WINDOW)
        self._seen_limit: str | None = None

    def feed(self, line: str) -> QuotaRefusal | None:
        recent = list(self._recent)
        self._recent.append(line)
        if _RETRY_EXHAUSTED.match(line) and self._seen_limit is not None:
            return QuotaRefusal(self._seen_limit)
        match = _RESPONSE_BODY.match(line)
        if match is None or not any(_STATUS_429.match(r) for r in recent):
            return None
        limit = _quota_limit(match.group("body"))
        if limit is None:
            return None
        self._seen_limit = limit
        if limit in NON_RETRYABLE_LIMITS:
            return QuotaRefusal(limit)
        return None


def _signal_group(pgid: int, sig: int) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pgid, sig)


def _stop(proc: subprocess.Popen[bytes]) -> None:
    _signal_group(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        _signal_group(proc.pid, signal.SIGKILL)
        proc.wait()


def _report(refusal: QuotaRefusal, out: IO[str]) -> None:
    out.write(f"::error title=BLOCKED_SERVICE::{refusal.message()}\n")
    out.flush()
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"**BLOCKED_SERVICE** - {refusal.message()}\n")


def run(command: list[str], *, out: IO[bytes] | None = None, log: IO[bytes] | None = None) -> int:
    """Run ``command``, copy its output to ``out`` (and ``log``) and stop it on a quota refusal."""
    sink = out if out is not None else sys.stdout.buffer
    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True
    )

    def forward(signum: int, _frame: object) -> None:
        _signal_group(proc.pid, signum)

    previous = {s: signal.signal(s, forward) for s in (signal.SIGINT, signal.SIGTERM)}
    scanner = QuotaScanner()
    refusal: QuotaRefusal | None = None
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            sink.write(raw)
            sink.flush()
            if log is not None:
                log.write(raw)
                log.flush()
            refusal = scanner.feed(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
            if refusal is not None:
                break
        if refusal is not None:
            _stop(proc)
            proc.stdout.close()
        returncode = proc.wait()
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    if refusal is not None:
        _report(refusal, sys.stdout)
        return EXIT_BLOCKED_SERVICE
    return returncode if returncode >= 0 else 128 - returncode


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    log_path: str | None = None
    if args[:1] == ["--log"]:
        if len(args) < 2:
            sys.stderr.write("usage: quota_watchdog.py [--log FILE] -- COMMAND [ARG...]\n")
            return 2
        log_path, args = args[1], args[2:]
    if args[:1] == ["--"]:
        args = args[1:]
    if not args:
        sys.stderr.write("usage: quota_watchdog.py [--log FILE] -- COMMAND [ARG...]\n")
        return 2
    if log_path is None:
        return run(args)
    with open(log_path, "wb") as log:
        return run(args, log=log)


if __name__ == "__main__":
    sys.exit(main())
