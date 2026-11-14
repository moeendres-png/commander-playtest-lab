"""``pytest --shards=N`` runs every selected test exactly once and keeps the suite's verdict."""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests import pytest_shards as shards

REPO = Path(__file__).resolve().parents[2]
QUALITY_ARGUMENTS = (
    "-q",
    "--durations=50",
    "--junitxml=artifacts/quality/pytest-junit.xml",
    "--shards=4",
    "--ignore=tests/qualification",
)


def _write(path: Path, text: str = "def test_ok():\n    assert True\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _suite(tmp_path: Path) -> Path:
    """Five test files, one failing test, one ignored directory, under the real conftest."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/__init__.py").write_text("", encoding="utf-8")
    for name in ("conftest.py", "pytest_shards.py"):
        shutil.copy(REPO / "tests" / name, tmp_path / "tests" / name)
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\ntestpaths = tests/suite\naddopts = -p no:cacheprovider\n", encoding="utf-8"
    )
    _write(
        tmp_path / "tests/suite/a/test_one.py",
        "def test_a():\n    pass\n\ndef test_b():\n    pass\n",
    )
    _write(tmp_path / "tests/suite/a/test_two.py")
    _write(tmp_path / "tests/suite/b/test_three.py", "def test_bad():\n    assert 1 == 2\n")
    _write(tmp_path / "tests/suite/b/test_new_unlisted.py")
    _write(
        tmp_path / "tests/suite/skipped/test_ignored.py",
        "def test_never():\n    raise SystemExit\n",
    )
    (tmp_path / "weights.json").write_text(
        '{"files": {"tests/suite/a/test_one.py": 5.0, "tests/suite/a/test_two.py": 3.0,'
        ' "tests/suite/b/test_three.py": 4.0, "tests/suite/gone/test_removed.py": 9.0,'
        ' "tests/suite/skipped/test_ignored.py": 2.0}}',
        encoding="utf-8",
    )
    return tmp_path


def _environment() -> dict[str, str]:
    environment = {**os.environ, "PYTHONPATH": str(REPO / "src")}
    environment.pop(shards.CHILD_ENV, None)
    return environment


def _collect(root: Path, arguments: list[str]) -> set[str]:
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            *arguments,
        ],
        cwd=root,
        env=_environment(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return {line for line in done.stdout.splitlines() if "::" in line}


def test_conftest_and_module_agree_on_the_child_marker() -> None:
    assert f'"{shards.CHILD_ENV}"' in (REPO / "tests/conftest.py").read_text(encoding="utf-8")


def test_the_quality_command_is_modelled() -> None:
    selection = shards.parse_arguments(QUALITY_ARGUMENTS, ("tests",))
    assert selection.options == ("-q", "--durations=50")
    assert selection.junit == "artifacts/quality/pytest-junit.xml"
    assert selection.roots == ("tests",)
    assert selection.ignores == ("tests/qualification",)


@pytest.mark.parametrize(
    "argument",
    ["-k", "-x", "--shards", "--lf", "-m", "tests/unit/test_x.py::test_one", "-p"],
)
def test_an_unmodelled_argument_is_refused(argument: str) -> None:
    with pytest.raises(ValueError, match="unmodelled pytest argument"):
        shards.parse_arguments(["-q", argument], ("tests",))


def test_the_plan_is_a_deterministic_balanced_partition() -> None:
    files = {f"tests/f{index}.py": float(weight) for index, weight in enumerate(range(1, 40))}
    plan = shards.plan_shards(files, 4)
    assert plan == shards.plan_shards(dict(reversed(files.items())), 4)
    flat = [name for shard in plan for name in shard]
    assert sorted(flat) == sorted(files)
    loads = [sum(files[name] for name in shard) for shard in plan]
    assert max(loads) - min(loads) <= max(files.values())


def test_vanished_ignored_and_unselected_files_are_left_out(tmp_path: Path) -> None:
    root = _suite(tmp_path)
    selection = shards.parse_arguments(
        ["--ignore=tests/suite/skipped", "tests/suite"], ("tests/suite",)
    )
    chosen = shards.selected_files(shards.load_weights(root / "weights.json"), root, selection)
    assert sorted(chosen) == [
        "tests/suite/a/test_one.py",
        "tests/suite/a/test_two.py",
        "tests/suite/b/test_three.py",
    ]
    assert shards.load_weights(root / "missing.json") == {}


def test_every_shard_runs_its_own_tests_and_all_together_run_every_test_once(
    tmp_path: Path,
) -> None:
    root = _suite(tmp_path)
    selection = shards.parse_arguments(["--ignore=tests/suite/skipped"], ("tests/suite",))
    chosen = shards.selected_files(shards.load_weights(root / "weights.json"), root, selection)
    plan = shards.plan_shards(chosen, 3)
    per_shard = [
        _collect(root, shards.shard_arguments(selection, plan, index)) for index in range(3)
    ]
    everything = _collect(root, ["--ignore=tests/suite/skipped"])
    assert len(everything) == 5
    assert set().union(*per_shard) == everything
    assert sum(len(found) for found in per_shard) == len(everything)
    # the file the table does not know runs in the last shard
    assert "tests/suite/b/test_new_unlisted.py::test_ok" in per_shard[-1]


def _run_sharded(root: Path, weights: str = "weights.json") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--shards=2",
            f"--shard-weights={root / weights}",
            "--junitxml=out/pytest-junit.xml",
            "--ignore=tests/suite/skipped",
        ],
        cwd=root,
        env=_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_failing_test_in_any_shard_fails_the_run_and_the_report_is_merged(
    tmp_path: Path,
) -> None:
    root = _suite(tmp_path)
    done = _run_sharded(root)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "pytest shard 1/2: exit code" in done.stdout
    assert "test_bad" in done.stdout
    report = ET.parse(root / "out/pytest-junit.xml").getroot()
    assert report.tag == "testsuites"
    assert (report.get("tests"), report.get("failures")) == ("5", "1")
    cases = {case.get("name") for case in report.iter("testcase")}
    assert cases == {"test_a", "test_b", "test_ok", "test_bad"}
    assert sum(1 for _ in report.iter("testcase")) == 5
    assert (root / "out/pytest-shard-1.log").is_file()
    assert (root / "out/pytest-shard-2.log").is_file()
    assert not list((root / "out").glob(".pytest-junit-shard-*.xml"))


def test_an_error_that_stops_collection_in_one_shard_fails_the_run(tmp_path: Path) -> None:
    root = _suite(tmp_path)
    (root / "tests/suite/b/test_three.py").write_text("def test_bad(:\n", encoding="utf-8")
    (root / "tests/suite/b/test_new_unlisted.py").unlink()
    done = _run_sharded(root)
    assert done.returncode >= 2, done.stdout + done.stderr
    assert "SyntaxError" in done.stdout


def test_without_a_weight_table_the_suite_runs_as_one_ordinary_process(tmp_path: Path) -> None:
    root = _suite(tmp_path)
    done = _run_sharded(root, weights="missing.json")
    assert done.returncode == 1, done.stdout + done.stderr
    assert "running one process" in done.stdout
    assert "pytest shard" not in done.stdout
    assert "1 failed, 4 passed" in done.stdout


def test_junit_reports_are_merged_with_summed_totals(tmp_path: Path) -> None:
    first = tmp_path / "one.xml"
    second = tmp_path / "two.xml"
    first.write_text(
        '<testsuites><testsuite tests="2" failures="1" errors="0" skipped="0" time="1.5">'
        '<testcase classname="t.a" name="x" time="1"/></testsuite></testsuites>',
        encoding="utf-8",
    )
    second.write_text(
        '<testsuite tests="3" failures="0" errors="1" skipped="2" time="0.5"/>', encoding="utf-8"
    )
    target = tmp_path / "out" / "merged.xml"
    shards.merge_junit([first, second], target)
    merged = ET.parse(target).getroot()
    assert [merged.get(key) for key in ("tests", "failures", "errors", "skipped", "time")] == [
        "5",
        "1",
        "1",
        "2",
        "2.000",
    ]
    assert len(merged.findall("testsuite")) == 2


def test_a_missing_shard_report_is_an_error_not_a_gap(tmp_path: Path) -> None:
    present = tmp_path / "one.xml"
    present.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0" time="1"/>')
    with pytest.raises(FileNotFoundError):
        shards.merge_junit([present, tmp_path / "missing.xml"], tmp_path / "merged.xml")
    assert not (tmp_path / "merged.xml").exists()


@pytest.mark.parametrize(
    ("codes", "expected"),
    [
        ([0, 0], 0),
        ([0, 1, 0], 1),
        ([1, 2], 2),
        ([-9, 0, 0, 0], 137),
        ([0, 0, -15], 143),
        ([-9, 1], 137),
    ],
)
def test_the_worst_shard_exit_code_counts_a_signal_death_as_a_failure(
    codes: list[int], expected: int
) -> None:
    assert shards.exit_status(codes) == expected


def test_a_shard_killed_by_a_signal_fails_the_run(tmp_path: Path) -> None:
    root = _suite(tmp_path)
    _write(
        root / "tests/suite/c/test_killer.py",
        "import os\nimport signal\n\ndef test_kill():\n    os.kill(os.getpid(), signal.SIGKILL)\n",
    )
    (root / "weights.json").write_text(
        '{"files": {"tests/suite/c/test_killer.py": 9.0, "tests/suite/a/test_one.py": 5.0,'
        ' "tests/suite/a/test_two.py": 3.0}}',
        encoding="utf-8",
    )
    done = _run_sharded(root)
    assert done.returncode == 137, done.stdout + done.stderr
    assert "shard report missing for shard(s) [1]" in done.stdout
    assert "shard exit codes: -9, " in done.stdout
    assert not (root / "out/pytest-junit.xml").exists()


def test_a_stale_shard_report_is_never_merged(tmp_path: Path) -> None:
    root = _suite(tmp_path)
    (root / "out").mkdir()
    stale = root / "out/.pytest-junit-shard-1.xml"
    stale.write_text('<testsuite tests="999" failures="0" errors="0" skipped="0" time="1"/>')
    done = _run_sharded(root)
    assert done.returncode == 1, done.stdout + done.stderr
    report = ET.parse(root / "out/pytest-junit.xml").getroot()
    assert report.get("tests") == "5"


def test_without_the_option_and_in_a_child_the_module_is_not_even_imported(
    tmp_path: Path,
) -> None:
    root = _suite(tmp_path)
    program = (
        "import sys, pytest\n"
        "code = pytest.main(sys.argv[1:])\n"
        "print('MODULE IMPORTED', 'tests.pytest_shards' in sys.modules)\n"
        "raise SystemExit(code)\n"
    )
    for extra, marker in (([], None), (["--shards=2"], "1/2")):
        environment = _environment()
        if marker:
            environment[shards.CHILD_ENV] = marker
        done = subprocess.run(
            [sys.executable, "-c", program, "-q", *extra, "--ignore=tests/suite/skipped"],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode == 1, done.stdout + done.stderr
        assert "MODULE IMPORTED False" in done.stdout
        assert "pytest shard" not in done.stdout
        assert "1 failed, 4 passed" in done.stdout


def test_weights_are_read_from_junit_class_names(tmp_path: Path) -> None:
    _write(tmp_path / "tests/unit/test_alpha.py")
    report = tmp_path / "report.xml"
    report.write_text(
        "<testsuites><testsuite>"
        '<testcase classname="tests.unit.test_alpha" name="a" time="1.5"/>'
        '<testcase classname="tests.unit.test_alpha.TestKlass" name="b" time="2.0"/>'
        '<testcase classname="tests.unit.test_missing" name="c" time="9"/>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    assert shards.weights_from_junit([report], tmp_path) == {"tests/unit/test_alpha.py": 3.5}


REGENERATE = (
    "python -m tests.pytest_shards weights --from-artifacts > tests/pytest_shard_weights.json "
    "(rebuilds the table from the JUnit artifacts of the latest main CI run), or "
    "python -m tests.pytest_shards weights JUNIT_XML... > tests/pytest_shard_weights.json"
)
# A test file without a weight is planned at the mean weight and runs in the last in-slot shard,
# so adding a test never breaks CI; the table only has to stay mostly current.
UNWEIGHTED_SHARE = 0.05


def _unweighted(table: dict[str, float], discovered: list[str]) -> list[str]:
    return [name for name in discovered if name not in table]


def test_the_checked_in_weight_table_is_usable() -> None:
    weights = shards.load_weights(shards.WEIGHTS_PATH)
    discovered = shards.discover_test_files(REPO)
    stale = sorted(set(weights) - set(discovered))
    assert not stale, f"the weight table names files that do not exist: {stale[:10]}. {REGENERATE}"
    unweighted = _unweighted(weights, discovered)
    assert len(unweighted) <= UNWEIGHTED_SHARE * len(discovered), (
        f"{len(unweighted)} of {len(discovered)} test files have no weight "
        f"(limit {UNWEIGHTED_SHARE:.0%}), e.g. {unweighted[:5]}. {REGENERATE}"
    )
    assert all(seconds > 0 for seconds in weights.values())
    assert not any(name.startswith("tests/qualification/") for name in weights)


def test_the_weight_guard_tolerates_a_few_new_files_but_not_many() -> None:
    discovered = [f"tests/unit/test_{index}.py" for index in range(100)]
    table = {name: 1.0 for name in discovered[:96]}
    assert len(_unweighted(table, discovered)) <= UNWEIGHTED_SHARE * len(discovered)
    assert len(_unweighted({name: 1.0 for name in discovered[:90]}, discovered)) > (
        UNWEIGHTED_SHARE * len(discovered)
    )


def test_the_qualification_weight_table_is_usable() -> None:
    weights = shards.load_weights(shards.QUALIFICATION_WEIGHTS_PATH)
    discovered = shards.discover_qualification_files(REPO)
    stale = sorted(set(weights) - set(discovered))
    assert not stale, f"stale qualification weights: {stale[:10]}. {REGENERATE}"
    assert len(_unweighted(weights, discovered)) <= UNWEIGHTED_SHARE * len(discovered), REGENERATE


def test_the_checked_in_docs_test_list_is_complete_and_exists_on_disk() -> None:
    raw = shards.DOCS_TESTS_PATH.read_text(encoding="utf-8")
    import json

    files = json.loads(raw)["files"]
    assert files == sorted(set(files))
    discovered = set(shards.discover_test_files(REPO))
    assert set(files) <= discovered
    assert not any(name.startswith("tests/qualification/") for name in files)
    for required_guard in (
        "tests/unit/test_ci_change_scope.py",
        "tests/unit/test_ci_definition_integrity.py",
        "tests/unit/test_ci_gate.py",
        "tests/unit/test_ci_ruff_annotations.py",
        "tests/unit/test_pytest_shards.py",
        "tests/unit/test_required_test_ownership.py",
    ):
        assert required_guard in files


def test_matrix_files_plan_matrix_and_complete_weights(tmp_path: Path) -> None:
    _write(tmp_path / "tests/unit/test_a.py")
    _write(tmp_path / "tests/unit/test_b.py")
    _write(tmp_path / "tests/unit/test_c.py")
    _write(tmp_path / shards.PACKAGING_TEST)
    _write(tmp_path / "tests/qualification/test_q.py")
    discovered = shards.discover_test_files(tmp_path)
    assert discovered == [
        "tests/unit/test_a.py",
        "tests/unit/test_b.py",
        "tests/unit/test_c.py",
        shards.PACKAGING_TEST,
    ]
    completed = shards.complete_weights(
        {"tests/unit/test_a.py": 4.0, "tests/gone.py": 9.0}, tmp_path
    )
    assert completed == {
        "tests/unit/test_a.py": 4.0,
        "tests/unit/test_b.py": 0.1,
        "tests/unit/test_c.py": 0.1,
        shards.PACKAGING_TEST: 0.1,
    }
    slots = [
        shards.matrix_files(tmp_path, idx, 2, "all", weights={"tests/unit/test_a.py": 4.0})
        for idx in (1, 2)
    ]
    assert sorted(slots[0] + slots[1]) == [
        "tests/unit/test_a.py",
        "tests/unit/test_b.py",
        "tests/unit/test_c.py",
    ]
    docs_slot = shards.matrix_files(
        tmp_path,
        1,
        1,
        "docs",
        weights=completed,
        docs_tests=["tests/unit/test_a.py", "tests/unit/test_missing.py"],
    )
    assert docs_slot == ["tests/unit/test_a.py"]
    with pytest.raises(ValueError, match="matrix count"):
        shards.plan_matrix(["tests/unit/test_a.py"], {}, 0)
    with pytest.raises(ValueError, match=r"outside 1\.\.2"):
        shards.matrix_files(tmp_path, 3, 2)
    with pytest.raises(ValueError, match="unknown scope"):
        shards.matrix_files(tmp_path, 1, 1, "weird")


# Test files that mention a documentation-looking string without reading repository documents.
DOCS_SCAN_EXEMPT = {
    # ".claude" is the directory of a skill script that is loaded as code, not a document.
    "tests/unit/test_gh_ops_brief.py",
}
_DOCS_REFERENCE = re.compile(
    r"^(?:docs|\.claude)$|docs/|\.md$|README|AGENTS|CLAUDE|CHANGELOG|\.claude/"
)


def _docs_references(path: Path) -> list[str]:
    """String literals (docstrings excluded) that name a repository document."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and _DOCS_REFERENCE.search(node.value)
    ]


