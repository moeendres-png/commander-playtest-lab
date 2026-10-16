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
    592: [
        {
            "user": {"login": "moeendres-png"},
            "body": (
                "## Baton: session Z\n\n"
                "**Ownership.** session Z owned this lane.\n\n"
                "**Exact Next Action.** nothing, it is closed\n"
            ),
        }
    ],
}
ISSUE_TITLES = {
    441: "Lane 441",
    479: "Lane 479",
    561: "Lane 561",
    572: "Lane 572",
    592: "Closed lane 592",
}
ISSUE_STATES = {441: "open", 479: "open", 592: "closed"}
# 574 is an open PR; 600 was merged, so it is not live.
PR_STATES = {
    574: {"state": "open", "merged_at": None},
    600: {"state": "closed", "merged_at": "2026-10-01T00:00:00Z"},
}


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
        return {"title": ISSUE_TITLES[number], "state": ISSUE_STATES.get(number, "open")}
    if "/pulls/" in url and url.split("/pulls/")[1].isdigit():
        return PR_STATES[int(url.split("/pulls/")[1])]
    if url.endswith("/pulls?state=open&per_page=20"):
        return (
            []
            if "mage" in url
            else [{"number": 574, "head": {"ref": "opencode/x", "sha": "f" * 40}}]
        )
    if url.endswith("/commits/main"):
        return {"sha": "d" * 40}
    if url.endswith(LAB) or url.endswith("mage"):
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


def test_no_open_issue_means_no_lane_not_a_stale_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, "api", lambda url: None)
    assert handoff.lane_issues() == ()
    assert handoff.lane_lines(tmp_path, [], ()) == ["(no open issues)"]


def test_an_unreachable_engine_fork_is_reported_not_fatal(tmp_path, monkeypatch, fake_env):
    def scoped_api(url: str):
        if "moeendres-png/mage" in url:
            raise handoff.ApiUnavailable(f"gh api {url}: HTTP 403")
        return fake_api(url)

    monkeypatch.setattr(handoff, "api", scoped_api)
    lines = handoff.repo_head_lines(tmp_path)
    assert "mage unavailable (no GitHub access from this session)" in lines
    assert not any(line.startswith("forge ") for line in lines)


def test_an_unreachable_lab_still_aborts(tmp_path, monkeypatch, fake_env):
    def no_lab(url: str):
        if handoff.LAB in url:
            raise handoff.ApiUnavailable(f"gh api {url}: HTTP 403")
        return fake_api(url)

    monkeypatch.setattr(handoff, "api", no_lab)
    with pytest.raises(SystemExit, match="HTTP 403"):
        handoff.repo_head_lines(tmp_path)


def _write_state(tmp_path: Path, name: str, body: str) -> None:
    (tmp_path / ".foundry").mkdir(exist_ok=True)
    (tmp_path / ".foundry" / name).write_text(body, encoding="utf-8")


def test_open_issue_is_a_lane_but_a_closed_issue_with_a_baton_is_not(tmp_path, fake_env):
    lines = handoff.lane_lines(tmp_path, [], (441, 592))
    assert lines == ["#441 Lane 441 [open] owner=session A next=land the fix"]
    assert not any("#592" in line for line in lines)


def test_a_no_comment_open_issue_is_still_included(tmp_path, fake_env):
    assert handoff.lane_lines(tmp_path, [], (479,)) == ["#479 Lane 479 [open] owner=? next=-"]


def test_open_prs_are_listed_with_head_sha(tmp_path, fake_env):
    lines = handoff.repo_head_lines(tmp_path)
    assert "commander-playtest-lab PR #574 opencode/x -> ffffffff" in lines


def test_decision_referencing_a_merged_pr_or_closed_issue_is_excluded(tmp_path, fake_env):
    _write_state(
        tmp_path,
        "merged-pr.yaml",
        "ownership: WS-MERGED-PR\nstatus: WAITING\n"
        "pr_url: https://github.com/moeendres-png/commander-playtest-lab/pull/600\n"
        "authority_gates:\n- Merged PR gate\n",
    )
    _write_state(
        tmp_path,
        "closed-issue.yaml",
        "ownership: WS-CLOSED-ISSUE\nstatus: WAITING\nissue: 592\n"
        "authority_gates:\n- Closed issue gate\n",
    )
    lines = handoff.decision_lines(tmp_path, handoff.load_states(tmp_path))
    assert lines == ["(none recorded in .foundry state)"]


def test_resolved_or_closed_out_decision_is_excluded(tmp_path, fake_env):
    _write_state(
        tmp_path,
        "superseded.yaml",
        "ownership: WS-SUPERSEDED\nstatus: SUPERSEDED\nauthority_gates:\n- Superseded gate\n",
    )
    _write_state(
        tmp_path,
        "closed-out.yaml",
        "ownership: WS-CLOSED-OUT\nstatus: WAITING\n"
        "closed_out: 'handoff ledger cleanup'\n"
        "authority_gates:\n- Closed out gate\n",
    )
    lines = handoff.decision_lines(tmp_path, handoff.load_states(tmp_path))
    assert lines == ["(none recorded in .foundry state)"]


def test_a_still_open_decision_stays(tmp_path, fake_env):
    _write_state(
        tmp_path,
        "live-issue.yaml",
        "ownership: WS-LIVE-ISSUE\nstatus: WAITING\nissue: 479\n"
        "authority_gates:\n- Live issue gate\n",
    )
    _write_state(
        tmp_path,
        "live-pr.yaml",
        "ownership: WS-LIVE-PR\nstatus: WAITING\n"
        "pr_url: https://github.com/moeendres-png/commander-playtest-lab/pull/574\n"
        "authority_gates:\n- Live PR gate\n",
    )
    joined = "\n".join(handoff.decision_lines(tmp_path, handoff.load_states(tmp_path)))
    assert "WS-LIVE-ISSUE: Live issue gate" in joined
    assert "WS-LIVE-PR: Live PR gate" in joined


def test_render_shows_only_the_live_decision(tmp_path, fake_env):
    _write_state(
        tmp_path,
        "stale.yaml",
        "ownership: WS-STALE\nstatus: SUPERSEDED\nauthority_gates:\n- Stale gate\n",
    )
    _write_state(
        tmp_path,
        "live.yaml",
        "ownership: WS-LIVE\nstatus: WAITING\nissue: 479\nauthority_gates:\n- Live gate\n",
    )
    text = handoff.render(tmp_path, "2026-10-16T00:00Z")
    assert "WS-LIVE: Live gate" in text
    assert "WS-STALE" not in text
