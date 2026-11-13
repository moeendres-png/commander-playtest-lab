"""Every command line of the "Alles importieren" doc section parses with the real parser."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from commander_lab.studio.__main__ import _parser

DOC = Path(__file__).resolve().parents[2] / "docs" / "STUDIO_DECKBUILDER.md"
PREFIX = re.compile(r"^(?:\S*python3?(?:\.exe)?) -m commander_lab\.studio ")
SUBCOMMANDS = {"import-all", "import-signals", "import-tagger-roles", "serve"}


def _section() -> str:
    text = DOC.read_text(encoding="utf-8")
    start = text.index("### Alles importieren")
    return text[start : text.index("\n## ", start + 5)]


def _commands() -> list[list[str]]:
    found: list[str] = []
    section = _section()
    for block in re.findall(r"```(?:powershell|sh|bash)?\n(.*?)```", section, re.S):
        joined = re.sub(r"[`\\]\s*\n\s*", " ", block)
        found += [line.strip() for line in joined.splitlines() if PREFIX.match(line.strip())]
    found += re.findall(r"`(python3? -m commander_lab\.studio [^`]+)`", section)
    commands: list[list[str]] = []
    for line in found:
        text = re.sub(r"--expect-pool <[^>]*>", "--expect-pool 1", PREFIX.sub("", line))
        text = re.sub(r"<[^>]*>", "X", text)
        commands.append([t.strip('"') for t in shlex.split(text, posix=False)])
    return commands


def test_the_doc_documents_commands() -> None:
    commands = _commands()
    assert commands
    assert any("import-all" in tokens for tokens in commands)
    assert any(tokens[0] == "--data" for tokens in commands)  # --data before the subcommand


@pytest.mark.parametrize("tokens", _commands(), ids=lambda tokens: " ".join(tokens)[:60])
def test_documented_command_parses(tokens: list[str]) -> None:
    parsed = _parser().parse_args(tokens)
    assert parsed.command in SUBCOMMANDS | {"import-lab-deck"}
    assert parsed.command in tokens


def test_data_after_the_subcommand_is_not_accepted() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(["import-all", "--commander", "x", "--inventory", "a", "--data", "d"])
