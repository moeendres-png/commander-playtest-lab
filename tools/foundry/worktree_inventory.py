"""Machine-readable worktree/session inventory.

Lists every worktree known to the current repository with branch, HEAD,
clean/dirty state, and ownership (read from .foundry/WORKSTREAM_STATE.yaml
when present, else UNKNOWN). Read-only: never kills processes, never deletes
worktrees.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def _run(args: list[str], cwd: str) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def _git_in(path: str, args: list[str]) -> str | None:
    try:
        return _run(["-C", path, *args], ".").strip()
    except RuntimeError:
        return None


def _ownership(path: str) -> str:
    state = Path(path) / ".foundry" / "WORKSTREAM_STATE.yaml"
    if not state.exists():
        return "UNKNOWN"
    try:
        for line in state.read_text(encoding="utf-8").splitlines():
            if line.startswith("ownership:"):
                return line.split(":", 1)[1].strip() or "UNKNOWN"
    except OSError:
        return "UNKNOWN"
    return "UNKNOWN"


def inventory(workdir: str = ".") -> list[dict[str, str | bool | None]]:
    raw = _run(["worktree", "list", "--porcelain"], workdir)
    entries: list[dict[str, str | bool | None]] = []
    current: dict[str, str] = {}
    for line in raw.splitlines():
        if line.startswith("worktree "):
            if current:
                entries.append(_describe(current))
            current = {"path": line[len("worktree ") :]}
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch ") :]
        elif line == "bare":
            current["bare"] = "true"
        elif line == "detached":
            current["detached"] = "true"
    if current:
        entries.append(_describe(current))
    return entries


def _describe(block: dict[str, str]) -> dict[str, str | bool | None]:
    path = block["path"]
    branch = block.get("branch", "(detached)" if block.get("detached") else None)
    if branch is not None and branch.startswith("refs/heads/"):
        branch = branch[len("refs/heads/") :]
    head = block.get("head") or _git_in(path, ["rev-parse", "HEAD"])
    status = _git_in(path, ["status", "--porcelain"])
    return {
        "path": path,
        "branch": branch,
        "head": head,
        "clean": (status == "") if status is not None else None,
        "ownership": _ownership(path),
        "bare": bool(block.get("bare")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit worktree inventory as JSON.")
    parser.add_argument("--workdir", default=".", help="Repository to inspect.")
    parser.add_argument("--output", default=None, help="Write JSON here instead of stdout.")
    args = parser.parse_args(argv)
    payload = {"worktrees": inventory(args.workdir)}
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
