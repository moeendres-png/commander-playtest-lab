from __future__ import annotations

import argparse
import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".claude" / "skills" / "lab-ops" / "scripts" / "oc_dispatch.py"
spec = importlib.util.spec_from_file_location("oc_dispatch_under_test", SCRIPT)
assert spec and spec.loader
oc_dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oc_dispatch)

LAB = "moeendres-png/commander-playtest-lab"


def post_args(
    task: Path, lane: str = "oc", branch: str | None = None, dry_run: bool = True
) -> argparse.Namespace:
    return argparse.Namespace(
        issue=479, lane=lane, task=task, branch=branch, repo=LAB, dry_run=dry_run
    )


def test_oc_post_has_prefix_branch_and_the_fixed_footer(capsys, tmp_path):
    task = tmp_path / "task.md"
    task.write_text("**Objective.** Fix the thing.\n", encoding="utf-8")
    oc_dispatch.cmd_post(post_args(task, branch="ci/fix-20261006"))
    out = capsys.readouterr().out
    assert out.startswith("/oc ")
    assert "**Branch.** Work on `ci/fix-20261006` from current `main`" in out
    assert "No force-push" in out
    assert "never merge" in out
    assert "UNKNOWN != PASS" in out
    assert "NOT_RUN != PASS" in out
    assert "never weaken an" in out
    assert "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" in out
    assert "Claude-Session: https://claude.ai/code/session_01XoAKQUxcwkMyLLNvET1KVq" in out


def test_bunny_post_is_read_only_and_does_not_duplicate_the_prefix(capsys, tmp_path):
    task = tmp_path / "task.md"
    task.write_text("/bunny Audit the branch read-only.\n", encoding="utf-8")
    oc_dispatch.cmd_post(post_args(task, lane="bunny", branch="hardening/x-20261006"))
    out = capsys.readouterr().out
    assert out.startswith("/bunny Audit the branch read-only.")
    assert out.count("/bunny") == 1
    assert "Read-only" in out
    assert "No force-push" in out
    assert "UNKNOWN != PASS" in out
    assert "never merge" not in out


def test_post_creates_exactly_one_comment_with_the_body_on_stdin(monkeypatch, tmp_path):
    calls: list[dict] = []

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        return subprocess.CompletedProcess(cmd, 0, '{"html_url": "https://example.test/c/1"}', "")

    task = tmp_path / "task.md"
    task.write_text("**Objective.** Fix.\n", encoding="utf-8")
    monkeypatch.setattr(oc_dispatch.subprocess, "run", fake_run)
    oc_dispatch.cmd_post(post_args(task, branch="ci/x-20261006", dry_run=False))
    assert len(calls) == 1
    cmd = calls[0]["cmd"]
    assert cmd[:3] == ["gh", "api", "-X"]
    assert f"repos/{LAB}/issues/479/comments" in cmd
    assert calls[0]["kwargs"]["input"].startswith("{")
    assert "/oc " in calls[0]["kwargs"]["input"]
    assert "shell" not in calls[0]["kwargs"]


STARTED = {
    "id": 42,
    "status": "completed",
    "conclusion": "success",
    "html_url": "https://example.test/runs/42",
}
REPORT = """## Result

Work complete. PR opened.

## Tests

`python3 -m pytest -q tests/unit` -> 128 passed, 2 skipped in 4.20s

## Remaining blockers

- Forge lane is BLOCKED on the engine pin.
- The XMage column is UNKNOWN until PB-03 runs.
"""


def watch_api(path: str):
    if path.endswith("/actions/runs/42"):
        return STARTED
    if path.endswith("/jobs?per_page=50"):
        return {"jobs": [{"name": "opencode", "status": "completed", "conclusion": "success"}]}
    if "issues/comments" in path:
        return [
            {
                "html_url": "https://example.test/issues/479#issuecomment-7",
                "issue_url": "https://api.github.test/repos/x/issues/479",
                "body": "Created PR #9\n\n[github run](/x/actions/runs/42)",
            }
        ]
    if path.endswith("/pulls/9"):
        return {"head": {"ref": "ci/fix-20261006"}, "body": REPORT}
    raise AssertionError(f"unexpected api path: {path}")


