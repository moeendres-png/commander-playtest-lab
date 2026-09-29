"""Read Git objects only: a candidate must retain the project's operating entrypoints."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

# This policy is loaded from the trusted base, never from the candidate tree.
REQUIRED_FILES = (
    "AGENTS.md",
    "pyproject.toml",
    "requirements/lock.txt",
    "src/commander_lab/__init__.py",
    "tools/project_invariant_audit.py",
    ".github/workflows/ci.yml",
)


def inspect_tree(repo: Path, revision: str) -> dict[str, object]:
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision) is None:
        raise ValueError("an exact full commit SHA is required")

    def git(*args: str) -> bytes:
        try:
            return subprocess.run(
                ["git", "-C", str(repo), *args],
                check=True,
                capture_output=True,
                timeout=30,
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("candidate commit cannot be inspected") from exc

    # Reject tree/blob objects even if ls-tree would otherwise accept a tree SHA.
    git("rev-parse", "--verify", f"{revision}^{{commit}}")
    entries = {}
    for record in git("ls-tree", "-rz", "--full-tree", revision).split(b"\0"):
        if not record:
            continue
        header, name = record.split(b"\t", 1)
        mode, kind, _object_id = header.split()
        entries[name.decode("utf-8", errors="surrogateescape")] = (mode, kind)
    errors = [
        f"required regular file missing or replaced: {path}"
        for path in REQUIRED_FILES
        if entries.get(path) not in {(b"100644", b"blob"), (b"100755", b"blob")}
    ]
    return {"head": revision, "valid": not errors, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        result = inspect_tree(args.repo, args.head)
    except ValueError as exc:
        result = {"valid": False, "errors": [str(exc)]}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
