"""B5 (#486): every test file has exactly one required-context owner.

The required ``quality`` context (``ci.yml``) runs the universal pytest suite and
the required ``infrastructure`` context (``production-qualification.yml``) runs
``tests/qualification``. Before B5 the qualification tests ran in both. This guard
derives each context's selection from its workflow command and requires every
test file to be selected by exactly one of them, so no file is run twice and no
file is left without a required owner.
"""

from __future__ import annotations

import shlex
from functools import cache
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
OWNERS = {
    "quality": (".github/workflows/ci.yml", "quality"),
    "infrastructure": (".github/workflows/production-qualification.yml", "infrastructure"),
}


@cache
def _pytest_command(context: str) -> tuple[str, ...]:
    workflow, job = OWNERS[context]
    document = yaml.safe_load((REPO / workflow).read_text(encoding="utf-8"))
    commands = [
        tuple(shlex.split(line.strip()))
        for step in document["jobs"][job]["steps"]
        for line in (step.get("run") or "").splitlines()
        if line.strip().startswith(("pytest", "python -m pytest"))
    ]
    assert len(commands) == 1, f"{context}: expected one pytest command, found {commands}"
    return commands[0]


def selection(command: tuple[str, ...], test_files: list[str]) -> set[str]:
    """The test files a pytest command collects (paths and ``--ignore`` only).

    No argument selects ``testpaths`` (``tests``). Any option this function does
    not model fails the guard instead of being guessed.
    """
    args = list(command[command.index("pytest") + 1 :])
    paths: list[str] = []
    ignored: list[str] = []
    for arg in args:
        if arg in {"-q", "-ra", "-rs"}:
            continue
        if arg.startswith("--ignore="):
            ignored.append(arg.split("=", 1)[1].rstrip("/"))
        elif arg.startswith("-"):
            raise AssertionError(f"unmodelled pytest option {arg!r} in {command}")
        else:
            paths.append(arg.rstrip("/"))
    paths = paths or ["tests"]

    def under(path: str, root: str) -> bool:
        return path == root or path.startswith(root + "/")

    return {
        path
        for path in test_files
        if any(under(path, root) for root in paths)
        and not any(under(path, root) for root in ignored)
    }


@cache
def _test_files() -> list[str]:
    return sorted(
        str(path.relative_to(REPO))
        for path in (REPO / "tests").rglob("test_*.py")
        if "__pycache__" not in path.parts
    )


def test_every_test_file_has_exactly_one_required_owner() -> None:
    files = _test_files()
    selected = {context: selection(_pytest_command(context), files) for context in OWNERS}
    twice = sorted(selected["quality"] & selected["infrastructure"])
    orphan = sorted(set(files) - selected["quality"] - selected["infrastructure"])
    assert not twice, f"run by both required contexts: {twice[:10]} ({len(twice)} files)"
    assert not orphan, f"run by no required context: {orphan}"


def test_infrastructure_owns_the_qualification_tests() -> None:
    files = _test_files()
    qualification = {path for path in files if path.startswith("tests/qualification/")}
    assert qualification
    assert selection(_pytest_command("infrastructure"), files) == qualification
    assert _pytest_command("quality")[-1] == "--ignore=tests/qualification"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (("pytest", "-q"), {"tests/a/test_x.py", "tests/qualification/test_q.py"}),
        (("pytest", "-q", "--ignore=tests/qualification"), {"tests/a/test_x.py"}),
        (("pytest", "-q", "tests/qualification"), {"tests/qualification/test_q.py"}),
    ],
)
def test_the_selection_model(command, expected) -> None:
    files = ["tests/a/test_x.py", "tests/qualification/test_q.py"]
    assert selection(command, files) == expected


def test_an_unmodelled_option_fails_closed() -> None:
    with pytest.raises(AssertionError, match="unmodelled pytest option"):
        selection(("pytest", "-k", "fast"), ["tests/a/test_x.py"])
