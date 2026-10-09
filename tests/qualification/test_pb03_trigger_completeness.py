"""B12: every repository input of the PB-03 producer triggers PB-03 on a pull request.

PB-03 runs on ``pull_request`` only for the paths its workflow lists. A runner
input outside that list (a contract erratum, a fixture manifest, the engine pin
file) could change the evidence without PB-03 running on the PR. The inputs are
measured, not restated: a fresh interpreter imports the three PB-03 scripts and
loads the effective contract, the actual-card corpus and the engine pins under an
``open`` audit hook, and every repository file it touched must match a listed
path.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from functools import cache
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "pb03-runtime-qualification.yml"
SCRIPTS = (
    "scripts/run_current_boundary_qualification.py",
    "scripts/assemble_current_boundary_evidence.py",
    "scripts/run_midgame_capability_probe.py",
)

# Runs in a fresh interpreter so the audit hook never outlives the measurement.
_PROBE = r"""
import importlib.util, json, os, runpy, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
touched = set()
def hook(event, args):
    if event == "subprocess.Popen" and len(args) > 1 and isinstance(args[1], (list, tuple)):
        # A child process's own reads are invisible to this hook; a repository
        # script the child is launched with is still an input of the parent.
        base = Path(os.fsdecode(args[2])) if len(args) > 2 and args[2] else Path.cwd()
        for arg in args[1]:
            try:
                path = (base / os.fsdecode(arg)).resolve()
                if path.is_file():
                    touched.add(str(path.relative_to(root)))
            except Exception:
                pass
        return
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        try:
            raw = os.fsdecode(args[0])
            if raw.endswith(".pyc"):
                raw = importlib.util.source_from_cache(raw)
            path = Path(raw).resolve()
            touched.add(str(path.relative_to(root)))
        except Exception:
            pass
sys.addaudithook(hook)
sys.path.insert(0, str(root / "src"))
for script in sys.argv[2:]:
    runpy.run_path(str(root / script), run_name="pb03_input_probe")
