#!/usr/bin/env python3
"""Fail-open Claude Code hook for optional RTK Bash-output compression."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

RAW_MARKER = "COMMANDER_RAW_EVIDENCE=1"


def main() -> int:
    payload = sys.stdin.buffer.read()
    try:
        event = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0

    command = str((event.get("tool_input") or {}).get("command") or "")
    if RAW_MARKER in command or os.environ.get("COMMANDER_DISABLE_RTK") == "1":
        return 0

    rtk = shutil.which("rtk")
    if rtk is None:
        return 0

    proc = subprocess.run(
        [rtk, "hook", "claude"],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if proc.returncode == 0 and proc.stdout:
        sys.stdout.buffer.write(proc.stdout)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
