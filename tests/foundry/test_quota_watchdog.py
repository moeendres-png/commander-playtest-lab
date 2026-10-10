"""The OpenCode quota watchdog stops a quota-refused run instead of letting it hang.

The fixture is the provider error section of real run 38012694554 (job
114096050934), timestamps stripped and workspace/session ids redacted. After it
the pinned CLI printed nothing for two minutes until the run was cancelled by
hand; the fake child below reproduces that by sleeping after replaying it.
"""

from __future__ import annotations

import io
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import yaml
from tools.foundry import quota_watchdog as qw

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "opencode_go_quota_429_run38012694554.log"
WORKFLOW = ROOT / ".github/workflows/opencode.yml"
HANG_SECONDS = 45


def _child(tmp_path: Path, lines: list[str], *, then: str) -> list[str]:
    """A command that prints ``lines`` and then runs ``then`` (python source)."""
    data = tmp_path / "out.txt"
    data.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    script = tmp_path / "child.py"
    script.write_text(
        textwrap.dedent(
            f"""
            import sys, time
            sys.stdout.write(open({str(data)!r}, encoding="utf-8").read())
            sys.stdout.flush()
            {then}
            """
        ),
        encoding="utf-8",
    )
    return [sys.executable, "-I", str(script)]


def _run(command: list[str]) -> tuple[int, str, float]:
    sink = io.BytesIO()
    started = time.monotonic()
    code = qw.run(command, out=sink)
    return code, sink.getvalue().decode("utf-8"), time.monotonic() - started


def test_real_quota_log_stops_the_hung_cli_at_once(tmp_path, capsys):
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    code, copied, elapsed = _run(_child(tmp_path, lines, then=f"time.sleep({HANG_SECONDS})"))
    assert code == qw.EXIT_BLOCKED_SERVICE
    assert elapsed < 30, elapsed
    # Output is copied through unchanged up to and including the refusal record.
    first_body = next(i for i, line in enumerate(lines) if "responseBody" in line)
    assert copied.splitlines()[: first_body + 1] == lines[: first_body + 1]
    annotation = capsys.readouterr().out
    assert annotation.startswith("::error title=BLOCKED_SERVICE::")
    assert "limitName=monthly" in annotation
    assert "not PASS" in annotation


def test_old_bare_command_hangs_on_the_same_log(tmp_path):
    """Control: without the watchdog the replayed run does not end by itself."""
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    proc = subprocess.Popen(
        _child(tmp_path, lines, then=f"time.sleep({HANG_SECONDS})"),
        stdout=subprocess.DEVNULL,
    )
    try:
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            hung = True
        else:
            hung = False
    finally:
        proc.kill()
        proc.wait()
    assert hung


def test_step_summary_records_blocked_service(tmp_path, monkeypatch, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    assert (
        _run(_child(tmp_path, lines, then=f"time.sleep({HANG_SECONDS})"))[0]
        == qw.EXIT_BLOCKED_SERVICE
    )
    assert summary.read_text(encoding="utf-8").startswith("**BLOCKED_SERVICE**")
    capsys.readouterr()


PROSE = [
    "Both fail before model work with HTTP429 GoUsageLimitError, limitName=monthly.",
    'responseBody: "{\\"type\\":\\"error\\",\\"error\\":{\\"type\\":\\"GoUsageLimitError\\"}}",',
    "AI_RetryError: Failed after 3 attempts. Last error: Go usage limit exceeded",
    " statusCode: 429,",
    ' responseBody: "{not json",',
    ' responseBody: "{\\"type\\":\\"error\\",\\"error\\":{\\"type\\":\\"RateLimitError\\"}}",',
]


def test_prose_and_other_errors_never_stop_the_run(tmp_path):
    """Quoted error text, a body without its 429 status, malformed or other
    error bodies, and a retry error with no parsed quota refusal all pass
    through; the command's own exit code is returned."""
    code, copied, _ = _run(_child(tmp_path, PROSE, then="sys.exit(0)"))
    assert code == 0
    assert copied.splitlines() == PROSE


def _refusal(limit: str) -> list[str]:
    body = (
        '{\\"type\\":\\"error\\",\\"error\\":{\\"type\\":\\"GoUsageLimitError\\",'
        '\\"message\\":\\"Go usage limit exceeded\\"},\\"metadata\\":{\\"limitName\\":\\"'
        + limit
        + '\\"}}'
    )
    return [" statusCode: 429,", " responseHeaders: [Object ...],", f' responseBody: "{body}",']


def test_short_window_limit_waits_for_the_cli_to_spend_its_retries(tmp_path, capsys):
    refusal = _refusal("rolling")
    code, _, _ = _run(_child(tmp_path, refusal, then="sys.exit(0)"))
    assert code == 0  # one refusal of a short-window limit alone does not stop the run
    lines = [*refusal, "AI_RetryError: Failed after 3 attempts. Last error: Go usage limit"]
    code, _, elapsed = _run(_child(tmp_path, lines, then=f"time.sleep({HANG_SECONDS})"))
    assert code == qw.EXIT_BLOCKED_SERVICE and elapsed < 30
    assert "limitName=rolling" in capsys.readouterr().out


def test_weekly_limit_stops_at_once(tmp_path, capsys):
    code, _, elapsed = _run(
        _child(tmp_path, _refusal("weekly"), then=f"time.sleep({HANG_SECONDS})")
    )
    assert code == qw.EXIT_BLOCKED_SERVICE and elapsed < 30
    capsys.readouterr()


def test_exit_codes_pass_through(tmp_path):
    assert _run(_child(tmp_path, ["ok"], then="sys.exit(3)"))[0] == 3
    killed = "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"
    assert _run(_child(tmp_path, ["ok"], then=killed))[0] == 128 + signal.SIGTERM


def test_cli_entry_requires_a_command(capsys):
    assert qw.main(["--"]) == 2
    assert "usage" in capsys.readouterr().err


def test_every_opencode_run_goes_through_the_trusted_watchdog_copy():
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    runs = [
        step
        for job in doc["jobs"].values()
        for step in job["steps"]
        if step.get("name") == "Run opencode"
    ]
    assert len(runs) == 3
    for step in runs:
        script = step["run"]
        assert "set -euo pipefail" in script
        # Copied from the triggering commit, never from the workspace the agent may change.
        assert '"${GITHUB_SHA}:tools/foundry/quota_watchdog.py"' in script
        assert script.rstrip().endswith('python3 -I "$watchdog" -- opencode github run')
        assert "OPENCODE_API_KEY" in step["env"]
        assert 0 < step["timeout-minutes"] <= 55
