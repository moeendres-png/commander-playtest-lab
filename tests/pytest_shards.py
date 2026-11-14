"""Opt-in parallel shards for the pytest suite: ``pytest --shards=N``.

``tests/conftest.py`` declares the option and calls ``command_line_main`` only when it is used;
it does not import this module otherwise, because a module conftest imports becomes a measured
input of every test (``tests/qualification/test_pb03_trigger_completeness.py``).

The required ``quality`` context ran the whole suite in one process (about 16 minutes of the
18-minute job on a 4-core runner). With ``--shards=N`` this process starts N pytest children
instead of running tests itself, and they run side by side:

* **No test is left out or run twice.** Shards 1..N-1 get explicit files from the weight table
  (``pytest_shard_weights.json``, measured seconds per file); the last shard runs the selection
  minus those files. A file missing from the table (a new test) therefore runs in the last
  shard, a file that left the repository is dropped from the table at plan time, and an empty
  or missing table collapses to one ordinary pytest run. A stale table only costs balance.
* **No shared mutable state.** Each shard works in its own copy of the checkout: the suite writes
  into the tree (``data/``, ``artifacts/``) and ``tests/conftest.py`` deletes two fixed report
  paths around every test, which broke a sibling shard's read when they shared one tree.
* **Same verdict.** Every option is passed to every shard unchanged, the exit code is the worst
  shard exit code, and the per-shard JUnit files are merged into the ``--junitxml`` target.

Only the options the required check uses are modelled (see ``parse_arguments``); anything else
is refused rather than guessed, like ``tests/unit/test_required_test_ownership.py`` does.
``python -m tests.pytest_shards weights JUNIT_XML...`` rewrites the table from a run.

CI (``.github/workflows/ci.yml``) adds one level above ``--shards``: the ``tests`` job is a
matrix of runners and each runner executes ``python -m tests.pytest_shards matrix --index I
--count N``, which prints the files of matrix slot I. Every file of ``tests/`` outside
``tests/qualification`` (owned by the ``infrastructure`` context) and outside the packaging
test (its own ``packaging`` job) belongs to exactly one slot; a file the weight table does not
know is still assigned (at the mean weight), so the table going stale only costs balance, and
``tests/unit/test_pytest_shards.py`` fails when the table does not cover the tree.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

WEIGHTS_PATH = Path(__file__).with_name("pytest_shard_weights.json")
DOCS_TESTS_PATH = Path(__file__).with_name("pytest_docs_tests.json")
# Owned by the ``infrastructure`` context (production-qualification.yml), never weighted.
OTHER_OWNER_ROOTS = ("tests/qualification",)
# Owned by the ``packaging`` job of ci.yml: 33 tests that build real wheels and virtual
# environments (about 330 s); the matrix slots never run it.
PACKAGING_TEST = "tests/unit/test_packaging_smoke.py"
CHILD_ENV = "COMMANDER_LAB_PYTEST_SHARD"
# Reporting-only options: they never change which tests are collected or how they run.
REPORTING_FLAGS = frozenset({"-q", "-ra", "-rs"})
REPORTING_PREFIXES = ("--durations=", "--durations-min=")
CHECKOUT_COPY_IGNORE = shutil.ignore_patterns(
    ".mypy_cache", ".ruff_cache", ".pytest_cache", "__pycache__"
)


def command_line_main(config: pytest.Config) -> int | None:
    """The ``pytest_cmdline_main`` of ``tests/conftest.py`` once ``--shards`` is above one."""
    count = int(config.getoption("shards"))
    if Path(config.invocation_params.dir).resolve() != config.rootpath.resolve():
        raise pytest.UsageError("--shards must be run from the rootdir")
    weights_option = config.getoption("shard_weights")
    weights = load_weights(Path(weights_option) if weights_option else WEIGHTS_PATH)
    try:
        selection = parse_arguments(
            config.invocation_params.args, tuple(config.getini("testpaths")) or ("tests",)
        )
    except ValueError as error:
        raise pytest.UsageError(str(error)) from error
    files = selected_files(weights, config.rootpath, selection)
    plan = plan_for(files, count)
    if plan is None:
        print(f"--shards={count}: {len(files)} weighted file(s) selected, running one process")
        return None
    return run_shards(config.rootpath, selection, plan)


@dataclass(frozen=True)
class Selection:
    """What the invoking command asks pytest to run."""

    options: tuple[str, ...]
    junit: str | None
    roots: tuple[str, ...]
    ignores: tuple[str, ...]


def parse_arguments(args: Sequence[str], default_roots: Sequence[str]) -> Selection:
    options: list[str] = []
    roots: list[str] = []
    ignores: list[str] = []
    junit: str | None = None
    for arg in args:
        if arg in REPORTING_FLAGS or arg.startswith(REPORTING_PREFIXES):
            options.append(arg)
        elif arg.startswith(("--shards=", "--shard-weights=")):
            continue
        elif arg.startswith("--junitxml="):
            junit = arg.split("=", 1)[1]
        elif arg.startswith("--ignore="):
            ignores.append(arg.split("=", 1)[1].rstrip("/"))
        elif arg.startswith("-") or "::" in arg:
            raise ValueError(f"unmodelled pytest argument {arg!r} with --shards")
        else:
            roots.append(arg.rstrip("/"))
    return Selection(tuple(options), junit, tuple(roots or default_roots), tuple(ignores))


def load_weights(path: Path) -> dict[str, float]:
    if not path.is_file():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    return {name: float(seconds) for name, seconds in document["files"].items()}


def _under(path: str, root: str) -> bool:
    return path == root or path.startswith(root + "/")


def selected_files(
    weights: Mapping[str, float], rootdir: Path, selection: Selection
) -> dict[str, float]:
    """Weighted files that exist and are selected by the command."""
    return {
        name: seconds
        for name, seconds in weights.items()
        if (rootdir / name).is_file()
        and any(_under(name, root) for root in selection.roots)
        and not any(_under(name, ignored) for ignored in selection.ignores)
    }


def plan_shards(files: Mapping[str, float], count: int) -> list[list[str]]:
    """Longest-processing-time-first assignment; deterministic, ties by name."""
    loads = [0.0] * count
    shards: list[list[str]] = [[] for _ in range(count)]
    for name in sorted(files, key=lambda item: (-files[item], item)):
        index = loads.index(min(loads))
        shards[index].append(name)
        loads[index] += files[name]
    return [sorted(shard) for shard in shards]


def plan_for(files: Mapping[str, float], count: int) -> list[list[str]] | None:
    """The shard plan for ``count`` requested shards, or None when fewer than two have files."""
    shards = min(count, len(files))
    return plan_shards(files, shards) if shards > 1 else None


def shard_arguments(selection: Selection, plan: Sequence[Sequence[str]], index: int) -> list[str]:
    """pytest arguments of shard ``index`` (without interpreter and without ``--junitxml``).

    Explicit test files (roots ending in ``.py``) go to exactly one shard each: pytest applies
    ``--ignore`` only to directory collection, never to a file named on the command line, so a
    "roots plus --ignore" last shard would rerun every file of the other shards. A named file the
    weight table does not know is run by the last shard. Directory roots keep the old shape for
    the last shard: the roots, ignoring every file the other shards run.
    """
    arguments = list(selection.options)
    if index < len(plan) - 1:
        return [*arguments, *plan[index]]
    planned = {name for shard in plan for name in shard}
    directory_roots = [root for root in selection.roots if not root.endswith(".py")]
    unplanned = [root for root in selection.roots if root.endswith(".py") and root not in planned]
    own = [name for name in plan[index] if not any(_under(name, root) for root in directory_roots)]
    if not directory_roots:
        return [*arguments, *own, *unplanned]
    others = [name for shard in plan[:-1] for name in shard]
    return [
        *arguments,
        *directory_roots,
        *own,
        *unplanned,
        *(f"--ignore={name}" for name in (*selection.ignores, *others)),
    ]


def merge_junit(parts: Sequence[Path], target: Path) -> None:
    """Merge every part into ``target``; a part that does not exist is an error, not a gap."""
    merged = ET.Element("testsuites")
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    seconds = 0.0
    for part in parts:
        document = ET.parse(part).getroot()
        for suite in [document] if document.tag == "testsuite" else list(document):
            merged.append(suite)
            for key in totals:
                totals[key] += int(suite.get(key, "0"))
            seconds += float(suite.get("time", "0"))
    for key, value in totals.items():
        merged.set(key, str(value))
    merged.set("time", f"{seconds:.3f}")
    target.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(merged).write(target, encoding="utf-8", xml_declaration=True)


def exit_status(codes: Sequence[int]) -> int:
    """The worst shard result as a process exit code.

    A child killed by a signal has a negative return code (``max([-9, 0])`` would be 0), so it
    counts as 128 plus the signal, the way a shell reports it.
    """
    return max(128 - code if code < 0 else code for code in codes)


def run_shards(rootdir: Path, selection: Selection, plan: Sequence[Sequence[str]]) -> int:
    count = len(plan)
    outdir = Path(selection.junit).resolve().parent if selection.junit else rootdir
    outdir.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="pytest-shards-"))
    junit = [outdir / f".pytest-junit-shard-{index + 1}.xml" for index in range(count)]
    for stale in junit:
        stale.unlink(missing_ok=True)
    print(f"--shards={count}: {sum(len(shard) for shard in plan)} weighted files, checkout copies")
    lock = threading.Lock()
    grouped = bool(os.environ.get("GITHUB_ACTIONS"))

    def run_one(index: int) -> int:
        checkout = scratch / f"shard-{index + 1}"
        shutil.copytree(rootdir, checkout, symlinks=True, ignore=CHECKOUT_COPY_IGNORE)
        log = outdir / f"pytest-shard-{index + 1}.log"
        command = [
            sys.executable,
            "-m",
            "pytest",
            *shard_arguments(selection, plan, index),
            f"--junitxml={junit[index]}",
        ]
        environment = {**os.environ, CHILD_ENV: f"{index + 1}/{count}"}
        try:
            with log.open("w", encoding="utf-8") as sink:
                code = subprocess.run(
                    command, cwd=checkout, env=environment, stdout=sink, stderr=subprocess.STDOUT
                ).returncode
        finally:
            shutil.rmtree(checkout, ignore_errors=True)
        with lock:
            title = f"pytest shard {index + 1}/{count}: exit code {code}"
            print(f"::group::{title}" if grouped else f"===== {title} =====")
            print(log.read_text(encoding="utf-8", errors="replace"), end="")
            print("::endgroup::" if grouped else "")
            sys.stdout.flush()
        return code

    try:
        with ThreadPoolExecutor(max_workers=count) as pool:
            codes = list(pool.map(run_one, range(count)))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    status = exit_status(codes)
    missing = [index + 1 for index, part in enumerate(junit) if not part.is_file()]
    if missing:
        # A shard that left no report cannot be told from one that ran nothing.
        print(f"shard report missing for shard(s) {missing}: the run is not trusted")
        status = max(status, 1)
    elif selection.junit:
        merge_junit(junit, Path(selection.junit).resolve())
    for part in junit:
        part.unlink(missing_ok=True)
    print("shard exit codes:", ", ".join(str(code) for code in codes))
    return status


def weights_from_junit(reports: Sequence[Path], rootdir: Path) -> dict[str, float]:
    """Seconds per test file from JUnit reports (``classname`` is the dotted module path)."""
    seconds: dict[str, float] = {}
    for report in reports:
        for case in ET.parse(report).getroot().iter("testcase"):
            parts = case.get("classname", "").split(".")
            for end in range(len(parts), 0, -1):
                name = "/".join(parts[:end]) + ".py"
                if (rootdir / name).is_file():
                    seconds[name] = seconds.get(name, 0.0) + float(case.get("time", "0"))
                    break
    return {name: max(round(value, 1), 0.1) for name, value in sorted(seconds.items())}


def discover_test_files(rootdir: Path, ignores: Sequence[str] = OTHER_OWNER_ROOTS) -> list[str]:
    """Every ``tests/**/test_*.py`` outside ``ignores``: what ``pytest tests --ignore=...`` collects."""
    return sorted(
        name
        for name in (
            path.relative_to(rootdir).as_posix()
            for path in (rootdir / "tests").rglob("test_*.py")
            if "__pycache__" not in path.parts
        )
        if not any(_under(name, ignored) for ignored in ignores)
    )


def load_docs_tests(path: Path = DOCS_TESTS_PATH) -> list[str]:
    """The test files that read documentation (the docs-only fast path runs only these)."""
    document = json.loads(path.read_text(encoding="utf-8"))
    return sorted(str(name) for name in document["files"])


def plan_matrix(files: Sequence[str], weights: Mapping[str, float], count: int) -> list[list[str]]:
    """Assign every file to exactly one of ``count`` matrix slots (balanced by weight).

    A file without a weight counts as the mean of the known weights, so it is still placed.
    """
    if count < 1:
        raise ValueError("matrix count must be at least 1")
    known = [weights[name] for name in files if name in weights]
    default = sum(known) / len(known) if known else 1.0
    return plan_shards({name: weights.get(name, default) for name in files}, count)


def matrix_files(
    rootdir: Path,
    index: int,
    count: int,
    scope: str = "all",
    weights: Mapping[str, float] | None = None,
    docs_tests: Sequence[str] | None = None,
) -> list[str]:
    """The test files of matrix slot ``index`` (1-based) of ``count``.

    ``all`` is every test the ``quality`` context owns except the packaging test; ``docs`` is the
    docs-only subset. Existing files only: a listed file that left the repository is dropped.
    """
    if not 1 <= index <= count:
        raise ValueError(f"matrix index {index} is outside 1..{count}")
    if scope == "all":
        files = [name for name in discover_test_files(rootdir) if name != PACKAGING_TEST]
    elif scope == "docs":
        listed = load_docs_tests() if docs_tests is None else docs_tests
        files = [name for name in listed if (rootdir / name).is_file()]
    else:
        raise ValueError(f"unknown scope {scope!r}")
    table = load_weights(WEIGHTS_PATH) if weights is None else weights
    return plan_matrix(files, table, count)[index - 1]


def complete_weights(measured: Mapping[str, float], rootdir: Path) -> dict[str, float]:
    """``measured`` restricted to the tree's test files, every other test file at the 0.1 floor."""
    names = discover_test_files(rootdir)
    return {name: measured.get(name, 0.1) for name in names}


def main(argv: Sequence[str]) -> int:
    usage = (
        "usage: python -m tests.pytest_shards weights JUNIT_XML...\n"
        "       python -m tests.pytest_shards matrix --index I --count N [--scope all|docs]"
    )
    if argv and argv[0] == "weights" and len(argv) >= 2:
        rootdir = Path.cwd()
        measured = weights_from_junit([Path(item) for item in argv[1:]], rootdir)
        document: dict[str, Any] = {
            "comment": "Seconds per test file from a serial run; used only to balance --shards"
            " and the CI matrix. Rebuild: python -m tests.pytest_shards weights JUNIT_XML...",
            "files": complete_weights(measured, rootdir),
        }
        print(json.dumps(document, indent=1, sort_keys=False))
        return 0
    if argv and argv[0] == "matrix":
        options = dict(zip(argv[1::2], argv[2::2], strict=False))
        try:
            index, count = int(options["--index"]), int(options["--count"])
            names = matrix_files(Path.cwd(), index, count, options.get("--scope", "all"))
        except (KeyError, ValueError) as error:
            print(f"{error}\n{usage}", file=sys.stderr)
            return 2
        print("\n".join(names))
        return 0
    print(usage, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