def test_every_test_that_reads_repository_documents_is_in_the_docs_list() -> None:
    """A docs-only PR runs only the listed files, so a test that reads docs must be listed.

    Files under tests/qualification (run by ``infrastructure``) and the packaging test
    (``packaging`` job) are outside the matrix; ``DOCS_SCAN_EXEMPT`` names the files that only
    mention such strings. This is a static scan of string literals, a guard rather than a proof:
    a path built from non-literal parts is not seen.
    """
    listed = set(shards.load_docs_tests())
    missing = {
        name: _docs_references(REPO / name)[:3]
        for name in shards.discover_test_files(REPO)
        if name not in listed
        and name != shards.PACKAGING_TEST
        and name not in DOCS_SCAN_EXEMPT
        and _docs_references(REPO / name)
    }
    assert not missing, (
        "add these files to tests/pytest_docs_tests.json (or to DOCS_SCAN_EXEMPT with a reason): "
        f"{missing}"
    )
    assert set(shards.discover_test_files(REPO)) >= DOCS_SCAN_EXEMPT


def test_the_docs_scan_sees_a_known_docs_reader() -> None:
    assert _docs_references(REPO / "tests/unit/test_docs_archive.py")


def _shard_commands(
    rootdir: Path, files: list[str], count: int, weights: dict[str, float] | None = None
) -> list[list[str]]:
    """The pytest argument lists of every in-slot shard for explicit ``files`` (as ci.yml runs)."""
    table = shards.load_weights(shards.WEIGHTS_PATH) if weights is None else weights
    selection = shards.parse_arguments(["-q", *files], ("tests",))
    plan = shards.plan_for(shards.selected_files(table, rootdir, selection), count)
    assert plan is not None
    return [shards.shard_arguments(selection, plan, index) for index in range(len(plan))]


