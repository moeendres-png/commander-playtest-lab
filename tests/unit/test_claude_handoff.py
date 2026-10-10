from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "claude_handoff.py"
spec = importlib.util.spec_from_file_location("claude_handoff_under_test", SCRIPT)
assert spec and spec.loader
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)

LAB = "moeendres-png/commander-playtest-lab"
WORKTREES = """worktree /wt/main
HEAD aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
branch refs/heads/main

worktree /wt/feature
HEAD bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
branch refs/heads/feat

worktree /wt/detached
HEAD cccccccccccccccccccccccccccccccccccccccc
detached

"""
COMMENTS = {
    441: [
        {
            "user": {"login": "moeendres-png"},
            "body": (
                "## Baton: session A\n\n"
                "**Ownership.** session A takes over the lane.\n\n"
                "**Exact Next Action.** land the fix\n"
            ),
        }
    ],
}
ISSUE_TITLES = {441: "Lane 441", 479: "Lane 479", 561: "Lane 561", 572: "Lane 572"}


@pytest.fixture
def fake_env(monkeypatch):
    monkeypatch.setattr(handoff, "git", fake_git)
    monkeypatch.setattr(handoff, "api", fake_api)


def fake_git(repo_dir: Path, *args: str):
    path = str(repo_dir)
    joined = " ".join(args)
    if joined == "worktree list --porcelain":
        return WORKTREES
    if joined == "status --porcelain":
        return " M src/a.py\n M src/b.py" if path == "/wt/feature" else ""
    if joined == "rev-parse --abbrev-ref HEAD":
        return "main"
    if joined == "rev-parse HEAD":
        return "a" * 40
    if joined == "rev-parse --verify --quiet refs/remotes/origin/main":
        return "d" * 40
    if joined == "rev-parse --verify --quiet refs/remotes/origin/feat":
        return "e" * 40
    if joined == "rev-list --count origin/feat..HEAD":
        return "3"
    if joined == "rev-list --count origin/main..HEAD":
        return "0"
    if joined.startswith("log -1 --format=%ct"):
        return "200" if "waiting" in joined else "100"
    raise AssertionError(f"unexpected git call: {path} {joined}")


OPEN_ISSUES = [
    {"number": 441, "title": "Lane 441"},
    {"number": 479, "title": "Lane 479"},
    {"number": 600, "title": "a pull request", "pull_request": {}},
]


def fake_api(url: str):
    if url.endswith("/issues?state=open&per_page=50"):
        return OPEN_ISSUES
    if "/issues/" in url and url.endswith("/comments?per_page=100"):
        return COMMENTS.get(int(url.split("/issues/")[1].split("/")[0]), [])
    if "/issues/" in url:
        number = int(url.split("/issues/")[1].split("?")[0])
        return {"title": ISSUE_TITLES[number], "state": "open"}
    if url.endswith("/pulls?state=open&per_page=20"):
        return (
            []
            if "mage" in url or "forge" in url
            else [{"number": 574, "head": {"ref": "opencode/x", "sha": "f" * 40}}]
        )
    if url.endswith("/commits/main"):
        return {"sha": "d" * 40}
    if url.endswith(LAB) or url.endswith("mage") or url.endswith("forge"):
        return {"default_branch": "main"}
    raise AssertionError(f"unexpected api url: {url}")


def test_render_is_deterministic_and_capped(tmp_path, fake_env):
    (tmp_path / ".foundry").mkdir()
    (tmp_path / ".foundry" / "waiting.yaml").write_text(
        "schema_version: '2.0'\n"
        "ownership: WS-WAITING\n"
        "status: WAITING\n"
        "issue: 479\n"
        "authority_gates:\n- Choose option A or B\n"
        "exact_next_action: do the waiting thing\n",
        encoding="utf-8",
    )
    (tmp_path / ".foundry" / "complete.yaml").write_text(
        "schema_version: '2.0'\n"
        "ownership: WS-COMPLETE\n"
        "status: COMPLETE\n"
        "exact_next_action: nothing left\n",
        encoding="utf-8",
    )
    first = handoff.render(tmp_path, "2026-10-06T18:00Z")
    second = handoff.render(tmp_path, "2026-10-06T18:00Z")
    assert first == second
    assert len(first.splitlines()) <= handoff.MAX_LINES


def test_render_covers_lanes_heads_worktrees_and_decisions(tmp_path, fake_env):
    (tmp_path / ".foundry").mkdir()
    (tmp_path / ".foundry" / "waiting.yaml").write_text(
        "schema_version: '2.0'\n"
        "ownership: WS-WAITING\n"
        "status: WAITING\n"
        "issue: 479\n"
        "authority_gates:\n- Choose option A or B\n"
        "exact_next_action: do the waiting thing\n",
        encoding="utf-8",
    )
    (tmp_path / ".foundry" / "complete.yaml").write_text(
        "schema_version: '2.0'\n"
        "ownership: WS-COMPLETE\n"
        "status: COMPLETE\n"
        "exact_next_action: nothing left\n",
        encoding="utf-8",
    )
    text = handoff.render(tmp_path, "2026-10-06T18:00Z")
    assert "# Claude handoff — 2026-10-06T18:00Z" in text
    assert "owner=session A" in text
    assert "next=land the fix" in text
    assert "next=do the waiting thing" in text
    assert "lab HEAD main@aaaaaaaa (clean) origin/main=dddddddd" in text
    assert "PR #574 opencode/x -> ffffffff" in text
    assert "/wt/feature [feat] dirty=2 unpushed=3" in text
    assert "/wt/detached" not in text
    assert "WS-WAITING: Choose option A or B" in text
    assert "WS-COMPLETE" not in text


def test_lanes_are_the_open_issues_without_pull_requests(fake_env):
    assert handoff.lane_issues() == (479, 441)


def test_lanes_fall_back_when_the_api_answers_nothing(monkeypatch):
    monkeypatch.setattr(handoff, "api", lambda url: None)
    assert handoff.lane_issues() == handoff.LANE_ISSUES


def test_an_unreachable_engine_fork_is_reported_not_fatal(tmp_path, monkeypatch, fake_env):
    def scoped_api(url: str):
        if "moeendres-png/mage" in url:
            raise handoff.ApiUnavailable(f"gh api {url}: HTTP 403")
        return fake_api(url)

    monkeypatch.setattr(handoff, "api", scoped_api)
    lines = handoff.repo_head_lines(tmp_path)
    assert "mage unavailable (no GitHub access from this session)" in lines
    assert any(line.startswith("forge ") and "unavailable" not in line for line in lines)


def test_an_unreachable_lab_still_aborts(tmp_path, monkeypatch, fake_env):
    def no_lab(url: str):
        if handoff.LAB in url:
            raise handoff.ApiUnavailable(f"gh api {url}: HTTP 403")
        return fake_api(url)

    monkeypatch.setattr(handoff, "api", no_lab)
    with pytest.raises(SystemExit, match="HTTP 403"):
        handoff.repo_head_lines(tmp_path)
