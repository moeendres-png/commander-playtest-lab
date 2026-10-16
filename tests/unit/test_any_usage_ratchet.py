"""Ratchet: the number of ``Any`` uses in ``src/commander_lab`` may only go down.

Definition (deterministic, AST only): every ``ast.Name`` with ``id == "Any"`` and
every ``ast.Attribute`` with ``attr == "Any"`` (``typing.Any``) in every ``*.py``
file under ``src/commander_lab``. Import statements are not expression nodes and
are not counted, so each count is one use in an annotation, ``cast`` or alias.

The recorded baseline lives in ``tests/fixtures/any_usage_baseline.json``.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "commander_lab"
BASELINE = ROOT / "tests" / "fixtures" / "any_usage_baseline.json"


def count_any_uses(source_root: Path = SOURCE) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        total = sum(
            1
            for node in ast.walk(tree)
            if (isinstance(node, ast.Name) and node.id == "Any")
            or (isinstance(node, ast.Attribute) and node.attr == "Any")
        )
        if total:
            counts[path.relative_to(ROOT).as_posix()] = total
    return counts


def test_any_usage_does_not_exceed_baseline() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["max_any_uses"]
    observed = sum(count_any_uses().values())
    assert observed <= baseline, (
        f"`Any` uses in src/commander_lab rose to {observed} (baseline {baseline}). "
        "Use a TypedDict, a precise type or `object` at the boundary instead of `Any`."
    )
    assert observed == baseline, (
        f"`Any` uses fell to {observed} (baseline {baseline}). Lower "
        f"tests/fixtures/any_usage_baseline.json `max_any_uses` to {observed} to lock the gain."
    )


def test_counter_counts_names_and_attributes_but_not_imports(tmp_path: Path) -> None:
    module = tmp_path / "sample.py"
    module.write_text(
        "from typing import Any\nimport typing\n"
        "def f(a: Any, b: typing.Any) -> dict[str, Any]: ...\n",
        encoding="utf-8",
    )
    counts: dict[str, int] = {}
    tree = ast.parse(module.read_text(encoding="utf-8"))
    counts["sample"] = sum(
        1
        for node in ast.walk(tree)
        if (isinstance(node, ast.Name) and node.id == "Any")
        or (isinstance(node, ast.Attribute) and node.attr == "Any")
    )
    assert counts["sample"] == 3