def _listed_files(arguments: list[str]) -> list[str]:
    return [item for item in arguments if item.endswith(".py")]


def test_explicit_files_are_split_into_disjoint_shards_that_cover_the_list(
    tmp_path: Path,
) -> None:
    names = [f"tests/unit/test_{letter}.py" for letter in "abcdefghij"]
    for name in names:
        _write(tmp_path / name)
    weights = {name: float(index + 1) for index, name in enumerate(names)}
    commands = _shard_commands(tmp_path, names, 4, weights)
    per_shard = [_listed_files(command) for command in commands]
    flat = [name for shard in per_shard for name in shard]
    assert sorted(flat) == sorted(names), "every file exactly once"
    assert len(flat) == len(set(flat))
    for command in commands:
        # --ignore never applies to a file named on the command line, so none may be used.
        assert not any(item.startswith("--ignore") for item in command)


def test_unweighted_explicit_file_is_still_run_exactly_once(tmp_path: Path) -> None:
    names = [f"tests/unit/test_{letter}.py" for letter in "abcd"]
    for name in names:
        _write(tmp_path / name)
    weights = {name: 1.0 for name in names[:3]}
    flat = [
        name
        for command in _shard_commands(tmp_path, names, 2, weights)
        for name in _listed_files(command)
    ]
    assert sorted(flat) == sorted(names)