from commander_lab.qualification.current_boundary import bridge_launcher, gate_derivations
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)
materialization = load_effective_materialization(root)
materialization.receipt()
list(materialization.denominator_records())
gate_derivations.actual_card_corpus(root)
bridge_launcher.canonical_forge_authority()
# Every input the runner digests into its identity is an input of the evidence.
from commander_lab.qualification.current_boundary import receipts
touched.update(receipts.capture_runner_identity(root).input_digests)
modules = {
    str(Path(module.__file__).resolve().relative_to(root))
    for module in list(sys.modules.values())
    if getattr(module, "__file__", None)
    and str(Path(module.__file__).resolve()).startswith(str(root))
}
print(json.dumps(sorted(touched | modules)))
"""


# Installed as sitecustomize for every Python process the measured tests start:
# appends each file the process opens to $PB03_CHILD_READS. The log is opened
# before the hook exists, so the hook's own writes are not audited.
_CHILD_HOOK = r"""
import os, sys
_log = os.environ.get("PB03_CHILD_READS")
if _log:
    _fd = os.open(_log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    def _hook(event, args):
        if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
            try:
                os.write(_fd, (os.path.abspath(os.fsdecode(args[0])) + "\n").encode())
            except Exception:
                pass
    sys.addaudithook(_hook)
"""


def _pattern(glob: str) -> re.Pattern[str]:
    """GitHub path-filter semantics: ``**`` crosses directories, ``*`` does not."""
    out = ""
    index = 0
    while index < len(glob):
        if glob.startswith("**", index):
            out += ".*"
            index += 2
        elif glob[index] == "*":
            out += "[^/]*"
            index += 1
        else:
            out += re.escape(glob[index])
            index += 1
    return re.compile(out + r"\Z")


@cache
def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _trigger_paths() -> list[str]:
    triggers = _workflow().get("on") or _workflow().get(True)
    return list(triggers["pull_request"]["paths"])


def _covered(path: str) -> bool:
    return any(_pattern(glob).match(path) for glob in _trigger_paths())


@cache
def _measured_inputs() -> tuple[str, ...]:
    # No bytecode cache: a warm .pyc would hide the source file it was compiled
    # from (a module loaded by spec_from_file_location is not in sys.modules).
    with tempfile.TemporaryDirectory() as empty_cache:
        env = {
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": empty_cache,
        }
        completed = subprocess.run(
            [sys.executable, "-c", _PROBE, str(REPO), *SCRIPTS],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
    paths = json.loads(completed.stdout.strip().splitlines()[-1])
    return tuple(
        path
        for path in paths
        if "__pycache__" not in path
        and not path.startswith(("qualification/current-boundary-epochs/", ".git/"))
    )


def test_the_measurement_sees_the_contract_and_the_code() -> None:
    """The probe itself is live: it reports the contract, the pins and the runner code."""
    inputs = set(_measured_inputs())
    assert "qualification/CURRENT_PRE_FREEZE_CONTRACT.json" in inputs
    assert "config/rules_engines.json" in inputs
    assert any(path.startswith("qualification/pre-freeze-successor/") for path in inputs)
    assert "src/commander_lab/qualification/current_boundary/materialization.py" in inputs


def test_every_measured_input_triggers_pb03() -> None:
    uncovered = sorted(path for path in _measured_inputs() if not _covered(path))
    assert not uncovered, f"PB-03 inputs that do not trigger PB-03 on a PR: {uncovered}"


def _packaging_inputs() -> set[str]:
    """Files ``pip install -e .`` reads: pyproject.toml and the files it declares."""
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    declared = set()
    readme = project.get("readme")
    if isinstance(readme, str):
        declared.add(readme)
    elif isinstance(readme, dict) and "file" in readme:
        declared.add(readme["file"])
    license_ = project.get("license")
    if isinstance(license_, dict) and "file" in license_:
        declared.add(license_["file"])
    declared.update(project.get("license-files") or ())
    return {"pyproject.toml", *declared}


def test_the_packaging_inputs_include_the_declared_readme() -> None:
    assert "README.md" in _packaging_inputs()


def _workflow_steps() -> str:
    return "\n".join(
        step.get("run") or "" for job in _workflow()["jobs"].values() for step in job["steps"]
    )


@cache
def _tracked_files() -> tuple[str, ...]:
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    return tuple(path for path in listed.split("\0") if path)


def _shell_glob(argument: str) -> re.Pattern[str]:
    """The shell's own glob for one path argument: ``*``, ``?`` and ``[...]``
    never cross ``/``."""
    out = ""
    index = 0
    while index < len(argument):
        char = argument[index]
        if char == "*":
            out += "[^/]*"
        elif char == "?":
            out += "[^/]"
        elif char == "[" and "]" in argument[index + 2 :]:
            end = argument.index("]", index + 2)
            body = argument[index + 1 : end]
            negate = body[:1] in ("!", "^")
            body = body[1:] if negate else body
            out += "(?!/)[" + ("^" if negate else "") + body.replace("\\", "\\\\") + "]"
            index = end
        else:
            out += re.escape(char)
        index += 1
    return re.compile(out + r"\Z")


def _expand(arguments: list[str], tracked: tuple[str, ...]) -> list[str]:
    """Each workflow path argument as the files the shell hands the command.

    A literal argument is itself; a wildcard argument is every tracked file it
    matches. A wildcard that matches nothing fails closed: the shell would pass
    the pattern through unchanged and the measurement would silently lose it.
    """
    files: set[str] = set()
    for argument in arguments:
        if not any(char in argument for char in "*?["):
            files.add(argument)
            continue
        matched = [path for path in tracked if _shell_glob(argument).match(path)]
        if not matched:
            raise AssertionError(f"workflow argument {argument!r} selects no tracked file")
        files.update(matched)
    return sorted(files)


_ARGUMENT = r"[\w./*?\[\]!-]+\.py"
# pytest options that consume the next token as their value.
_PYTEST_VALUE_OPTIONS = frozenset(
    {"-k", "-m", "-o", "-p", "-c", "-W", "--rootdir", "--deselect", "--ignore", "--basetemp"}
)


def _pytest_positionals(steps: str) -> list[str]:
    """Every positional argument of every pytest command in the workflow.

    Each one must be a recognisable test path (a literal file or a wildcard
    over files); anything else (a directory, a variable, a brace list) fails
    closed rather than silently leaving the measurement.
    """
    import shlex

    positionals: list[str] = []
    for line in steps.replace("\\\n", " ").splitlines():
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError as exc:
            raise AssertionError(f"unparseable workflow command {line!r}") from exc
        if "pytest" not in tokens:
            continue
        rest = tokens[tokens.index("pytest") + 1 :]
        skip = False
        for token in rest:
            if skip:
                skip = False
                continue
            if token in _PYTEST_VALUE_OPTIONS:
                skip = True
                continue
            if token.startswith("-"):
                continue
            path = token.split("::", 1)[0]
            if not re.fullmatch(rf"tests/{_ARGUMENT}", path):
                raise AssertionError(f"pytest argument {token!r} is not a recognisable test path")
            positionals.append(path)
    return positionals


def _workflow_arguments(prefixes: str) -> list[str]:
    """Every script/test path argument the workflow passes, wildcards included."""
    steps = _workflow_steps()
    found = set(re.findall(rf"(?:{prefixes})/{_ARGUMENT}", steps))
    if "tests" in prefixes.split("|"):
        found.update(_pytest_positionals(steps))
    return sorted(found)


def test_every_file_the_workflow_runs_triggers_pb03() -> None:
    invoked = sorted(
        set(_expand(_workflow_arguments("scripts|tests"), _tracked_files()))
        | _packaging_inputs()
        | {
            "requirements/lock.txt",
            ".github/workflows/pb03-runtime-qualification.yml",
        }
    )
    uncovered = [path for path in invoked if not _covered(path)]
    assert not uncovered, f"files the PB-03 workflow runs or installs from: {uncovered}"


@pytest.mark.parametrize(
    ("glob", "path", "expected"),
    [
        (
            "qualification/pre-freeze-successor/**",
            "qualification/pre-freeze-successor/a/b.json",
            True,
        ),
        ("src/commander_lab/*.py", "src/commander_lab/x/y.py", False),
        ("config/rules_engines.json", "config/rules_engines.json.bak", False),
    ],
)
def test_the_path_matcher_follows_github_semantics(glob, path, expected) -> None:
    assert bool(_pattern(glob).match(path)) is expected


def test_the_workflow_streams_runner_output() -> None:
    assert _workflow()["env"].get("PYTHONUNBUFFERED") == "1"


def test_runner_phases_report_their_duration_on_stdout_only(monkeypatch, capsys, tmp_path) -> None:
    import importlib.util

    monkeypatch.delenv("FORGE_WORKSPACE", raising=False)
    path = REPO / "scripts" / "run_current_boundary_qualification.py"
    spec = importlib.util.spec_from_file_location("b12_runner_under_test", path)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, runner)
    spec.loader.exec_module(runner)
    monkeypatch.setattr(runner, "OUT_DIR", tmp_path / "out")
    ticks = iter([10.0, 12.5, 20.0])
    monkeypatch.setattr(runner, "time", type("Clock", (), {"monotonic": lambda: next(ticks)}))
    runner.phase("first")
    runner.phase("second")
    runner.phase(None)
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "[pb03 phase] first: start",
        "[pb03 phase] first: done in 2.5s (run 2.5s)",
        "[pb03 phase] second: start",
        "[pb03 phase] second: done in 7.5s (run 10.0s)",
    ]
    # Timing never reaches an evidence artifact.
    assert not (tmp_path / "out").exists()
    source = path.read_text(encoding="utf-8")
    assert source.count('phase("') + source.count('phase(f"') >= 9


@cache
def _measured_workflow_test_inputs() -> tuple[str, ...]:
    """Execute the workflow's offline tests under the same file-read audit hook."""
    invoked = _expand(_workflow_arguments("tests"), _tracked_files())
    assert invoked, "measurement must execute the workflow's actual tests"
    probe = (
        _PROBE[: _PROBE.index("for script in sys.argv[2:]:")]
        + r"""
import pytest
result = pytest.main(["-q", "-p", "no:cacheprovider", "-o", "addopts=", *sys.argv[2:]])
if result != 0:
    raise SystemExit(result)
print(json.dumps(sorted(touched)))
"""
    )
    with tempfile.TemporaryDirectory() as empty_cache, tempfile.TemporaryDirectory() as hooks:
        # Child Python processes the tests launch (the generator determinism
        # tests) inherit this sitecustomize: their own reads are logged too,
        # so an input a child reads directly cannot leave the measurement.
        child_log = Path(hooks) / "child-reads.log"
        (Path(hooks) / "sitecustomize.py").write_text(_CHILD_HOOK, encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, "-c", probe, str(REPO), *invoked],
            cwd=REPO,
            env={
                **os.environ,
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPYCACHEPREFIX": empty_cache,
                "PYTHONPATH": os.pathsep.join(
                    [hooks, *filter(None, [os.environ.get("PYTHONPATH")])]
                ),
                "PB03_CHILD_READS": str(child_log),
            },
            capture_output=True,
            text=True,
            check=True,
        )
        child_reads = set()
        if child_log.exists():
            for raw in child_log.read_text(encoding="utf-8").splitlines():
                with contextlib.suppress(ValueError):
                    child_reads.add(str(Path(raw).resolve().relative_to(REPO)))
    tracked = set(_tracked_files())
    # Qualification consumes canonical files. Cache and temporary outputs are
    # neither repository inputs nor evidence, and must not widen the trigger.
    measured = set(json.loads(completed.stdout.strip().splitlines()[-1])) | child_reads
    return tuple(sorted(path for path in measured if path in tracked))


