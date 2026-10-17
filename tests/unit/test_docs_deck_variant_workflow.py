"""Keep docs/DECK_VARIANT_WORKFLOW.md true (#853).

Parses the fenced bash blocks of the workflow page and asserts that every
``scripts/<name>.py`` it invokes exists and that every ``--flag`` it uses
appears in that script's ``--help`` output. No JVM, no network.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "DECK_VARIANT_WORKFLOW.md"

#: ``python scripts/<name>.py`` invocations inside fenced bash blocks.
_SCRIPT_RE = re.compile(r"^python\s+(scripts/\S+\.py)\b(.*)$")
#: ``--flag`` or ``--flag=value`` tokens.
_FLAG_RE = re.compile(r"--([a-zA-Z][a-zA-Z0-9_-]*)")


def _bash_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    in_block = False
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "```bash":
            in_block = True
            current = []
        elif stripped == "```" and in_block:
            in_block = False
            blocks.append("\n".join(current))
        elif in_block:
            current.append(line)
    return blocks


def _invocations() -> list[tuple[str, str | None, list[str]]]:
    """(script path, subcommand or None, flags) for every invocation."""
    found: list[tuple[str, str | None, list[str]]] = []
    for block in _bash_blocks(PAGE.read_text(encoding="utf-8")):
        # Join backslash continuations before matching.
        joined = re.sub(r"\\\n\s*", " ", block)
        for line in joined.splitlines():
            match = _SCRIPT_RE.match(line.strip())
            if not match:
                continue
            script, rest = match.group(1), match.group(2)
            tokens = rest.split()
            # First non-flag token is the subcommand (e.g. "run", "compare").
            subcommand = next((t for t in tokens if not t.startswith("-")), None)
            flags = sorted(set(_FLAG_RE.findall(rest)))
            found.append((script, subcommand, [f"--{flag}" for flag in flags]))
    return found


def _help_text(script: str, subcommand: str | None) -> str:
    args = [sys.executable, script]
    if subcommand:
        args.append(subcommand)
    args.append("--help")
    proc = subprocess.run(
        args,
        cwd=ROOT,
        env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"{script} --help failed: {proc.stderr[:500]}"
    return proc.stdout


def test_workflow_page_scripts_and_flags_exist() -> None:
    invocations = _invocations()
    assert invocations, "no script invocations found in the workflow page"
    for script, subcommand, flags in invocations:
        assert (ROOT / script).is_file(), f"script missing: {script}"
        help_text = _help_text(script, subcommand)
        where = f"{script} {subcommand}" if subcommand else script
        for flag in flags:
            assert flag in help_text, f"{where}: flag {flag} not in --help output"
