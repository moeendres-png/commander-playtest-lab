"""``pytest --shards=N`` runs every selected test exactly once and keeps the suite's verdict."""

from __future__ import annotations

import os
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
    """Five test files, one failing test, one ignored directory."""
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\ntestpaths = suite\naddopts = -p no:cacheprovider\n", encoding="utf-8"
    )
    _write(tmp_path / "suite/a/test_one.py", "def test_a():\n    pass\n\ndef test_b():\n    pass\n")
    _write(tmp_path / "suite/a/test_two.py")
    _write(tmp_path / "suite/b/test_three.py", "def test_bad():\n    assert 1 == 2\n")
    _write(tmp_path / "suite/b/test_new_unlisted.py")
    _write(tmp_path / "suite/skipped/test_ignored.py", "def test_never():\n    raise SystemExit\n")
    (tmp_path / "weights.json").write_text(
        '{"files": {"suite/a/test_one.py": 5.0, "suite/a/test_two.py": 3.0,'
        ' "suite/b/test_three.py": 4.0, "suite/gone/test_removed.py": 9.0,'
        ' "suite/skipped/test_ignored.py": 2.0}}',
        encoding="utf-8",
    )
    return tmp_path


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
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return {line for line in done.stdout.splitlines() if "::" in line}


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
    selection = shards.parse_arguments(["--ignore=suite/skipped", "suite"], ("suite",))
    chosen = shards.selected_files(shards.load_weights(root / "weights.json"), root, selection)
    assert sorted(chosen) == ["suite/a/test_one.py", "suite/a/test_two.py", "suite/b/test_three.py"]
    assert shards.load_weights(root / "missing.json") == {}


def test_every_shard_runs_its_own_tests_and_all_together_run_every_test_once(
    tmp_path: Path,
) -> None:
    root = _suite(tmp_path)
    selection = shards.parse_arguments(["--ignore=suite/skipped"], ("suite",))
    chosen = shards.selected_files(shards.load_weights(root / "weights.json"), root, selection)
    plan = shards.plan_shards(chosen, 3)
    per_shard = [
        _collect(root, shards.shard_arguments(selection, plan, index)) for index in range(3)
    ]
    everything = _collect(root, ["--ignore=suite/skipped"])
    assert len(everything) == 5
    assert set().union(*per_shard) == everything
    assert sum(len(found) for found in per_shard) == len(everything)
    # the file the table does not know runs in the last shard
    assert "suite/b/test_new_unlisted.py::test_ok" in per_shard[-1]


def _run_sharded(root: Path, weights: str = "weights.json") -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "PYTHONPATH": str(REPO), "PYTEST_PLUGINS": "tests.pytest_shards"}
    environment.pop(shards.CHILD_ENV, None)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--shards=2",
            f"--shard-weights={root / weights}",
            "--junitxml=out/pytest-junit.xml",
            "--ignore=suite/skipped",
        ],
        cwd=root,
        env=environment,
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
    (root / "suite/b/test_three.py").write_text("def test_bad(:\n", encoding="utf-8")
    (root / "suite/b/test_new_unlisted.py").unlink()
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
    shards.merge_junit([first, second, tmp_path / "missing.xml"], target)
    merged = ET.parse(target).getroot()
    assert [merged.get(key) for key in ("tests", "failures", "errors", "skipped", "time")] == [
        "5",
        "1",
        "1",
        "2",
        "2.000",
    ]
    assert len(merged.findall("testsuite")) == 2


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


def test_the_checked_in_weight_table_is_usable() -> None:
    weights = shards.load_weights(shards.WEIGHTS_PATH)
    assert weights
    assert all(seconds > 0 for seconds in weights.values())
    assert not any(name.startswith("tests/qualification/") for name in weights)
