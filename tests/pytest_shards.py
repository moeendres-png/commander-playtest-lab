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
    """pytest arguments of shard ``index`` (without interpreter and without ``--junitxml``)."""
    arguments = list(selection.options)
    if index < len(plan) - 1:
        return [*arguments, *plan[index]]
    others = [name for shard in plan[:-1] for name in shard]
    return [
        *arguments,
        *selection.roots,
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


def main(argv: Sequence[str]) -> int:
    if len(argv) < 2 or argv[0] != "weights":
        print("usage: python -m tests.pytest_shards weights JUNIT_XML...", file=sys.stderr)
        return 2
    document: dict[str, Any] = {
        "comment": "Seconds per test file from a serial run; used only to balance --shards.",
        "files": weights_from_junit([Path(item) for item in argv[1:]], Path.cwd()),
    }
    print(json.dumps(document, indent=1, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