def test_workflow_test_data_inputs_trigger_pb03() -> None:
    inputs = _measured_workflow_test_inputs()
    assert (
        "qualification/pb03-fresh-main-reconciliation-20260929/MIDGAME_CAPABILITY_PROBE.json"
        in inputs
    )
    uncovered = [path for path in inputs if not path.startswith(".git/") and not _covered(path)]
    assert not uncovered, f"PB-03 offline test inputs without a trigger: {uncovered}"


FAMILY = "tests/qualification/test_midgame_arrival_history_*.py"


def test_the_workflow_runs_the_arrival_history_family_by_wildcard() -> None:
    """#646: the early contract step selects the family by wildcard; the
    measurement expands it to the real tracked modules and executes them."""
    assert FAMILY in _workflow_arguments("tests")
    family = _expand([FAMILY], _tracked_files())
    assert len(family) >= 2
    inputs = set(_measured_workflow_test_inputs())
    assert set(family) <= inputs
    # The family's deterministic-generator tests launch the generators in a
    # child process; every generator script is still a measured input.
    generators = _expand(
        ["docs/arrival_history_erratum_*/generate_contract_*.py"], _tracked_files()
    )
    assert len(generators) >= 2
    assert set(generators) <= inputs


def test_red_control_removing_the_family_trigger_leaves_it_uncovered() -> None:
    assert FAMILY in _trigger_paths()
    family = _expand([FAMILY], _tracked_files())
    remaining = [glob for glob in _trigger_paths() if glob != FAMILY]
    uncovered = [
        path for path in family if not any(_pattern(glob).match(path) for glob in remaining)
    ]
    assert uncovered == family


