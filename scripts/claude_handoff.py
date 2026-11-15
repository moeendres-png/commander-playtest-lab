#!/usr/bin/env python3
"""Write the <=60-line cold-start index for a fresh Claude session.

    scripts/claude_handoff.py [--repo-dir .] [--out docs/claude/state/HANDOFF.md]
                              [--repo O/R] [--now 2026-10-06T00:00Z] [--dry-run]

The file is assembled from local git (HEAD, worktrees, dirty/unpushed state),
the GitHub API (`gh api`: open issues and PRs, lane baton comments), and the
engine pin and newest sealed epoch in `config/rules_engines.json`. It is an
operational index, not Source Authority: Git, tests and GitHub stay canonical,
and a fresh session starts here instead of re-reading a compacted conversation.
Only the one output file is written.

Only live state is shown: lanes are open issues (closed issues and merged or
closed PRs never appear).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LAB = "moeendres-png/commander-playtest-lab"
REPOS = (LAB, "moeendres-png/mage")
MAX_LANES = 8
MAX_LINES = 60
BATON_MARKER = re.compile(r"(?i)\b(baton|ownership|owner|owns|handoff)\b")
OWNER_LINE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?#*\s*\*{0,2}(?:owner|ownership|baton)\*{0,2}\s*[:.\u2014-]\s*(.+)$"
)
NEXT_LINE = re.compile(
    r"(?im)^\s*(?:[-*#>\s]|\*\*)*(?:exact\s+)?next\s+action\*{0,2}\s*[:.\u2014-]\s*(.+)$"
)


def api(path: str) -> Any:
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise ApiUnavailable(f"gh api {path}: {out.stderr.strip() or out.stdout.strip()}")
    return json.loads(out.stdout or "null")


class ApiUnavailable(SystemExit):
    """A ``gh api`` call failed (no access, network, rate limit)."""


def git(repo_dir: Path, *args: str) -> str | None:
    out = subprocess.run(
        ["git", "-C", str(repo_dir), *args], capture_output=True, text=True, check=False
    )
    return out.stdout.strip() if out.returncode == 0 else None


def clip(text: str, limit: int) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "\u2026"


def display_path(path: Path, repo_dir: Path) -> str:
    """A worktree path relative to the repository: never an absolute local path."""
    if path == repo_dir:
        return "."
    if repo_dir in path.parents:
        return path.relative_to(repo_dir).as_posix()
    if path.parent == repo_dir.parent:
        return f"../{path.name}"
    return path.name


def worktree_lines(repo_dir: Path) -> list[str]:
    raw = git(repo_dir, "worktree", "list", "--porcelain") or ""
    blocks: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in [*raw.splitlines(), ""]:
        if not line.strip():
            if current:
                blocks.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    lines: list[str] = []
    for wt in blocks:
        path = Path(wt.get("worktree", "."))
        branch = wt.get("branch", "").replace("refs/heads/", "") or "(detached)"
        shown = display_path(path, repo_dir)
        dirty = len((git(path, "status", "--porcelain") or "").splitlines())
        if branch == "(detached)" and not dirty:
            continue  # prunable audit/baseline checkouts are not continuations
        unpushed = "no-remote"
        if branch != "(detached)" and git(
            path, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}"
        ):
            ahead = git(path, "rev-list", "--count", f"origin/{branch}..HEAD")
            unpushed = ahead if ahead and ahead.isdigit() else "?"
        if dirty or unpushed not in ("0", "no-remote"):
            lines.append(f"{shown} [{branch}] dirty={dirty} unpushed={unpushed}")
        elif unpushed == "no-remote":
            lines.append(f"{shown} [{branch}] dirty={dirty} unpushed=no-remote")
    return lines[:6] or ["(none dirty or unpushed)"]


def pin_lines(repo_dir: Path) -> list[str]:
    """The live engine pin and the newest sealed epoch, read from the pin authority.

    ``config/rules_engines.json`` is the sole machine-readable pin authority, so the index
    reads it instead of carrying the values in prose, where they went stale at every repin.
    A pin that is ahead of the sealed qualification is flagged: a merged repin is not done
    until PB-03, the AF11 decision and both seals have caught up.
    """
    path = repo_dir / "config" / "rules_engines.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        pin = str(config["primary_engine"]["commit"])
        qualification = config["architecture_freeze"]["current_qualification"]
        qualified = str(qualification["engine_commit"])
        epoch = str(qualification["evidence_epoch"]).rsplit("/", 1)[-1]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return ["(config/rules_engines.json: pin or current_qualification unreadable)"]
    lines = [
        f"engine pin {pin[:8]}; current_qualification epoch {epoch} on engine {qualified[:8]}"
        f" and lab {str(qualification.get('lab_commit', '?'))[:8]}"
        f" (freeze_eligible={qualification.get('freeze_eligible', '?')})"
    ]
    if qualified != pin:
        lines.append(
            "PIN AHEAD OF QUALIFICATION: requalify (PB-03 on main, AF11 decision, seals)"
            " per docs/claude/REPIN_RUNBOOK.md"
        )
    return lines


def repo_head_lines(repo_dir: Path) -> list[str]:
    branch = git(repo_dir, "rev-parse", "--abbrev-ref", "HEAD") or "?"
    head = (git(repo_dir, "rev-parse", "HEAD") or "?")[:8]
    dirty = "dirty" if (git(repo_dir, "status", "--porcelain") or "") else "clean"
    main_sha = (
        git(repo_dir, "rev-parse", "--verify", "--quiet", "refs/remotes/origin/main") or ""
    )[:8]
    lines = [
        f"lab HEAD {branch}@{head} ({dirty})" + (f" origin/main={main_sha}" if main_sha else "")
    ]
    for repo in REPOS:
        short = repo.split("/")[1]
        try:
            default = api(f"repos/{repo}").get("default_branch", "main")
            sha = (api(f"repos/{repo}/commits/{default}").get("sha") or "?")[:8]
            pulls = api(f"repos/{repo}/pulls?state=open&per_page=20") or []
        except ApiUnavailable:
            # A session scoped to the Lab cannot read the engine forks; one
            # unreachable sibling must not cost the whole index. The Lab stays
            # fail-closed: its own failure still aborts.
            if repo == LAB:
                raise
            lines.append(f"{short} unavailable (no GitHub access from this session)")
            continue
        lines.append(f"{short} {default}@{sha}")
        for pull in pulls:
            lines.append(
                f"{short} PR #{pull['number']} {pull['head']['ref']} -> {pull['head']['sha'][:8]}"
            )
    return lines[:12]


def lane_issues() -> tuple[int, ...]:
    """The open issues (pull requests excluded), newest first, capped at MAX_LANES.

    A hard-coded list went stale as lanes closed; the open issue set is the live
    lane index. No open issue means no lane: closed issues are never listed.
    """
    issues = api(f"repos/{LAB}/issues?state=open&per_page=50") or []
    numbers = [
        int(i["number"])
        for i in issues
        if isinstance(i, dict) and "number" in i and "pull_request" not in i
    ]
    return tuple(sorted(numbers, reverse=True)[:MAX_LANES])


def lane_lines(numbers: tuple[int, ...]) -> list[str]:
    lines: list[str] = []
    for number in numbers:
        issue = api(f"repos/{LAB}/issues/{number}")
        if not isinstance(issue, dict) or issue.get("state") != "open":
            continue  # an issue closed since the open list was read is not a lane
        comments = api(f"repos/{LAB}/issues/{number}/comments?per_page=100") or []
        markers = [c for c in comments if BATON_MARKER.search(c.get("body") or "")]
        owner, next_action = "?", ""
        for comment in reversed(markers):
            own = OWNER_LINE.search(comment.get("body") or "")
            if own:
                owner = clip(own.group(1).lstrip("* "), 36)
                break
        if owner == "?":
            owner = markers[-1]["user"]["login"] if markers else "?"
        for comment in reversed(markers):
            nxt = NEXT_LINE.search(comment.get("body") or "")
            if nxt:
                next_action = clip(nxt.group(1).lstrip("* "), 80)
                break
        lines.append(
            f"#{number} {clip(issue.get('title', ''), 44)} [{issue.get('state')}] "
            f"owner={owner} next={next_action or '-'}"
        )
    return lines or ["(no open issues)"]


def render(repo_dir: Path, now: str) -> str:
    """The whole HANDOFF.md body, deterministic for fixed git/API/state inputs."""
    lanes = lane_issues()
    sections = [
        ("Engine pin and qualification (config/rules_engines.json)", pin_lines(repo_dir)),
        (
            "Lanes and owners (open issues"
            + ("; baton comments: " + ", ".join(f"#{n}" for n in lanes) if lanes else "")
            + ")",
            lane_lines(lanes),
        ),
        ("Branches and heads", repo_head_lines(repo_dir)),
        ("Local worktrees (dirty or unpushed only)", worktree_lines(repo_dir)),
    ]
    out = [
        f"# Claude handoff \u2014 {now}",
        "",
        "Fresh session: start here instead of a compacted conversation. Operational index, not",
        "Source Authority; regenerate with `python3 scripts/claude_handoff.py`. Git wins.",
        "Know-how: `docs/claude/SESSION_PLAYBOOK.md`; repin procedure: `docs/claude/REPIN_RUNBOOK.md`.",
        "",
    ]
    for title, lines in sections:
        out.append(f"## {title}")
        out.extend(f"- {line}" for line in lines)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo-dir", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=Path("docs/claude/state/HANDOFF.md"))
    parser.add_argument("--now", default=datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"))
    parser.add_argument("--dry-run", action="store_true", help="print, write nothing")
    a = parser.parse_args()
    text = render(a.repo_dir.resolve(), a.now)
    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        raise SystemExit(f"HANDOFF would be {len(lines)} lines; the cap is {MAX_LINES}")
    if a.dry_run:
        print(text, end="")
        return 0
    out = a.out if a.out.is_absolute() else a.repo_dir / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} ({len(lines)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
