#!/usr/bin/env python3
"""Report local readiness for optional Claude efficiency tooling."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def present(command: str) -> bool:
    return shutil.which(command) is not None


def main() -> int:
    checks = {
        "claude": present("claude"),
        "python": present("python") or present("python3"),
        "uvx_for_serena": present("uvx"),
        "rtk_optional_compression": present("rtk"),
        "npx_for_context7_repomix": present("npx"),
        "project_mcp_config": (ROOT / ".mcp.json").is_file(),
        "serena_project_config": (ROOT / ".serena" / "project.yml").is_file(),
        "claude_project_settings": (ROOT / ".claude" / "settings.json").is_file(),
    }
    print(json.dumps(checks, indent=2, sort_keys=True))
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        print("\nMissing/disabled:", ", ".join(missing))
        print("See docs/agent-policy/CLAUDE_EFFICIENCY_SETUP.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