def test_red_control_a_new_family_module_is_selected_and_triggers() -> None:
    added = "tests/qualification/test_midgame_arrival_history_9_9_99.py"
    tracked = (*_tracked_files(), added)
    assert added in _expand([FAMILY], tracked)
    assert _covered(added)


def test_red_control_a_wildcard_that_selects_nothing_fails_closed() -> None:
    with pytest.raises(AssertionError, match="selects no tracked file"):
        _expand(["tests/qualification/test_no_such_family_*.py"], _tracked_files())


def test_the_shell_glob_does_not_cross_directories() -> None:
    assert _shell_glob("tests/a_*.py").match("tests/a_1.py")
    assert not _shell_glob("tests/a_*.py").match("tests/a_x/y.py")


def test_red_control_an_unrecognisable_pytest_argument_fails_closed() -> None:
    for step in (
        "pytest -q tests/qualification/",
        'pytest -q "$FAMILY"',
        "pytest -q tests/qualification/test_{a,b}.py",
    ):
        with pytest.raises(AssertionError, match="not a recognisable test path"):
            _pytest_positionals(step)
    assert _pytest_positionals(
        "python -m pytest -q -k 'x and y' \\\n  tests/a_[0-9]*.py tests/b.py::test_c"
    ) == ["tests/a_[0-9]*.py", "tests/b.py"]


def test_the_shell_glob_handles_bracket_classes() -> None:
    assert _shell_glob("tests/a_1_0_2[89].py").match("tests/a_1_0_28.py")
    assert not _shell_glob("tests/a_1_0_2[89].py").match("tests/a_1_0_27.py")
    assert not _shell_glob("tests/a_[!0-9].py").match("tests/a_5.py")


def test_the_registry_preflight_runs_before_the_engine_builds() -> None:
    """Efficiency M16: a lane-registry record gap fails in the early contract
    step, before the ≈5 min of engine builds and the ≈40 min runtime."""
    steps = [step for job in _workflow()["jobs"].values() for step in job["steps"]]
    names = [step.get("name") for step in steps]
    preflight = next(
        index
        for index, step in enumerate(steps)
        if "tests/qualification/test_lane_registry_declarations.py" in (step.get("run") or "")
    )
    assert preflight < names.index("Build pinned XMage")
    assert preflight < names.index("Build and warm admitted Forge exact source")