def test_watch_prints_at_most_15_lines_with_outcome_tests_and_unknowns(monkeypatch, capsys):
    monkeypatch.setattr(oc_dispatch, "api", watch_api)
    oc_dispatch.cmd_watch(argparse.Namespace(run=42, issue=None, repo=LAB, interval=60, timeout=10))
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert len(lines) <= 15
    assert "run 42 oc success" in out
    assert "branch ci/fix-20261006, PR #9" in out
    assert "128 passed" in out
    assert "engine pin" in out and "XMage column" in out
    assert out.count("UNKNOWN") + out.count("BLOCKED") >= 2


def test_watch_says_plainly_when_the_run_posted_nothing(monkeypatch, capsys):
    def no_comment_api(path: str):
        if path.endswith("/actions/runs/42"):
            return STARTED
        if path.endswith("/jobs?per_page=50"):
            return {
                "jobs": [{"name": "opencode-bunny", "status": "completed", "conclusion": "failure"}]
            }
        if "issues/comments" in path:
            return []
        raise AssertionError(f"unexpected api path: {path}")

    monkeypatch.setattr(oc_dispatch, "api", no_comment_api)
    oc_dispatch.cmd_watch(argparse.Namespace(run=42, issue=None, repo=LAB, interval=60, timeout=10))
    out = capsys.readouterr().out
    assert "run 42 bunny success (job failure)" in out
    assert "no report comment" in out
    assert len(out.splitlines()) <= 15


@pytest.mark.parametrize(
    "body",
    [
        "- a row is UNKNOWN until PB-03",
        "- a lane is BLOCKED on the pin",
        "**Remaining blockers**\n- missing engine checkout",
    ],
)
def test_non_credit_items_are_extracted(body):
    assert oc_dispatch.non_credit_items(body)


def test_non_credit_items_respect_the_cap():
    body = "\n".join(f"- item {n} is UNKNOWN" for n in range(12))
    assert len(oc_dispatch.non_credit_items(body)) == 5


def test_rescue_reports_plainly_when_the_run_left_no_artifact(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(oc_dispatch, "api", lambda path, body=None: {"artifacts": []})
    oc_dispatch.cmd_rescue(argparse.Namespace(run=7, repo=LAB, out=str(tmp_path)))
    assert "no unexpired opencode-rescue artifact" in capsys.readouterr().out


def test_rescue_downloads_only_rescue_artifacts_and_pushes_nothing(monkeypatch, capsys, tmp_path):
    artifacts = [
        {"name": "opencode-rescue-opencode-7", "expired": False},
        {"name": "pb03-packet", "expired": False},
        {"name": "opencode-rescue-opencode-bunny-7", "expired": True},
    ]
    monkeypatch.setattr(oc_dispatch, "api", lambda path, body=None: {"artifacts": artifacts})
    calls: list[list[str]] = []

    def fake_run(cmd, check):
        calls.append(cmd)
        out = Path(cmd[cmd.index("-D") + 1])
        (out / "log.txt").write_text("abc123 agent work\n", encoding="utf-8")
        (out / "status.txt").write_text("", encoding="utf-8")
        (out / "work.bundle").write_bytes(b"bundle")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(oc_dispatch.subprocess, "run", fake_run)
    oc_dispatch.cmd_rescue(argparse.Namespace(run=7, repo=LAB, out=str(tmp_path)))
    assert [c[c.index("-n") + 1] for c in calls] == ["opencode-rescue-opencode-7"]
    assert all(c[:3] == ["gh", "run", "download"] for c in calls)
    out = capsys.readouterr().out
    assert "abc123 agent work" in out
    assert "git fetch" in out and "work.bundle" in out


def test_oc_footer_forbids_closing_keywords():
    text = oc_dispatch.footer("oc")
    assert "Never write a GitHub closing keyword" in text
    assert "Refs #N" in text
