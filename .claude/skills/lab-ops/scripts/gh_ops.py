#!/usr/bin/env python3
"""Compact GitHub views for agent sessions: one line per fact, never raw JSON dumps.

    gh_ops.py brief                         one screen (<=25 lines): open PRs in Lab, mage and
                                            forge, running/recent /oc and /bunny runs with the
                                            branch or PR and final-comment link, PB-03 runs, and
                                            the newest sealed epoch
    gh_ops.py status  [--repo O/R] PR...    head, merge state, red/pending checks, open threads
    gh_ops.py queue                         one status line per open PR in Lab, mage and forge
    gh_ops.py threads [--repo O/R] PR       every unresolved thread: comment id, path:line, excerpt
    gh_ops.py wait    [--repo O/R] PR...    block until no check on any head is pending, then status
    gh_ops.py run     [--repo O/R] RUN_ID   block until a workflow run completes; print its jobs
    gh_ops.py errors  [--repo O/R] JOB_ID   the failing lines of one job log (pytest/maven/actions)
    gh_ops.py rerun-cancelled [--repo O/R] [--dry-run] PR...
                                            re-run only jobs that died on infrastructure (runner
                                            never acquired / operation canceled, no failed step)

Uses `gh api` (REST, plus the CCR review-thread route; GraphQL is unavailable in
Claude Code sessions). ``ci-definition-integrity-shadow`` is red by design (CI-02)
and is reported apart, never as this PR's failure.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

DEFAULT_REPO = "moeendres-png/commander-playtest-lab"
BY_DESIGN_RED = {"ci-definition-integrity-shadow"}
OPENCODE_WORKFLOW = "opencode.yml"
PB03_WORKFLOW = "pb03-runtime-qualification.yml"
EPOCH_ROOT = Path("qualification/current-boundary-epochs")
FAILURE = re.compile(
    r"(##\[error\]|^FAILED |^ERROR |\[ERROR\] (?!Tests run:.*Failures: 0)|Tests run:.*(Failures|Errors): [1-9]"
    r"|AssertionError|Traceback|error:|BUILD FAILURE|semantic replay|EARLY_TERMINATION)"
)


def api(path: str, *, raw: bool = False) -> Any:
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise SystemExit(f"gh api {path}: {out.stderr.strip() or out.stdout.strip()}")
    return out.stdout if raw else json.loads(out.stdout or "null")


def checks(repo: str, sha: str) -> tuple[list[str], list[str], list[str]]:
    every = api(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")["check_runs"]
    # One verdict per check name: the newest run, except that a cancelled run (a
    # superseded duplicate) never hides a newer-or-older run that reached a result.
    by_name: dict[str, list[dict[str, Any]]] = {}
    for r in every:
        by_name.setdefault(r["name"], []).append(r)
    runs = []
    for group in by_name.values():
        group.sort(key=lambda r: r["id"], reverse=True)
        decided = [r for r in group if r["conclusion"] != "cancelled"]
        runs.append(decided[0] if decided else group[0])
    pending = sorted(r["name"] for r in runs if r["status"] != "completed")
    red = sorted(
        r["name"]
        for r in runs
        if r["status"] == "completed" and r["conclusion"] not in ("success", "skipped", "neutral")
    )
    return (
        pending,
        [n for n in red if n not in BY_DESIGN_RED],
        [n for n in red if n in BY_DESIGN_RED],
    )


def open_threads(repo: str, pr: int) -> list[dict[str, Any]]:
    threads = api(f"repos/{repo}/pulls/{pr}/ccr/review_threads") or []
    return [t for t in threads if not t.get("resolved")]


def status_line(repo: str, pr: int) -> tuple[str, bool]:
    p = api(f"repos/{repo}/pulls/{pr}")
    sha = p["head"]["sha"]
    if p.get("merged"):
        return f"#{pr} MERGED {p.get('merge_commit_sha', '')[:8]}", True
    if p["state"] != "open":
        return f"#{pr} {p['state'].upper()}", True
    pending, red, by_design = checks(repo, sha)
    threads = open_threads(repo, pr)
    auto = "auto-merge" if p.get("auto_merge") else ""
    parts = [
        f"#{pr} {sha[:8]} {p['mergeable_state']} {auto}".rstrip(),
        f"red={','.join(red) or '-'}",
        f"pending={len(pending)}" + (f"({','.join(pending[:4])})" if pending else ""),
        f"open_threads={len(threads)}",
    ]
    if by_design:
        parts.append("shadow=red-by-design")
    ready = (
        not pending and not red and not threads and p["mergeable_state"] in ("clean", "unstable")
    )
    if ready:
        parts.append("READY")
    return " ".join(parts), not pending


def cmd_status(a: argparse.Namespace) -> None:
    for pr in a.prs:
        print(status_line(a.repo, pr)[0])


QUEUE_REPOS = (
    "moeendres-png/commander-playtest-lab",
    "moeendres-png/mage",
    "moeendres-png/forge",
)


def cmd_queue(a: argparse.Namespace) -> None:
    """One status line per open PR across the Lab and both engine forks."""
    for repo in QUEUE_REPOS:
        for p in api(f"repos/{repo}/pulls?state=open&per_page=50"):
            line = status_line(repo, p["number"])[0]
            draft = " draft" if p.get("draft") else ""
            print(f"{repo.split('/')[1]}{draft} {line} :: {p['title'][:60]}")


def cmd_threads(a: argparse.Namespace) -> None:
    for t in open_threads(a.repo, a.prs[0]):
        first = t["comment_ids"][0]
        body = api(f"repos/{a.repo}/pulls/comments/{first}")["body"]
        title = re.sub(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)|\*\*", "", body).strip().splitlines()[0][:160]
        last = t["comment_ids"][-1]
        print(
            f"{first} last={last} {t.get('path')}:{t.get('line')} outdated={t.get('outdated')} :: {title}"
        )


def cmd_wait(a: argparse.Namespace) -> None:
    deadline = time.time() + a.timeout
    while True:
        lines = [status_line(a.repo, pr) for pr in a.prs]
        if all(done for _, done in lines) or time.time() > deadline:
            print("\n".join(line for line, _ in lines))
            return
        time.sleep(a.interval)


def cmd_run(a: argparse.Namespace) -> None:
    deadline = time.time() + a.timeout
    while True:
        run = api(f"repos/{a.repo}/actions/runs/{a.prs[0]}")
        if run["status"] == "completed" or time.time() > deadline:
            break
        time.sleep(a.interval)
    print(
        f"run {run['id']} {run['name']} {run['head_sha'][:8]} {run['status']} {run['conclusion']}"
    )
    for job in api(f"repos/{a.repo}/actions/runs/{a.prs[0]}/jobs?per_page=100")["jobs"]:
        print(f"  job {job['id']} {job['name']}: {job['conclusion'] or job['status']}")


def cmd_errors(a: argparse.Namespace) -> None:
    log = api(f"repos/{a.repo}/actions/jobs/{a.prs[0]}/logs", raw=True)
    lines = [re.sub(r"^\S+Z ", "", line) for line in log.splitlines()]
    hits = [i for i, line in enumerate(lines) if FAILURE.search(line)]
    shown: set[int] = set()
    for i in hits[: a.limit]:
        for j in range(max(0, i - a.context), min(len(lines), i + a.context + 1)):
            if j not in shown:
                shown.add(j)
                print(lines[j][:300])
    if not hits:
        print("(no failure lines matched; last 15 lines)")
        print("\n".join(lines[-15:]))


INFRA_CANCEL = re.compile(
    r"not acquired by Runner|The operation was canceled|runner has received a shutdown signal"
    r"|lost communication with the server"
)


def infra_cancelled(repo: str, run: dict[str, Any]) -> bool:
    """True only for a job that died on infrastructure, never on a test or step failure."""
    job = api(f"repos/{repo}/actions/jobs/{run['id']}")
    if any(step.get("conclusion") == "failure" for step in job.get("steps") or []):
        return False
    notes = api(f"repos/{repo}/check-runs/{run['id']}/annotations") or []
    return any(
        n.get("annotation_level") == "failure" and INFRA_CANCEL.search(n.get("message", ""))
        for n in notes
    )


def cmd_rerun_cancelled(a: argparse.Namespace) -> None:
    for pr in a.prs:
        sha = api(f"repos/{a.repo}/pulls/{pr}")["head"]["sha"]
        every = api(f"repos/{a.repo}/commits/{sha}/check-runs?per_page=100")["check_runs"]
        by_name: dict[str, list[dict[str, Any]]] = {}
        for r in every:
            by_name.setdefault(r["name"], []).append(r)
        runs: dict[int, list[str]] = {}
        for name, group in sorted(by_name.items()):
            group.sort(key=lambda r: r["id"], reverse=True)
            newest = group[0]
            if name in BY_DESIGN_RED or newest["status"] != "completed":
                continue
            if any(r["conclusion"] in ("success", "skipped", "neutral") for r in group):
                continue
            if newest["conclusion"] not in ("cancelled", "failure"):
                continue
            if not infra_cancelled(a.repo, newest):
                print(f"#{pr} {name}: {newest['conclusion']} is not an infrastructure abort; left")
                continue
            run_id = api(f"repos/{a.repo}/actions/jobs/{newest['id']}")["run_id"]
            runs.setdefault(run_id, []).append(name)
        for run_id, names in runs.items():
            state = api(f"repos/{a.repo}/actions/runs/{run_id}")["status"]
            if state != "completed":
                print(f"#{pr} run {run_id} still {state}; skip ({','.join(names)})")
                continue
            if a.dry_run:
                print(f"#{pr} would re-run run {run_id}: {','.join(names)}")
                continue
            out = subprocess.run(
                [
                    "gh",
                    "api",
                    "-X",
                    "POST",
                    f"repos/{a.repo}/actions/runs/{run_id}/rerun-failed-jobs",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            verdict = "re-run" if out.returncode == 0 else f"FAILED {out.stderr.strip()[:120]}"
            print(f"#{pr} run {run_id} {verdict}: {','.join(names)}")
        if not runs:
            print(f"#{pr} {sha[:8]}: no infrastructure-aborted job")


def _thread_count(repo: str, pr: int) -> int | None:
    """Open review threads, or None when the CCR route is not reachable here."""
    try:
        return len(open_threads(repo, pr))
    except SystemExit:
        return None


def pr_brief_line(repo: str, p: dict[str, Any]) -> str:
    """One line for one open PR: head, CI verdict, open threads, title."""
    sha = p["head"]["sha"]
    pending, red, by_design = checks(repo, sha)
    threads = _thread_count(repo, p["number"])
    parts = [
        f"{repo.split('/')[1]} #{p['number']}{' draft' if p.get('draft') else ''}",
        p["head"]["ref"],
        sha[:8],
        p.get("mergeable_state") or "unknown",
        f"red={','.join(red) or '-'}",
        f"pending={len(pending)}",
        f"threads={'?' if threads is None else threads}",
    ]
    if by_design:
        parts.append("shadow=red-by-design")
    return " ".join(parts) + f" :: {p['title'][:44]}"


def _run_jobs(repo: str, run_id: int) -> list[dict[str, Any]]:
    return api(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=50")["jobs"]


def run_lane(repo: str, run: dict[str, Any]) -> str:
    """`oc` or `bunny` by which job of the opencode workflow actually ran."""
    names = [
        j["name"]
        for j in _run_jobs(repo, run["id"])
        if not (j.get("status") == "completed" and j.get("conclusion") == "skipped")
    ]
    return "bunny" if any("bunny" in name for name in names) else "oc"


def _comment_for_run(comments: list[dict[str, Any]], run_id: int) -> dict[str, Any] | None:
    needle = f"/actions/runs/{run_id}"
    for c in comments:
        if needle in (c.get("body") or ""):
            return c
    return None


def _issue_from_comment(comment: dict[str, Any]) -> int | None:
    m = re.search(r"/issues/(\d+)$", comment.get("issue_url") or "")
    return int(m.group(1)) if m else None


def _title_index(repo: str) -> dict[str, tuple[int, bool]]:
    """display_title (the issue/PR title) -> (number, is_pull_request)."""
    index: dict[str, tuple[int, bool]] = {}
    for item in api(f"repos/{repo}/issues?state=all&per_page=100") or []:
        index.setdefault(item["title"], (item["number"], "pull_request" in item))
    return index


def _issue_branch(repo: str, issue: int, cache: dict[int, str | None]) -> str | None:
    if issue not in cache:
        refs = api(f"repos/{repo}/git/matching-refs/heads/opencode/issue{issue}-") or []
        names = sorted(r["ref"].removeprefix("refs/heads/") for r in refs)
        cache[issue] = names[-1] if names else None
    return cache[issue]


def cmd_brief(a: argparse.Namespace) -> None:
    """One screen across every lane, assembled from the API and the local epoch tree."""
    for repo in QUEUE_REPOS:
        for p in api(f"repos/{repo}/pulls?state=open&per_page=50") or []:
            print(pr_brief_line(repo, p))

    lab = a.repo
    runs = (
        api(
            f"repos/{lab}/actions/workflows/{OPENCODE_WORKFLOW}/runs?per_page=15&event=issue_comment"
        )
        or {}
    ).get("workflow_runs", [])
    runs = [
        r for r in runs if not (r.get("status") == "completed" and r.get("conclusion") == "skipped")
    ][:4]
    comments: list[dict[str, Any]] = []
    if runs:
        comments = (
            api(f"repos/{lab}/issues/comments?sort=created&direction=desc&per_page=100") or []
        )
    titles: dict[str, tuple[int, bool]] = {}
    branches: dict[int, str | None] = {}
    for run in runs:
        comment = _comment_for_run(comments, run["id"])
        issue = _issue_from_comment(comment) if comment else None
        found = None
        if issue is None:
            titles = titles or _title_index(lab)
            found = titles.get(run.get("display_title", ""))
            issue = found[0] if found else None
        produced = f"PR #{issue}" if found and found[1] else f"issue #{issue}" if issue else "-"
        if comment:
            m = re.search(r"Created PR #(\d+)", comment.get("body") or "")
            if m:
                produced = f"PR #{m.group(1)}"
            elif issue:
                branch = _issue_branch(lab, issue, branches)
                produced = branch or produced
        state = "running" if run["status"] != "completed" else str(run.get("conclusion"))
        link = (comment or run).get("html_url", run["html_url"])
        print(f"{run_lane(lab, run)} run {run['id']} {state} {produced} -> {link}")

    pb03 = (api(f"repos/{lab}/actions/workflows/{PB03_WORKFLOW}/runs?per_page=5") or {}).get(
        "workflow_runs", []
    )
    active = [r for r in pb03 if r["status"] != "completed"]
    if active:
        for r in active:
            print(f"pb03 run {r['id']} {r['status']} {r['head_branch']} -> {r['html_url']}")
    elif pb03:
        r = pb03[0]
        print(
            f"pb03 none running; last {r['conclusion']} {r['created_at'][:16]} -> {r['html_url']}"
        )

    print(f"epoch {newest_epoch(Path(a.lab))}")


def newest_epoch(lab: Path) -> str:
    """Newest sealed epoch id by EPOCH_IDENTITY.created_utc, from the local checkout."""
    best: tuple[str, str] | None = None
    for identity in sorted((lab / EPOCH_ROOT).glob("*/EPOCH_IDENTITY.json")):
        try:
            data = json.loads(identity.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        created = str(data.get("created_utc") or "")
        if not created:
            continue
        if best is None or created > best[0]:
            best = (created, str(data.get("epoch_id") or identity.parent.name))
    if best is None:
        return "unavailable (no local EPOCH_IDENTITY.json; run in a Lab checkout)"
    return f"{best[1]} sealed {best[0][:16]}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "command",
        choices=["brief", "status", "queue", "threads", "wait", "run", "errors", "rerun-cancelled"],
    )
    parser.add_argument("prs", nargs="*", type=int, help="PR numbers, or a run/job id")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--lab", default=".", help="Lab checkout root for the epoch tree")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--timeout", type=int, default=7000)
    parser.add_argument("--context", type=int, default=2)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--dry-run", action="store_true")
    a = parser.parse_args()
    if a.command not in ("brief", "queue") and not a.prs:
        parser.error(f"{a.command} needs at least one PR, run or job id")
    {
        "brief": cmd_brief,
        "status": cmd_status,
        "queue": cmd_queue,
        "threads": cmd_threads,
        "wait": cmd_wait,
        "run": cmd_run,
        "errors": cmd_errors,
        "rerun-cancelled": cmd_rerun_cancelled,
    }[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
