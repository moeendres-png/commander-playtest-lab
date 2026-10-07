#!/usr/bin/env python3
"""Write the <=80-line cold-start index for a fresh Claude session.

    scripts/claude_handoff.py [--repo-dir .] [--out docs/claude/state/HANDOFF.md]
                              [--repo O/R] [--now 2026-10-06T00:00Z] [--dry-run]

The file is assembled from local git (HEAD, worktrees, dirty/unpushed state),
the GitHub API (`gh api`: open PRs per repo, lane-issue baton comments) and the
`.foundry/*.yaml|*.json` workstream states. It is an operational index, not
Source Authority: Git, tests and GitHub stay canonical, and a fresh session
starts here instead of re-reading a compacted conversation. Only the one output
file is written.
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

import yaml

LAB = "moeendres-png/commander-playtest-lab"
REPOS = (LAB, "moeendres-png/mage", "moeendres-png/forge")
LANE_ISSUES = (441, 479, 561, 572)
MAX_LINES = 80
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
        raise SystemExit(f"gh api {path}: {out.stderr.strip() or out.stdout.strip()}")
    return json.loads(out.stdout or "null")


def git(repo_dir: Path, *args: str) -> str | None:
    out = subprocess.run(
        ["git", "-C", str(repo_dir), *args], capture_output=True, text=True, check=False
    )
    return out.stdout.strip() if out.returncode == 0 else None


def clip(text: str, limit: int) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "\u2026"


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
            lines.append(f"{path} [{branch}] dirty={dirty} unpushed={unpushed}")
        elif unpushed == "no-remote":
            lines.append(f"{path} [{branch}] dirty={dirty} unpushed=no-remote")
    return lines[:6] or ["(none dirty or unpushed)"]


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
        default = api(f"repos/{repo}").get("default_branch", "main")
        sha = (api(f"repos/{repo}/commits/{default}").get("sha") or "?")[:8]
        lines.append(f"{short} {default}@{sha}")
        for pull in api(f"repos/{repo}/pulls?state=open&per_page=20") or []:
            lines.append(
                f"{short} PR #{pull['number']} {pull['head']['ref']} -> {pull['head']['sha'][:8]}"
            )
    return lines[:12]


def load_states(repo_dir: Path) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for path in sorted((repo_dir / ".foundry").glob("*.yaml")) + sorted(
        (repo_dir / ".foundry").glob("*.json")
    ):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, yaml.YAMLError):
            continue
        if isinstance(data, dict) and ("ownership" in data or "workstream" in data):
            data["_path"] = path.name
            states.append(data)
    return states


def _state_recency(repo_dir: Path, state: dict[str, Any]) -> int:
    stamp = git(repo_dir, "log", "-1", "--format=%ct", "--", f".foundry/{state['_path']}")
    return int(stamp) if stamp and stamp.isdigit() else 0


def lane_lines(repo_dir: Path, states: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for number in LANE_ISSUES:
        issue = api(f"repos/{LAB}/issues/{number}")
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
        if not next_action:
            lane_states = [
                s for s in states if s.get("issue") == number or s.get("parent") == number
            ]
            if lane_states:
                best = min(
                    lane_states,
                    key=lambda s: (
                        s.get("status") not in ("ACTIVE", "WAITING", "BLOCKED"),
                        -_state_recency(repo_dir, s),
                        s["_path"],
                    ),
                )
                next_action = clip(best.get("exact_next_action") or "", 80)
        lines.append(
            f"#{number} {clip(issue.get('title', ''), 44)} [{issue.get('state')}] "
            f"owner={owner} next={next_action or '-'}"
        )
    return lines


BOILERPLATE_GATE = re.compile(r"(?i)remain(s)? reserved|freeze decisions? remain|reserved$")


def decision_lines(repo_dir: Path, states: list[dict[str, Any]]) -> list[str]:
    relevant = [
        s
        for s in states
        if s.get("status") in ("ACTIVE", "WAITING", "BLOCKED")
        and (s.get("authority_gates") or s.get("status") in ("WAITING", "BLOCKED"))
    ]
    relevant.sort(
        key=lambda s: (s.get("status") == "ACTIVE", -_state_recency(repo_dir, s), s["_path"])
    )
    lines: list[str] = []
    seen: set[str] = set()
    for state in relevant:
        label = clip(state.get("ownership") or state["_path"], 60)
        gates = [
            g for g in (state.get("authority_gates") or []) if not BOILERPLATE_GATE.search(str(g))
        ]
        if gates:
            entries = [f"{label}: {clip(gate, 100)}" for gate in gates[:2]]
        elif state.get("status") in ("WAITING", "BLOCKED"):
            entries = [
                f"{label} ({state['status']}): {clip(state.get('exact_next_action') or '', 100)}"
            ]
        else:
            entries = []
        for entry in entries:
            if entry not in seen:
                seen.add(entry)
                lines.append(entry)
        if len(lines) >= 6:
            break
    return lines[:6] or ["(none recorded in .foundry state)"]


def render(repo_dir: Path, now: str) -> str:
    """The whole HANDOFF.md body, deterministic for fixed git/API/state inputs."""
    states = load_states(repo_dir)
    sections = [
        (
            "Lanes and owners (baton comments: " + ", ".join(f"#{n}" for n in LANE_ISSUES) + ")",
            lane_lines(repo_dir, states),
        ),
        ("Branches and heads", repo_head_lines(repo_dir)),
        ("Local worktrees (dirty or unpushed only)", worktree_lines(repo_dir)),
        ("Open Coordinator decisions", decision_lines(repo_dir, states)),
    ]
    out = [
        f"# Claude handoff \u2014 {now}",
        "",
        "Fresh session: start here instead of a compacted conversation. Operational index, not",
        "Source Authority; regenerate with `python3 scripts/claude_handoff.py`. Git wins.",
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
