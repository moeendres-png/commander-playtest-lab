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
# setuptools' PEP 639 ``license-files`` default when the project declares none.
SETUPTOOLS_DEFAULT_LICENSE_FILES = ("LICEN[CS]E*", "COPYING*", "NOTICE*", "AUTHORS*")
# Root files setuptools reads when they exist next to pyproject.toml.
SETUPTOOLS_ROOT_FILES = ("setup.py", "setup.cfg", "MANIFEST.in")
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


def _covered(path: str, trigger_paths: list[str] | None = None) -> bool:
    globs = _trigger_paths() if trigger_paths is None else trigger_paths
    return any(_pattern(glob).match(path) for glob in globs)


def _install_inputs(root: Path) -> list[str]:
    """Files the build backend reads for ``pip install -e .``, derived from pyproject.toml.

    The declared readme (string or ``{file = ...}`` table), a ``{file = ...}``
    license, the ``license-files`` globs (setuptools' default globs when none are
    declared), file-backed ``[tool.setuptools.dynamic]`` metadata and the legacy
    setuptools root files, each only where it resolves to a real file.
    """
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project", {})
    setuptools_config = pyproject.get("tool", {}).get("setuptools", {})
    declared: set[str] = {"pyproject.toml"}
    for field in (project.get("readme"), project.get("license")):
        if isinstance(field, dict) and "file" in field:
            declared.add(field["file"])
    if isinstance(project.get("readme"), str):
        declared.add(project["readme"])
    for spec in setuptools_config.get("dynamic", {}).values():
        if isinstance(spec, dict) and "file" in spec:
            files = spec["file"]
            declared.update([files] if isinstance(files, str) else files)
    license_globs = project.get(
        "license-files",
        setuptools_config.get("license-files", SETUPTOOLS_DEFAULT_LICENSE_FILES),
    )
    for glob in license_globs:
        declared.update(path.relative_to(root).as_posix() for path in root.glob(glob))
    declared.update(SETUPTOOLS_ROOT_FILES)
    return sorted(path for path in declared if (root / path).is_file())


def _uncovered_workflow_files(trigger_paths: list[str]) -> list[str]:
    steps = [step.get("run") or "" for job in _workflow()["jobs"].values() for step in job["steps"]]
    script = "\n".join(steps)
    # The workflow installs the project itself, so the build backend's inputs are inputs.
    assert re.search(r"pip install [^\n]*-e \.(?:\s|$)", script), (
        "PB-03 no longer runs pip install -e ."
    )
    invoked = sorted(
        set(re.findall(r"(?:scripts|tests)/[\w./-]+\.py", script))
        | set(_install_inputs(REPO))
        | {"requirements/lock.txt", ".github/workflows/pb03-runtime-qualification.yml"}
    )
    return [path for path in invoked if not _covered(path, trigger_paths)]


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


def test_every_file_the_workflow_runs_triggers_pb03() -> None:
    uncovered = _uncovered_workflow_files(_trigger_paths())
    assert not uncovered, f"files the PB-03 workflow runs or installs from: {uncovered}"


def test_the_package_readme_is_a_derived_install_input() -> None:
    """The live derivation reads ``readme = "README.md"`` from pyproject.toml."""
    assert {"pyproject.toml", "README.md"} <= set(_install_inputs(REPO))


def test_red_control_a_trigger_list_without_the_readme_fails() -> None:
    """The pre-fix trigger list (no README.md) is rejected for exactly the readme."""
    without_readme = [path for path in _trigger_paths() if path != "README.md"]
    assert without_readme != _trigger_paths()
    assert _uncovered_workflow_files(without_readme) == ["README.md"]


def test_install_inputs_follow_every_declared_build_backend_file(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        'readme = { file = "docs/INTRO.rst", content-type = "text/x-rst" }\n'
        'license = { file = "LICENSE.txt" }\n'
        'license-files = ["legal/*.md"]\n'
        "[tool.setuptools.dynamic]\n"
        'version = { file = "VERSION" }\n'
        'dependencies = { file = ["requirements/a.in", "requirements/missing.in"] }\n',
        encoding="utf-8",
    )
    for name in (
        "docs/INTRO.rst",
        "LICENSE.txt",
        "legal/TERMS.md",
        "VERSION",
        "requirements/a.in",
        "setup.cfg",
        "MANIFEST.in",
        "COPYING",
    ):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("x", encoding="utf-8")
    # Declared license-files replace the default globs, so COPYING is not read.
    assert _install_inputs(tmp_path) == [
        "LICENSE.txt",
        "MANIFEST.in",
        "VERSION",
        "docs/INTRO.rst",
        "legal/TERMS.md",
        "pyproject.toml",
        "requirements/a.in",
        "setup.cfg",
    ]
    (tmp_path / "pyproject.toml").write_text('[project]\nreadme = "README.md"\n', encoding="utf-8")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    # Without declared license-files setuptools' default globs apply.
    assert _install_inputs(tmp_path) == [
        "COPYING",
        "LICENSE.txt",
        "MANIFEST.in",
        "README.md",
        "pyproject.toml",
        "setup.cfg",
    ]


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
