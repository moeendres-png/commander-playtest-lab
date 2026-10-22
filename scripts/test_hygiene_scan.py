"""Find tests that can pass without testing anything (#961 Q-1).

Three kinds of test are counted, statically (``ast``), without running a test:

* ``no_assertion``: no ``assert``, no ``pytest.raises``/``warns``/``fail``, no call of an
  assertion helper. The test passes when the code under test returns.
* ``trivial_only``: every assertion is trivial (``is not None``, ``exists()``, bare
  truthiness, ``isinstance`` alone). The test passes for almost any value.
* ``unguarded_loop``: every assertion sits inside a ``for`` loop and one of the loops walks
  a collection that is not a literal (a glob, a parsed file, a query result). The test
  passes when the collection is empty, for example when a directory is moved.

    python scripts/test_hygiene_scan.py            # the counts and the tests
    python scripts/test_hygiene_scan.py --json

A test that really means "must not raise" says so with an assertion on what it returned or
with ``assert_never_raises``-style helpers named ``assert_*``; a loop test asserts that the
collection is not empty before the loop.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

_ASSERT_CALLS = re.compile(
    r"(raises|warns|fail|assertRaises|assertEqual|assertTrue|assertIn|assertIs|assertFalse)$"
)
_ASSERT_HELPER = re.compile(
    r"^(assert|check|verify|expect|ensure|require|must|_assert|_check|_verify|_expect)", re.I
)
GROUPS = ("no_assertion", "trivial_only", "unguarded_loop")


@dataclass
class Hygiene:
    """The tests of each group as ``(path relative to tests/, test name)``."""

    tests: int = 0
    groups: dict[str, list[tuple[str, str]]] = field(
        default_factory=lambda: {name: [] for name in GROUPS}
    )

    def counts(self) -> dict[str, int]:
        return {name: len(found) for name, found in self.groups.items()}


def trivial_kind(node: ast.Assert) -> str | None:
    """Why an assertion proves almost nothing, or None when it is a real check."""
    test = node.test
    if isinstance(test, ast.Constant) and bool(test.value):
        return "const_true"
    if (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
    ):
        return "is_not_none"
    if (
        isinstance(test, ast.Call)
        and isinstance(test.func, ast.Attribute)
        and test.func.attr in {"exists", "is_file", "is_dir"}
    ):
        return "exists"
    if isinstance(test, ast.Name | ast.Attribute):
        return "bare_truthy"
    if isinstance(test, ast.Call) and getattr(test.func, "id", None) == "isinstance":
        return "isinstance_only"
    return None


def _module_literals(tree: ast.Module) -> set[str]:
    """Names bound at module level to a literal collection."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(
            node.value, ast.Tuple | ast.List | ast.Set | ast.Dict
        ):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def _is_static(iterable: ast.expr, literals: set[str]) -> bool:
    if isinstance(iterable, ast.Tuple | ast.List | ast.Set | ast.Dict):
        return True
    if isinstance(iterable, ast.Call):
        name = getattr(iterable.func, "id", "")
        if name == "range":
            return True
        if name in {"zip", "enumerate", "sorted", "list", "tuple", "reversed"}:
            return bool(iterable.args) and all(_is_static(a, literals) for a in iterable.args)
    return isinstance(iterable, ast.Name) and iterable.id in literals


def _walk_tests(tree: ast.Module) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            yield node


def _unguarded_loop(body: Sequence[ast.stmt], literals: set[str], guarded: bool = False) -> bool:
    """True when a loop over a non-literal collection runs with no assertion before it.

    An assertion earlier in the same block, or in a block that encloses it, is the guard
    (``assert items`` before the loop); one inside another statement does not guard the rest.
    """
    for stmt in body:
        if isinstance(stmt, ast.Assert):
            guarded = True
        elif isinstance(stmt, ast.For | ast.AsyncFor):
            if not guarded and not _is_static(stmt.iter, literals):
                return True
            if _unguarded_loop(stmt.body, literals, guarded):
                return True
        else:
            for block in ("body", "orelse", "finalbody", "handlers"):
                children = getattr(stmt, block, None)
                if not isinstance(children, list):
                    continue
                for child in children:
                    inner = child.body if isinstance(child, ast.ExceptHandler) else [child]
                    if _unguarded_loop(inner, literals, guarded):
                        return True
    return False


def classify(node: ast.FunctionDef | ast.AsyncFunctionDef, literals: set[str]) -> str | None:
    """The hygiene group of one test function, or None when it asserts something real."""
    asserts = [n for n in ast.walk(node) if isinstance(n, ast.Assert)]
    calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
    checks = any(_ASSERT_CALLS.search(ast.unparse(c.func)) for c in calls)
    helper = any(
        _ASSERT_HELPER.match(getattr(c.func, "id", None) or getattr(c.func, "attr", "") or "")
        for c in calls
    )
    if not asserts and not checks and not helper:
        return "no_assertion"
    if not asserts or checks or helper:
        return None
    if all(trivial_kind(a) for a in asserts):
        return "trivial_only"
    loops = [n for n in ast.walk(node) if isinstance(n, ast.For | ast.AsyncFor)]
    in_loop = {id(a) for loop in loops for a in ast.walk(loop) if isinstance(a, ast.Assert)}
    if all(id(a) in in_loop for a in asserts) and _unguarded_loop(node.body, literals):
        return "unguarded_loop"
    return None


def scan_source(source: str) -> list[tuple[str, str]]:
    """``(group, test name)`` for every flagged test of one module (used by the tests)."""
    tree = ast.parse(source)
    literals = _module_literals(tree)
    found = []
    for node in _walk_tests(tree):
        group = classify(node, literals)
        if group:
            found.append((group, node.name))
    return found


def scan(root: Path = TESTS) -> Hygiene:
    result = Hygiene()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        literals = _module_literals(tree)
        relative = path.relative_to(root).as_posix()
        for node in _walk_tests(tree):
            result.tests += 1
            group = classify(node, literals)
            if group:
                result.groups[group].append((relative, node.name))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", type=Path, default=TESTS)
    args = parser.parse_args(argv)
    found = scan(args.root)
    if args.json:
        print(json.dumps({"tests": found.tests, "groups": found.groups}, indent=1, sort_keys=True))
    else:
        print(f"{found.tests} test functions")
        for name in GROUPS:
            print(f"{name}: {len(found.groups[name])}")
            for relative, test in found.groups[name]:
                print(f"  {relative}::{test}")
    return 1 if any(found.groups.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
