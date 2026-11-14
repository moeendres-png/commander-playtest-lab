"""B5 (#486): every test file has exactly one required-context owner.

The required ``quality`` context (``ci.yml``) is a gate over the ``tests`` matrix (the universal
pytest suite, split into slots by ``tests/pytest_shards.py``) and the ``packaging`` job (the
packaging test); the required ``infrastructure`` context (``production-qualification.yml``) runs
``tests/qualification``. Before B5 the qualification tests ran in both. This guard
derives each context's selection from its workflow command and requires every
test file to be selected by exactly one of them, so no file is run twice and no
file is left without a required owner.
"""

from __future__ import annotations

import importlib.util
import shlex
from functools import cache
from pathlib import Path

import pytest
import yaml

from tests import pytest_shards

REPO = Path(__file__).resolve().parents[2]
OWNERS = {
    "quality": (".github/workflows/ci.yml", "quality"),
    "infrastructure": (".github/workflows/production-qualification.yml", "infrastructure"),
}


def _jobs(workflow: str) -> dict:
    return yaml.safe_load((REPO / workflow).read_text(encoding="utf-8"))["jobs"]


@cache
def _pytest_commands(workflow: str, job: str) -> list[tuple[str, ...]]:
    return [
        tuple(shlex.split(line.strip()))
        for step in _jobs(workflow)[job]["steps"]
        for line in (step.get("run") or "").splitlines()
        if line.strip().startswith(("pytest", "python -m pytest"))
    ]


@cache
def _pytest_command(context: str) -> tuple[str, ...]:
    workflow, job = OWNERS[context]
    commands = _pytest_commands(workflow, job)
    assert len(commands) == 1, f"{context}: expected one pytest command, found {commands}"
    return commands[0]


def _matrix_count() -> int:
    """The number of slots the ``changes`` job publishes for a full run."""
    spec = importlib.util.spec_from_file_location(
        "ci_change_scope", REPO / "scripts" / "ci_change_scope.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return int(module.MATRIX_COUNT)


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
        # Reporting only: they never change which tests are collected. ``--shards=N``
        # splits the same selection over N processes (test_every_shard_selection_...).
        if arg.startswith(("--durations=", "--junitxml=", "--shards=", "--shard-weights=")):
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


def _quality_slots(files: list[str]) -> list[set[str]]:
    """The files of every ``tests`` matrix slot of a full run, as the workflow computes them."""
    count = _matrix_count()
    return [
        set(pytest_shards.matrix_files(REPO, index, count, "all")) for index in range(1, count + 1)
    ]


def _quality_selection(files: list[str]) -> set[str]:
    packaging = _pytest_commands(*OWNERS["quality"][:1], "packaging")
    assert len(packaging) == 1
    owned = selection(packaging[0], files)
    assert owned == {pytest_shards.PACKAGING_TEST}
    return set().union(*_quality_slots(files)) | owned


def test_every_test_file_has_exactly_one_required_owner() -> None:
    files = _test_files()
    selected = {
        "quality": _quality_selection(files),
        "infrastructure": selection(_pytest_command("infrastructure"), files),
    }
    twice = sorted(selected["quality"] & selected["infrastructure"])
    orphan = sorted(set(files) - selected["quality"] - selected["infrastructure"])
    assert not twice, f"run by both required contexts: {twice[:10]} ({len(twice)} files)"
    assert not orphan, f"run by no required context: {orphan}"


def test_infrastructure_owns_the_qualification_tests() -> None:
    files = _test_files()
    qualification = {path for path in files if path.startswith("tests/qualification/")}
    assert qualification
    assert selection(_pytest_command("infrastructure"), files) == qualification
    assert not any(path.startswith("tests/qualification/") for path in _quality_selection(files))


def test_the_matrix_slots_select_each_quality_file_exactly_once() -> None:
    files = _test_files()
    slots = _quality_slots(files)
    assert len(slots) >= 2
    assert sum(len(slot) for slot in slots) == len(set().union(*slots)), "a file is in two slots"
    expected = {path for path in files if not path.startswith("tests/qualification/")}
    assert set().union(*slots) == expected - {pytest_shards.PACKAGING_TEST}


def test_the_tests_job_runs_its_slot_through_the_in_job_shards() -> None:
    commands = [
        command
        for step in _jobs(OWNERS["quality"][0])["tests"]["steps"]
        for line in (step.get("run") or "").splitlines()
        if (command := line.strip()).startswith("pytest")
    ]
    assert len(commands) == 1 and "--shards=4" in commands[0]
    assert '"${files[@]}"' in commands[0]
    assert "tests/qualification" not in commands[0]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (("pytest", "-q"), {"tests/a/test_x.py", "tests/qualification/test_q.py"}),
        (("pytest", "-q", "--ignore=tests/qualification"), {"tests/a/test_x.py"}),
        (("pytest", "-q", "tests/qualification"), {"tests/qualification/test_q.py"}),
        (
            (
                "pytest",
                "-q",
                "--durations=50",
                "--junitxml=out.xml",
                "--ignore=tests/qualification",
            ),
            {"tests/a/test_x.py"},
        ),
    ],
)
def test_the_selection_model(command, expected) -> None:
    files = ["tests/a/test_x.py", "tests/qualification/test_q.py"]
    assert selection(command, files) == expected


def test_an_unmodelled_option_fails_closed() -> None:
    with pytest.raises(AssertionError, match="unmodelled pytest option"):
        selection(("pytest", "-k", "fast"), ["tests/a/test_x.py"])


def test_in_slot_shards_of_every_matrix_slot_are_disjoint_and_cover_the_slot() -> None:
    """The ``tests`` job splits each slot over ``--shards=N`` pytest processes; no file may run twice."""
    command = next(
        line.strip()
        for step in _jobs(OWNERS["quality"][0])["tests"]["steps"]
        for line in (step.get("run") or "").splitlines()
        if line.strip().startswith("pytest")
    )
    count = int(
        next(part for part in shlex.split(command) if part.startswith("--shards=")).split("=")[1]
    )
    weights = pytest_shards.load_weights(pytest_shards.WEIGHTS_PATH)
    for index in range(1, _matrix_count() + 1):
        slot = pytest_shards.matrix_files(REPO, index, _matrix_count(), "all", weights)
        selection = pytest_shards.parse_arguments(["-q", *slot], ("tests",))
        plan = pytest_shards.plan_for(pytest_shards.selected_files(weights, REPO, selection), count)
        assert plan is not None
        commands = [
            pytest_shards.shard_arguments(selection, plan, shard) for shard in range(len(plan))
        ]
        listed = [[item for item in args if item.endswith(".py")] for args in commands]
        flat = [name for shard in listed for name in shard]
        assert sorted(flat) == sorted(slot), f"slot {index}: shards do not partition the slot"
        assert all(not item.startswith("--ignore") for args in commands for item in args)
