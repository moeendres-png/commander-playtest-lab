"""Guard: runtime ``assert`` statements vanish under ``python -O``; src/ must not use them."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "commander_lab"

# Files still pending cleanup by another change; the coordinator empties this after merge.
ALLOWLIST = {
    "engine/rules/full_game.py",
    "engine/rules/full_game_comparison.py",
}


def test_no_runtime_asserts_in_src() -> None:
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel in ALLOWLIST:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(
            f"{rel}:{node.lineno}" for node in ast.walk(tree) if isinstance(node, ast.Assert)
        )
    assert not offenders, "runtime assert statements in src/ (use explicit raises): " + ", ".join(
        offenders
    )
