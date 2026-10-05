#!/usr/bin/env python3
"""PostToolUse hook: ruff-fix and ruff-format a Python file Claude just edited.

Applies only to *.py files under src/, tests/, scripts/ and .claude/ of this
repository; everything else (evidence JSON, contract data, vendored engines)
is left untouched. Lint findings ruff cannot fix are fed back to Claude as a
short additionalContext, so they are fixed in the same turn instead of after
a red quality job. Missing ruff, or any hook error, never blocks the edit.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCOPES = ("src/", "tests/", "scripts/", ".claude/")


def ruff_command() -> list[str] | None:
    if shutil.which("ruff"):
        return ["ruff"]
    probe = subprocess.run(
        [sys.executable, "-m", "ruff", "--version"], capture_output=True, check=False
    )
    return [sys.executable, "-m", "ruff"] if probe.returncode == 0 else None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    path = Path((payload.get("tool_input") or {}).get("file_path") or "")
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".").resolve()
    if path.suffix != ".py" or not path.is_file():
        return 0
    try:
        relative = path.resolve().relative_to(root).as_posix()
    except ValueError:
        return 0
    if not relative.startswith(SCOPES):
        return 0
    ruff = ruff_command()
    if ruff is None:
        return 0
    subprocess.run(
        [*ruff, "check", "--fix", "--quiet", relative], cwd=root, capture_output=True, check=False
    )
    subprocess.run(
        [*ruff, "format", "--quiet", relative], cwd=root, capture_output=True, check=False
    )
    left = subprocess.run(
        [*ruff, "check", "--output-format", "concise", "--quiet", relative],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    findings = [line for line in left.stdout.splitlines() if line.strip()][:15]
    if findings:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": "ruff findings left after auto-fix in "
                        f"{relative}:\n" + "\n".join(findings),
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
