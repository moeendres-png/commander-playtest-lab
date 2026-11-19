"""B5 (#486): every test file has exactly one required-context owner.

The required ``quality`` context (``ci.yml``) is a gate over the ``tests`` matrix (the universal
pytest suite, split into slots by ``tests/pytest_shards.py``) and the two packaging jobs (the
packaging test, split into two fixed halves by test id); the required ``infrastructure`` context
(``production-qualification.yml``) runs ``tests/qualification``. Before B5 the qualification tests ran in both. This guard
derives each context's selection from its workflow command and requires every
test file to be selected by exactly one of them, so no file is run twice and no
file is left without a required owner.
"""

from __future__ import annotations

import importlib.util
import shlex
import subprocess
import sys
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
# The jobs that share tests/unit/test_packaging_smoke.py, each running one fixed half (#1570).
PACKAGING_JOBS = ("packaging-1", "packaging-2")


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
    """The test files a pytest command collects (paths, test ids and ``--ignore`` only).

    No argument selects ``testpaths`` (``tests``). A test id ``file::name`` selects (part of)
    its file; which part is proven per test by test_the_packaging_halves_partition_...
    Any option this function does not model fails the guard instead of being guessed.
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
            paths.append(arg.split("::", 1)[0].rstrip("/"))
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


def _packaging_command(job: str) -> tuple[str, ...]:
    commands = _pytest_commands(OWNERS["quality"][0], job)
    assert len(commands) == 1, f"{job}: expected one pytest command, found {commands}"
    return commands[0]


def _quality_selection(files: list[str]) -> set[str]:
    jobs = _jobs(OWNERS["quality"][0])
    assert sorted(name for name in jobs if name.startswith("packaging")) == list(PACKAGING_JOBS)
    assert set(PACKAGING_JOBS) <= set(jobs["quality"]["needs"])
    owned: set[str] = set()
    for job in PACKAGING_JOBS:
        part = selection(_packaging_command(job), files)
        assert part == {pytest_shards.PACKAGING_TEST}, job
        owned |= part
    return set().union(*_quality_slots(files)) | owned


def _collected_packaging_ids() -> list[str]:
    """The test ids pytest itself collects from the packaging module (parametrize included)."""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            pytest_shards.PACKAGING_TEST,
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout[-2000:] + completed.stderr[-2000:]
    ids = [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.startswith(pytest_shards.PACKAGING_TEST + "::")
    ]
    assert ids, completed.stdout[-2000:]
    return ids


def packaging_half(command: tuple[str, ...], collected: list[str]) -> list[str]:
    """The test ids one packaging job runs; a bare file path stands for every collected id."""
    selected: list[str] = []
    for arg in command[command.index("pytest") + 1 :]:
        if arg.startswith("-"):
            continue
        if arg == pytest_shards.PACKAGING_TEST:
            selected.extend(collected)
        elif arg.startswith(pytest_shards.PACKAGING_TEST + "::"):
            selected.append(arg)
        else:
            raise AssertionError(f"a packaging job selects {arg!r} outside the packaging module")
    return selected


def assert_partition(halves: list[list[str]], collected: list[str]) -> None:
    """The halves are disjoint, repeat nothing, and together are exactly the collected tests."""
    flat = [test_id for half in halves for test_id in half]
    repeated = sorted({test_id for test_id in flat if flat.count(test_id) > 1})
    assert not repeated, f"run twice: {repeated}"
    assert all(halves), "an empty half"
    missing = sorted(set(collected) - set(flat))
    unknown = sorted(set(flat) - set(collected))
    assert not missing, f"collected but run by no packaging half: {missing}"
    assert not unknown, f"selected but not collected (renamed or removed?): {unknown}"


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


def test_the_packaging_halves_partition_the_packaging_tests() -> None:
    """#1570: each packaging test runs in exactly one of the two packaging jobs.

    A new test that is in neither half, a test in both halves, or a renamed test fails here.
    """
    collected = _collected_packaging_ids()
    halves = [packaging_half(_packaging_command(job), collected) for job in PACKAGING_JOBS]
    assert_partition(halves, collected)


@pytest.mark.parametrize(
    ("halves", "message"),
    [
        ([["m::a", "m::b"], ["m::c"]], None),
        ([["m::a"], ["m::c"]], "run by no packaging half"),
        ([["m::a", "m::b"], ["m::b", "m::c"]], "run twice"),
        ([["m::a", "m::a", "m::b"], ["m::c"]], "run twice"),
        ([["m::a", "m::b", "m::c"], []], "an empty half"),
        ([["m::a", "m::b"], ["m::c", "m::d"]], "not collected"),
    ],
)
def test_the_partition_check_model(halves: list[list[str]], message: str | None) -> None:
    collected = ["m::a", "m::b", "m::c"]
    if message is None:
        assert_partition(halves, collected)
    else:
        with pytest.raises(AssertionError, match=message):
            assert_partition(halves, collected)


def test_a_bare_packaging_file_in_a_half_stands_for_every_test() -> None:
    module = pytest_shards.PACKAGING_TEST
    collected = [f"{module}::test_a", f"{module}::test_b"]
    whole = packaging_half(("pytest", "-q", module), collected)
    assert whole == collected
    with pytest.raises(AssertionError, match="run twice"):
        assert_partition([whole, [f"{module}::test_b"]], collected)
    with pytest.raises(AssertionError, match="outside the packaging module"):
        packaging_half(("pytest", "-q", "tests/unit/test_other.py::test_a"), collected)


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
        (("pytest", "-q", "tests/a/test_x.py::test_one"), {"tests/a/test_x.py"}),
        (
            ("pytest", "-q", "tests/a/test_x.py::test_one", "tests/a/test_x.py::test_two"),
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