def test_directory_roots_keep_the_last_shard_ignore_behaviour(tmp_path: Path) -> None:
    names = [f"tests/unit/test_{letter}.py" for letter in "abc"]
    for name in names:
        _write(tmp_path / name)
    selection = shards.parse_arguments(["tests"], ("tests",))
    plan = shards.plan_for({name: 1.0 for name in names}, 2)
    assert plan is not None
    last = shards.shard_arguments(selection, plan, len(plan) - 1)
    assert "tests" in last
    assert {item for item in last if item.startswith("--ignore=")} == {
        f"--ignore={name}" for name in plan[0]
    }


def test_real_tree_in_slot_shards_never_repeat_a_file_of_another_shard() -> None:
    weights = shards.load_weights(shards.WEIGHTS_PATH)
    files = [name for name in shards.discover_test_files(REPO) if name != shards.PACKAGING_TEST]
    for index in range(1, 5):
        slot = shards.matrix_files(REPO, index, 4, "all", weights)
        commands = _shard_commands(REPO, slot, 4, weights)
        per_shard = [_listed_files(command) for command in commands]
        flat = [name for shard in per_shard for name in shard]
        assert sorted(flat) == sorted(slot), f"slot {index}: shards do not partition the slot"
        for command, own in zip(commands, per_shard, strict=True):
            others = set(flat) - set(own)
            assert not others & set(command)
            assert not any(item.startswith("--ignore") for item in command)
    assert files
