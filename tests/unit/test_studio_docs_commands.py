"""Every command line in the setup section of the Studio doc parses with the real parser."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from commander_lab.studio.__main__ import _parser

DOC = Path(__file__).resolve().parents[2] / "docs" / "STUDIO_DECKBUILDER.md"
PREFIX = re.compile(r"^python3? -m commander_lab\.studio ")


def _section() -> str:
    text = DOC.read_text(encoding="utf-8")
    start = text.index("## Erste Einrichtung")
    return text[start : text.index("\n## ", start + 5)]


def _commands() -> list[list[str]]:
    found: list[list[str]] = []
    section = _section()
    for block in re.findall(r"```(?:powershell|sh|bash)?\n(.*?)```", section, re.S):
        joined = re.sub(r"[`\\]\s*\n\s*", " ", block)
        for line in joined.splitlines():
            if PREFIX.match(line.strip()):
                found.append(line.strip())
    for inline in re.findall(r"`(python3? -m commander_lab\.studio [^`]+)`", section):
        found.append(inline)
    commands = []
    for line in found:
        tokens = [t.strip('"') for t in shlex.split(PREFIX.sub("", line), posix=False)]
        commands.append(tokens)
    return commands


def test_the_doc_documents_commands() -> None:
    commands = _commands()
    assert len(commands) >= 4
    assert any(tokens[0] == "--data" for tokens in commands)  # --data before the subcommand
    assert any("import-all" in tokens for tokens in commands)


@pytest.mark.parametrize("tokens", _commands(), ids=lambda tokens: " ".join(tokens)[:60])
def test_documented_command_parses(tokens: list[str]) -> None:
    _parser().parse_args(tokens)


def test_data_after_the_subcommand_is_not_accepted() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(["import-all", "--collection", "a", "--scryfall", "b",
                              "--research", "c", "--commander", "x", "--data", "d"])  # fmt: skip
