from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".claude" / "skills" / "lab-ops" / "scripts" / "gh_ops.py"
spec = importlib.util.spec_from_file_location("gh_ops_under_test", SCRIPT)
assert spec and spec.loader
gh_ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gh_ops)

LAB = "moeendres-png/commander-playtest-lab"
HEAD = "a" * 40
PULL = {
    "number": 574,
    "draft": False,
    "mergeable_state": "blocked",
    "title": "Starting player: never a Lab default (#572)",
    "head": {"ref": "opencode/oc572-starting-player-20261006", "sha": HEAD},
}
CHECK_RUNS = {
    HEAD: {
        "check_runs": [
            {"id": 1, "name": "quality", "status": "completed", "conclusion": "failure"},
            {
                "id": 2,
                "name": "ci-definition-integrity-shadow",
                "status": "completed",
                "conclusion": "failure",
            },
            {"id": 3, "name": "build", "status": "completed", "conclusion": "success"},
        ]
    }
}
RUNS = [
    {
        "id": 111,
        "status": "in_progress",
        "conclusion": None,
        "event": "issue_comment",
        "display_title": "A running lane issue",
        "html_url": "https://example.test/runs/111",
    },
    {
        "id": 222,
        "status": "completed",
        "conclusion": "success",
        "event": "issue_comment",
        "display_title": "An audited lane issue",
        "html_url": "https://example.test/runs/222",
    },
    {
        "id": 333,
        "status": "completed",
        "conclusion": "skipped",
        "event": "issue_comment",
        "display_title": "A comment with no mention",
        "html_url": "https://example.test/runs/333",
    },
]
JOBS = {
    111: [{"name": "opencode", "status": "in_progress", "conclusion": None}],
    222: [
        {"name": "opencode-bunny", "status": "completed", "conclusion": "success"},
        {"name": "opencode", "status": "completed", "conclusion": "skipped"},
    ],
}
COMMENTS = [
    {
        "html_url": "https://example.test/issues/701#issuecomment-1",
        "issue_url": f"https://api.github.test/repos/{LAB}/issues/701",
        "body": (
            "Created PR #9\n\n[github run](/moeendres-png/commander-playtest-lab/actions/runs/222)"
        ),
    }
]
ISSUES = [
    {"number": 700, "title": "A running lane issue"},
    {"number": 701, "title": "An audited lane issue"},
]
PB03_RUNS = [
    {
        "id": 900,
        "status": "in_progress",
        "conclusion": None,
        "head_branch": "main",
        "html_url": "https://example.test/runs/900",
    }
]


def fake_api(path: str):
    if "ccr/review_threads" in path:
        raise SystemExit("gh api: Not Found (HTTP 404)")
    if path.endswith("/pulls/574"):
        return PULL
    if "/pulls?" in path:
        return [PULL] if LAB in path else []
    if "/check-runs?" in path:
        sha = path.split("/commits/")[1].split("/")[0]
        return CHECK_RUNS[sha]
    if "/actions/workflows/opencode.yml/runs" in path:
        return {"workflow_runs": RUNS}
    if "/actions/runs/" in path and path.endswith("/jobs?per_page=50"):
        run_id = int(path.split("/actions/runs/")[1].split("/")[0])
        return {"jobs": JOBS[run_id]}
    if "/actions/workflows/pb03-runtime-qualification.yml/runs" in path:
        return {"workflow_runs": PB03_RUNS}
    if "issues/comments" in path:
        return COMMENTS
    if "issues?state=all" in path:
        return ISSUES
    if "matching-refs/heads/opencode/issue" in path:
        issue = path.split("issue")[-1].split("-")[0]
        return [{"ref": f"refs/heads/opencode/issue{issue}-20261006"}]
    raise AssertionError(f"unexpected api path: {path}")


def test_brief_is_one_screen_and_covers_every_lane(monkeypatch, capsys, tmp_path):
    epoch_root = tmp_path / gh_ops.EPOCH_ROOT
    for epoch, created in (
        ("111111111111-aaaaaaaaaaaa", "2026-10-05T01:00:00+00:00"),
        ("222222222222-bbbbbbbbbbbb", "2026-10-06T02:04:38+00:00"),
    ):
        directory = epoch_root / epoch
        directory.mkdir(parents=True)
        (directory / "EPOCH_IDENTITY.json").write_text(
            json.dumps({"epoch_id": epoch, "created_utc": created}), encoding="utf-8"
        )
    monkeypatch.setattr(gh_ops, "api", fake_api)
    gh_ops.cmd_brief(argparse.Namespace(repo=LAB, lab=str(tmp_path)))
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert len(lines) <= 25
    assert "shadow=red-by-design" in out
    assert "opencode/oc572-starting-player-20261006" in out
    assert "red=quality" in out
    assert "threads=?" in out
    assert "run 222 success PR #9 -> https://example.test/issues/701#issuecomment-1" in out
    assert "run 111 running issue #700 -> https://example.test/runs/111" in out
    assert "run 333" not in out
    assert "pb03 run 900 in_progress" in out
    assert "epoch 222222222222-bbbbbbbbbbbb sealed 2026-10-06T02:04" in out
    assert "check_runs" not in out and "{" not in out


def test_brief_reports_a_pushed_branch_without_a_pr(monkeypatch, capsys, tmp_path):
    run = dict(RUNS[1], id=444, display_title="An audited lane issue")
    comment = dict(COMMENTS[0], body="audit done\n[github run](/x/actions/runs/444)")
    monkeypatch.setattr(
        gh_ops,
        "api",
        lambda path: (
            {"workflow_runs": [run]}
            if "opencode.yml/runs" in path
            else [comment]
            if "issues/comments" in path
            else {"jobs": [{"name": "opencode", "status": "completed", "conclusion": "success"}]}
            if path.endswith("/jobs?per_page=50")
            else [{"ref": "refs/heads/opencode/issue701-20261006"}]
            if "matching-refs" in path
            else []
            if "/pulls?" in path
            else {"workflow_runs": []}
        ),
    )
    gh_ops.cmd_brief(argparse.Namespace(repo=LAB, lab=str(tmp_path)))
    out = capsys.readouterr().out
    assert "opencode/issue701-20261006" in out


def test_newest_epoch_absent_is_unknown_not_a_guess(tmp_path):
    assert "unavailable" in gh_ops.newest_epoch(tmp_path)
