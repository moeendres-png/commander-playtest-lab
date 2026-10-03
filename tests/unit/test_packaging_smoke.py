"""B9 packaging-smoke contract tests (issue #490).

The suite proves three distinct things:

* the **positive control really passes** — a real wheel built from the candidate
  source installs into a clean isolated environment together with *only* its own
  declared dependency closure, the installed package imports from that
  installation, every declared console entrypoint runs, and the independent
  ``check`` re-adjudicates the evidence to PASS;
* every required **red control** kills its failure class for the intended reason
  (each asserts its specific failure code) — a broken, missing, ambiguous,
  tampered or foreign-commit wheel, a dirty working tree, an undeclared runtime
  dependency that merely happens to be locked, a version mismatch, a missing or
  retargeted entrypoint, a source-tree-import substitution, an editable or
  contaminated install, stale evidence surviving an early failure, and missing,
  malformed, ``UNKNOWN``, forged, contradictory or unbound evidence;
* the packaging smoke is wired into the required ``quality`` context without
  weakening any required-check static invariant.

The full-consumer-path controls deliberately use the real script entry point
rather than a helper function, so a guard that only works in isolation cannot
produce a false PASS. Every repository the smoke runs against is a clean clone of
the current ``HEAD`` in a temporary directory, so the suite never modifies the
real tree and does not depend on the caller's uncommitted state. The honest
isolated run is shared by every control that only needs a template document.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_packaging_smoke.py"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

sys.path.insert(0, str(ROOT / "scripts"))

import verify_packaging_smoke as packaging  # noqa: E402

# The package contract is read from the live pyproject.toml by the consumer, so the
# expectations below are pinned to the contract the smoke itself uses.
CONTRACT = packaging.read_package_contract(ROOT / "pyproject.toml")
DEPENDENCY_LOCK = ROOT / "requirements" / "lock.txt"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNKNOWN = 3

# Full-consumer-path controls cost one isolated environment each. Keep them bounded
# so a hung probe fails the control instead of stalling the suite.
FULL_PATH_TIMEOUT_SECONDS = 2400

# Locked distributions that belong only to the dev/api/openai extras or to the CI
# tool pins. None of them is in the wheel's declared runtime closure, so none may
# appear in the isolated environment.
EXTRAS_ONLY_DISTRIBUTIONS = frozenset(
    {
        "pytest",
        "hypothesis",
        "jsonschema",
        "mypy",
        "ruff",
        "fastapi",
        "uvicorn",
        "openai",
        "openai-agents",
        "httpx2",
        "pip-audit",
        "cyclonedx-bom",
    }
)

_GIT_IDENTITY = (
    "-c",
    "user.name=b9-red-control",
    "-c",
    "user.email=b9-red-control@invalid.example",
    "-c",
    "commit.gpgsign=false",
)


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    return completed.stdout.strip()


def _clone_head(source: Path, destination: Path) -> Path:
    """A clean clone of ``source``'s ``HEAD`` that shares its object store."""
    head = _git(source, "rev-parse", "HEAD")
    subprocess.run(
        ["git", "clone", "--quiet", "--shared", "--no-checkout", str(source), str(destination)],
        capture_output=True,
        text=True,
        timeout=600,
        check=True,
    )
    _git(destination, "checkout", "--quiet", "--detach", head)
    assert _git(destination, "status", "--porcelain", "--untracked-files=no") == ""
    return destination


def _build_wheel(repo: Path, wheel_dir: Path) -> Path:
    wheel_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            ".",
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=FULL_PATH_TIMEOUT_SECONDS,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-4000:]
    wheels = sorted(wheel_dir.glob("*.whl"))
    assert len(wheels) == 1, wheels
    return wheels[0]


def _run_script(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Invoke the consumer exactly as CI does, as a real subprocess."""
    child_env = dict(env) if env is not None else dict(os.environ)
    child_env.setdefault("PYTHONHASHSEED", "0")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        env=child_env,
        capture_output=True,
        text=True,
        timeout=FULL_PATH_TIMEOUT_SECONDS,
        check=False,
    )


def _smoke(
    repo: Path,
    wheel_dir: Path,
    work_dir: Path,
    *,
    extra: tuple[str, ...] = (),
    env: dict[str, str] | None = None,
    output: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    output = output or work_dir / "evidence" / "PACKAGING_SMOKE.json"
    completed = _run_script(
        "smoke",
        "--repo",
        str(repo),
        "--wheel-dir",
        str(wheel_dir),
        "--venv-dir",
        str(work_dir / "venv"),
        "--scratch-dir",
        str(work_dir / "scratch"),
        "--output",
        str(output),
        *extra,
        env=env,
    )
    document = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    return completed, document


def _check(
    repo: Path, evidence: Path, wheel_dir: Path, *extra: str
) -> subprocess.CompletedProcess[str]:
    return _run_script(
        "check",
        "--repo",
        str(repo),
        "--evidence",
        str(evidence),
        "--wheel-dir",
        str(wheel_dir),
        *extra,
    )


def _copy_wheel(wheel: Path, wheel_dir: Path) -> Path:
    wheel_dir.mkdir(parents=True, exist_ok=True)
    destination = wheel_dir / wheel.name
    shutil.copyfile(wheel, destination)
    return destination


# --------------------------------------------------------------------------- #
# Shared fixtures: one clean source clone, one honest wheel, one honest run.
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def source_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A clean clone of the candidate ``HEAD``; the real tree is never touched."""
    return _clone_head(ROOT, tmp_path_factory.mktemp("b9-source") / "repo")


@pytest.fixture(scope="session")
def built_wheel(source_repo: Path, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """Build the actual wheel artifact from the candidate source."""
    wheel = _build_wheel(source_repo, tmp_path_factory.mktemp("b9-wheel-dir"))
    return wheel, packaging.sha256_file(wheel)


@dataclass(frozen=True)
class HonestRun:
    completed: subprocess.CompletedProcess[str]
    document: dict[str, Any]
    evidence: Path
    wheel_dir: Path
    work_dir: Path
    source_sha: str
    source_tree: str
    wheel_sha256: str


@pytest.fixture(scope="module")
def honest_run(
    source_repo: Path, built_wheel: tuple[Path, str], tmp_path_factory: pytest.TempPathFactory
) -> HonestRun:
    """The single honest isolated run that every template-only control shares.

    The caller environment is deliberately polluted: ``PYTHONPATH`` points at the
    candidate ``src`` and the caller runs from the repository root. The installation
    must still be what is attested.
    """
    wheel, wheel_sha256 = built_wheel
    root = tmp_path_factory.mktemp("b9-honest")
    wheel_dir = root / "dist"
    _copy_wheel(wheel, wheel_dir)
    work_dir = root / "work"
    source_sha, source_tree = packaging.read_source_identity(source_repo)
    polluted_env = dict(os.environ)
    polluted_env["PYTHONPATH"] = str(source_repo / "src")
    completed, document = _smoke(
        source_repo,
        wheel_dir,
        work_dir,
        extra=(
            "--expect-source-sha",
            source_sha,
            "--expect-source-tree",
            source_tree,
            "--expect-wheel-sha256",
            wheel_sha256,
            "--expect-version",
            CONTRACT.version,
        ),
        env=polluted_env,
    )
    return HonestRun(
        completed=completed,
        document=document,
        evidence=work_dir / "evidence" / "PACKAGING_SMOKE.json",
        wheel_dir=wheel_dir,
        work_dir=work_dir,
        source_sha=source_sha,
        source_tree=source_tree,
        wheel_sha256=wheel_sha256,
    )


@dataclass(frozen=True)
class ForeignCommit:
    repo: Path
    wheel_dir: Path


@pytest.fixture(scope="module")
def undeclared_dependency_commit(
    source_repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> ForeignCommit:
    """A *different* commit whose package imports a locked-but-undeclared package.

    ``jsonschema`` is in ``requirements/lock.txt`` (dev extra) but not in the
    wheel's ``Requires-Dist``. Installing the whole lock would mask the defect; a
    plain ``pip install`` of the wheel would then crash on import.
    """
    root = tmp_path_factory.mktemp("b9-undeclared")
    repo = _clone_head(source_repo, root / "repo")
    init = repo / "src" / "commander_lab" / "__init__.py"
    init.write_text(
        init.read_text(encoding="utf-8") + "\nimport jsonschema  # undeclared runtime import\n",
        encoding="utf-8",
    )
    _git(repo, *_GIT_IDENTITY, "commit", "--quiet", "-am", "b9 red control: undeclared import")
    wheel_dir = root / "dist"
    _build_wheel(repo, wheel_dir)
    return ForeignCommit(repo=repo, wheel_dir=wheel_dir)


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    """A scratch root outside the repository, as the isolation contract requires."""
    root = tmp_path / "b9-work"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_source_proxy_wheel(
    wheel_dir: Path, *, name: str, version: str, proxied_source_root: Path
) -> Path:
    """Build an installable decoy wheel that makes the package importable only from
    the repository source tree.

    This is the realistic supply-chain shape of the defect the isolation contract
    exists to catch: a wheel that installs cleanly and declares the right version,
    yet resolves ``commander_lab`` from the worktree instead of from its own
    payload. A naive "did the import succeed?" smoke would call this a PASS.
    """
    wheel_dir.mkdir(parents=True, exist_ok=True)
    escaped = name.replace("-", "_")
    dist_info = f"{escaped}-{version}.dist-info"
    wheel_path = wheel_dir / f"{escaped}-{version}-py3-none-any.whl"
    records = [
        f"{dist_info}/METADATA",
        f"{dist_info}/WHEEL",
        f"{dist_info}/RECORD",
        "commander_lab_source_proxy.pth",
    ]
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{dist_info}/METADATA",
            "Metadata-Version: 2.1\n"
            f"Name: {name}\n"
            f"Version: {version}\n"
            "Requires-Python: >=3.12\n"
            "Requires-Dist: pydantic<3,>=2.10\n"
            "Requires-Dist: openpyxl<4,>=3.1\n"
            "Requires-Dist: PyYAML<7,>=6.0\n"
            "Requires-Dist: typer<1,>=0.15\n"
            "\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: b9-red-control\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        archive.writestr("commander_lab_source_proxy.pth", f"{proxied_source_root}\n")
        archive.writestr(
            f"{dist_info}/RECORD",
            "".join(f"{entry},,\n" for entry in records),
        )
    return wheel_path


def _mutated_pyproject(
    destination: Path,
    *,
    extra_script: str | None = None,
    retarget: tuple[str, str] | None = None,
) -> Path:
    """Copy the live pyproject, optionally declaring or retargeting an entrypoint."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if extra_script is not None:
        marker = f"{next(iter(CONTRACT.scripts))} ="
        assert marker in text, marker
        text = text.replace(
            marker,
            f'{extra_script} = "commander_lab.cli.main:app"\n{marker}',
            1,
        )
    if retarget is not None:
        script_name, new_target = retarget
        line = f'{script_name} = "{CONTRACT.scripts[script_name]}"'
        assert line in text, line
        text = text.replace(line, f'{script_name} = "{new_target}"', 1)
    destination.write_text(text, encoding="utf-8")
    return destination


# --------------------------------------------------------------------------- #
# Positive control
# --------------------------------------------------------------------------- #


def test_positive_control_installs_imports_and_runs_every_declared_entrypoint(
    honest_run: HonestRun, source_repo: Path, built_wheel: tuple[Path, str]
) -> None:
    """A real wheel from the candidate source must PASS the whole consumer path."""
    wheel, wheel_sha256 = built_wheel
    completed, document = honest_run.completed, honest_run.document

    assert completed.returncode == EXIT_PASS, completed.stdout + completed.stderr
    assert document["overall_classification"] == "PASS"
    assert document["reasons"] == []
    assert document["schema_version"] == packaging.SCHEMA_VERSION
    assert document["generated_by"] == packaging.GENERATED_BY
    # Bound to the exact candidate, a clean tree and the exact artifact.
    assert document["source_sha"] == honest_run.source_sha
    assert document["source_tree"] == honest_run.source_tree
    assert document["source_working_tree_clean"] is True
    assert document["wheel_filename"] == wheel.name
    assert document["wheel_sha256"] == wheel_sha256
    assert document["wheel_sha256"] == packaging.sha256_file(honest_run.wheel_dir / wheel.name)
    binding = document["wheel_source_binding"]
    assert binding["status"] == "PASS"
    assert binding["compared_files"] == len(
        _git(source_repo, "ls-files", "--", CONTRACT.source_root).splitlines()
    )
    assert (binding["different"], binding["extra"], binding["missing"]) == (0, 0, 0)
    assert document["package_name"] == CONTRACT.name
    assert document["package_version"] == CONTRACT.version
    assert document["install_source"] == "wheel"
    assert document["python_version"] == sys.version.split()[0]
    # Installed from the wheel artifact, never an editable install or a directory.
    install = document["install"]
    assert install["install_source"] == "wheel"
    assert install["direct_url_sha256"] == wheel_sha256
    assert install["direct_url_filename"] == wheel.name
    assert install["index_access"] == "disabled"
    assert "--no-index" in install["project_install_command"]
    assert "--no-deps" not in install["project_install_command"]
    assert install["editable"] is False
    assert install["dependency_lock_sha256"] == packaging.sha256_file(DEPENDENCY_LOCK)
    assert install["wheelhouse"]["every_file_lock_pinned_and_hash_listed"] is True
    assert "--require-hashes" in install["dependency_provisioning_command"]
    # The import came from the installation, not from the worktree.
    assert document["installed_import"]["status"] == "PASS"
    assert document["installed_import"]["resolved_in_isolated_environment"] is True
    assert document["installed_import"]["module"] == packaging.DEFAULT_IMPORT_MODULE
    assert document["installed_import"]["module_file_relative_to_purelib"].startswith(
        "commander_lab/"
    )
    # Every officially declared console entrypoint ran from the installation.
    assert set(document["cli_entrypoint_results"]) == set(CONTRACT.scripts)
    for name, record in document["cli_entrypoint_results"].items():
        assert record["status"] == "PASS", (name, record)
        assert record["returncode"] == 0, (name, record)
        assert record["argument"] == packaging.CLI_SMOKE_ARGUMENT
        assert record["installed_target"] == CONTRACT.scripts[name]
    # Only the wheel's declared runtime closure was installed, at the lock pins.
    closure = document["dependency_closure"]
    assert closure["status"] == "PASS"
    assert closure["runtime_requirements_satisfied"], closure
    installed = set(closure["installed_distributions"])
    added = installed - set(closure["baseline_distributions"]) - {CONTRACT.normalized_name}
    assert added == set(closure["closure"]), (added, closure["closure"])
    assert not installed & EXTRAS_ONLY_DISTRIBUTIONS, installed & EXTRAS_ONLY_DISTRIBUTIONS
    pins = packaging.read_dependency_lock(DEPENDENCY_LOCK)
    for name, version in closure["closure"].items():
        assert pins[name][0] == version, (name, version)
    # No absolute temporary or repository path is used as a semantic identity.
    rendered = json.dumps(document)
    assert str(honest_run.work_dir) not in rendered
    assert str(source_repo) not in rendered
    assert "<repository>" in rendered

    checked = _check(
        source_repo,
        honest_run.evidence,
        honest_run.wheel_dir,
        "--expect-source-sha",
        honest_run.source_sha,
        "--expect-wheel-sha256",
        wheel_sha256,
    )
    assert checked.returncode == EXIT_PASS, checked.stdout + checked.stderr


def test_source_tree_exposure_in_the_ambient_environment_cannot_substitute_for_the_installation(
    honest_run: HonestRun,
) -> None:
    """A polluted caller environment must not be mistaken for the install.

    The honest run is executed with ``PYTHONPATH`` pointed at the candidate ``src``
    from the repository root. It still passes *and* still attests the installation,
    which is what makes the provenance guard meaningful: it is not red-only.
    """
    document = honest_run.document
    assert honest_run.completed.returncode == EXIT_PASS
    environment = document["environment"]
    assert environment["pythonpath_in_probe_environment"] is False
    assert environment["pythonhome_in_probe_environment"] is False
    assert environment["python_isolated_flag"] == 1
    assert environment["include_system_site_packages"] is False
    assert environment["created_by_this_run"] is True
    assert environment["sys_prefix_is_isolated_environment"] is True
    assert document["installed_import"]["resolved_in_isolated_environment"] is True


# --------------------------------------------------------------------------- #
# P1-1: undeclared runtime dependencies are not masked by the lock
# --------------------------------------------------------------------------- #


def test_red_control_undeclared_but_locked_dependency_import_fails_closed(
    undeclared_dependency_commit: ForeignCommit, work_dir: Path
) -> None:
    """A wheel importing a locked package it does not declare must FAIL.

    The source binding is satisfied (the smoke runs against the very commit the
    wheel was built from), so the failure is the installed import, not binding.
    """
    completed, document = _smoke(
        undeclared_dependency_commit.repo, undeclared_dependency_commit.wheel_dir, work_dir
    )
    assert completed.returncode == EXIT_FAIL, completed.stdout + completed.stderr
    assert document["overall_classification"] == "FAIL"
    assert document["reasons"] == ["installed_import_failed:ModuleNotFoundError"]
    assert document["wheel_source_binding"]["status"] == "PASS"
    installed = set(document["dependency_closure"]["installed_distributions"])
    assert "jsonschema" not in installed
    assert not installed & EXTRAS_ONLY_DISTRIBUTIONS
    checked = _check(
        undeclared_dependency_commit.repo,
        work_dir / "evidence" / "PACKAGING_SMOKE.json",
        undeclared_dependency_commit.wheel_dir,
    )
    assert checked.returncode == EXIT_FAIL
    assert "recorded_classification_not_pass:FAIL" in checked.stderr


# --------------------------------------------------------------------------- #
# P2-2: the wheel is bound to the clean source tree at HEAD
# --------------------------------------------------------------------------- #


def test_red_control_wheel_built_from_another_commit_fails_closed(
    undeclared_dependency_commit: ForeignCommit, source_repo: Path, work_dir: Path
) -> None:
    completed, document = _smoke(source_repo, undeclared_dependency_commit.wheel_dir, work_dir)
    assert completed.returncode == EXIT_FAIL, completed.stdout + completed.stderr
    assert document["reasons"] == [
        "wheel_payload_differs_from_source:different=1,extra=0,missing=0"
    ]
    assert not (work_dir / "venv").exists(), "an unbound wheel must never be installed"


def test_red_control_dirty_working_tree_fails_closed(
    source_repo: Path, built_wheel: tuple[Path, str], tmp_path: Path, work_dir: Path
) -> None:
    repo = _clone_head(source_repo, tmp_path / "dirty-repo")
    init = repo / "src" / "commander_lab" / "__init__.py"
    init.write_text(init.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
    wheel_dir = tmp_path / "dist"
    _copy_wheel(built_wheel[0], wheel_dir)
    completed, document = _smoke(repo, wheel_dir, work_dir)
    assert completed.returncode == EXIT_FAIL
    assert document["reasons"] == ["source_working_tree_dirty:tracked_changes=1"]
    assert not (work_dir / "venv").exists()


def test_red_control_source_tree_proxy_wheel_is_rejected_before_install(
    source_repo: Path, work_dir: Path, tmp_path: Path
) -> None:
    """A wheel that only proxies imports to the worktree must never PASS.

    The decoy installs cleanly, declares the current version, and would make
    ``import commander_lab`` genuinely succeed — so a naive import smoke would call
    this a PASS. Its payload is not the source tree, so it is killed before it is
    ever installed. The import-provenance guard behind it is proven separately.
    """
    wheel_dir = tmp_path / "dist"
    _write_source_proxy_wheel(
        wheel_dir,
        name=CONTRACT.name,
        version=CONTRACT.version,
        proxied_source_root=source_repo / "src",
    )
    completed, document = _smoke(source_repo, wheel_dir, work_dir)
    assert completed.returncode == EXIT_FAIL, completed.stdout + completed.stderr
    assert document["overall_classification"] == "FAIL"
    assert len(document["reasons"]) == 1
    assert document["reasons"][0].startswith("wheel_payload_has_files_not_in_source:")
    assert not (work_dir / "venv").exists()


def test_import_provenance_guard_rejects_a_source_tree_import(tmp_path: Path) -> None:
    """Behind the binding, the probe itself refuses an import resolved via the tree."""
    venv_dir = tmp_path / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(venv_dir)],
        capture_output=True,
        text=True,
        timeout=600,
        check=True,
    )
    site_packages = packaging._venv_site_packages(venv_dir)
    (site_packages / "commander_lab_source_proxy.pth").write_text(
        f"{ROOT / 'src'}\n", encoding="utf-8"
    )
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    with pytest.raises(packaging._Classification) as failure:
        packaging.run_installed_probe(
            venv_dir,
            module_name=packaging.DEFAULT_IMPORT_MODULE,
            distribution=CONTRACT.normalized_name,
            forbidden_roots=[ROOT, ROOT / "src"],
            scratch_dir=scratch,
        )
    assert failure.value.classification == "FAIL"
    assert failure.value.code == "source_tree_leaked_onto_isolated_sys_path:entries=1"


# --------------------------------------------------------------------------- #
# P2-1: stale evidence never survives an early failure
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EarlyFailure:
    """How to provoke one early smoke failure: argument overrides, then the outcome."""

    expected_reason: str
    expected_exit: int
    wheel_dir: str | None = None
    scratch_dir: str | None = None
    extra: tuple[str, ...] = ()


def _early_failures(repo: Path, tmp: Path) -> dict[str, EarlyFailure]:
    return {
        "missing_wheel": EarlyFailure(
            "project_wheel_missing:commander-playtest-lab",
            EXIT_FAIL,
            wheel_dir=str(tmp / "empty-dist"),
        ),
        "digest_mismatch": EarlyFailure(
            "wheel_digest_mismatch:", EXIT_FAIL, extra=("--expect-wheel-sha256", "0" * 64)
        ),
        "contract_unreadable": EarlyFailure(
            "package_contract_unreadable:FileNotFoundError",
            EXIT_UNKNOWN,
            extra=("--pyproject", str(tmp / "absent-pyproject.toml")),
        ),
        "lock_missing": EarlyFailure(
            "dependency_lock_missing:absent-lock.txt",
            EXIT_FAIL,
            extra=("--dependency-lock", str(tmp / "absent-lock.txt")),
        ),
        "scratch_dir_inside_repository": EarlyFailure(
            "scratch_dir_inside_repository", EXIT_FAIL, scratch_dir=str(repo / "b9-scratch")
        ),
        "source_binding_mismatch": EarlyFailure(
            "source_tree_mismatch:", EXIT_FAIL, extra=("--expect-source-tree", "1" * 40)
        ),
    }


_EARLY_FAILURE_IDS = sorted(_early_failures(Path("/"), Path("/")))


@pytest.mark.parametrize("case", _EARLY_FAILURE_IDS)
def test_red_control_stale_pass_evidence_never_survives_an_early_failure(
    honest_run: HonestRun, source_repo: Path, tmp_path: Path, work_dir: Path, case: str
) -> None:
    """A pre-existing PASS document is replaced by FAIL evidence, never left behind."""
    failure = _early_failures(source_repo, tmp_path)[case]
    output = tmp_path / "evidence" / "PACKAGING_SMOKE.json"
    output.parent.mkdir(parents=True)
    shutil.copyfile(honest_run.evidence, output)
    (tmp_path / "empty-dist").mkdir()

    completed = _run_script(
        "smoke",
        "--repo",
        str(source_repo),
        "--wheel-dir",
        failure.wheel_dir or str(honest_run.wheel_dir),
        "--venv-dir",
        str(work_dir / "venv"),
        "--scratch-dir",
        failure.scratch_dir or str(work_dir / "scratch"),
        "--output",
        str(output),
        *failure.extra,
    )
    assert completed.returncode == failure.expected_exit, completed.stdout + completed.stderr
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["overall_classification"] != "PASS"
    assert len(document["reasons"]) == 1
    assert document["reasons"][0].startswith(failure.expected_reason), document["reasons"]
    assert str(tmp_path) not in document["reasons"][0]
    assert not (work_dir / "venv").exists()
    assert not (source_repo / "b9-scratch").exists()

    checked = _check(source_repo, output, honest_run.wheel_dir)
    assert checked.returncode == EXIT_FAIL
    assert "recorded_classification_not_pass" in checked.stderr


# --------------------------------------------------------------------------- #
# Wheel selection and digest binding
# --------------------------------------------------------------------------- #


def test_red_control_ambiguous_project_wheels_fail_instead_of_first_file_selection(
    built_wheel: tuple[Path, str], source_repo: Path, work_dir: Path, tmp_path: Path
) -> None:
    wheel, _ = built_wheel
    wheel_dir = tmp_path / "dist"
    _copy_wheel(wheel, wheel_dir)
    # A second, different artifact for the same project distribution.
    decoy = wheel_dir / f"{wheel.name.split('-')[0]}-9.99.9-py3-none-any.whl"
    decoy.write_bytes(wheel.read_bytes())

    completed, document = _smoke(source_repo, wheel_dir, work_dir)
    assert completed.returncode == EXIT_FAIL
    assert "project_wheel_ambiguous" in completed.stderr
    assert wheel.name in completed.stderr
    assert decoy.name in completed.stderr
    assert document["reasons"][0].startswith("project_wheel_ambiguous:")
    assert not (work_dir / "venv").exists(), (
        "no environment may be created for an ambiguous wheel set"
    )


def test_red_control_wheel_tampered_after_binding_is_detected_by_the_evidence_consumer(
    honest_run: HonestRun, source_repo: Path, tmp_path: Path
) -> None:
    """Bind evidence to a real wheel, then mutate the artifact behind the evidence."""
    wheel_dir = tmp_path / "dist"
    shutil.copytree(honest_run.wheel_dir, wheel_dir)
    checked = _check(source_repo, honest_run.evidence, wheel_dir)
    assert checked.returncode == EXIT_PASS, checked.stdout + checked.stderr

    artifact = wheel_dir / honest_run.document["wheel_filename"]
    payload = artifact.read_bytes()
    artifact.write_bytes(payload[:-1] + bytes([payload[-1] ^ 0xFF]))

    reverified = _check(source_repo, honest_run.evidence, wheel_dir)
    assert reverified.returncode == EXIT_FAIL
    assert "artifact_reverification_digest_mismatch" in reverified.stderr
    assert "artifact_reverification_install_digest_mismatch" in reverified.stderr


def test_red_control_source_identity_binding_mismatch_fails_closed(
    honest_run: HonestRun, source_repo: Path, work_dir: Path
) -> None:
    completed, document = _smoke(
        source_repo, honest_run.wheel_dir, work_dir, extra=("--expect-source-sha", "0" * 40)
    )
    assert completed.returncode == EXIT_FAIL
    assert document["reasons"] == [
        f"source_sha_mismatch:expected={'0' * 40} observed={honest_run.source_sha}"
    ]


# --------------------------------------------------------------------------- #
# Package/version mismatch and entrypoint contract (full consumer path)
# --------------------------------------------------------------------------- #


def test_red_control_package_version_mismatch_fails_after_isolated_install(
    honest_run: HonestRun, source_repo: Path, work_dir: Path
) -> None:
    completed, document = _smoke(
        source_repo, honest_run.wheel_dir, work_dir, extra=("--expect-version", "9.99.99")
    )
    assert completed.returncode == EXIT_FAIL
    assert document["reasons"] == [
        f"package_version_mismatch:expected=9.99.99 installed={CONTRACT.version}"
    ]
    # The mismatch was detected only after a real isolated install of the wheel.
    assert document["install"]["direct_url_sha256"] == honest_run.wheel_sha256
    assert document["package_version"] == CONTRACT.version
    assert document["expected_bindings"]["package_version"] == "9.99.99"
    assert document["installed_import"] == {
        "status": "FAIL",
        "module": packaging.DEFAULT_IMPORT_MODULE,
    }
    assert document["overall_classification"] == "FAIL"


def test_red_control_missing_or_retargeted_cli_entrypoint_fails_after_install(
    honest_run: HonestRun, source_repo: Path, work_dir: Path, tmp_path: Path
) -> None:
    """A declared-but-absent script and a script whose installed target differs."""
    names = list(CONTRACT.scripts)
    retargeted = names[-1]
    ghost = tmp_path / "pyproject-with-ghost-entrypoint.toml"
    _mutated_pyproject(
        ghost,
        extra_script="commander-lab-ghost-entrypoint",
        retarget=(retargeted, "commander_lab.cli.main:not_the_installed_target"),
    )

    completed, document = _smoke(
        source_repo, honest_run.wheel_dir, work_dir, extra=("--pyproject", str(ghost))
    )
    assert completed.returncode == EXIT_FAIL
    broken = sorted(
        [
            f"{retargeted}:cli_entrypoint_target_mismatch",
            "commander-lab-ghost-entrypoint:cli_entrypoint_missing",
        ]
    )
    assert document["reasons"] == [f"cli_entrypoint_smoke_failed:{','.join(broken)}"]
    results = document["cli_entrypoint_results"]
    assert results["commander-lab-ghost-entrypoint"]["status"] == "FAIL"
    assert results["commander-lab-ghost-entrypoint"]["reason"] == "cli_entrypoint_missing"
    assert results[retargeted]["installed_target"] == CONTRACT.scripts[retargeted]
    for name in names[:-1]:
        assert results[name]["status"] == "PASS", (name, results[name])
    assert document["installed_import"]["status"] == "PASS"


def test_editable_install_markers_are_rejected_by_the_isolation_contract(tmp_path: Path) -> None:
    """Neither an editable marker nor an editable ``direct_url`` record is accepted."""
    wheel_name = f"{CONTRACT.name.replace('-', '_')}-{CONTRACT.version}-py3-none-any.whl"
    venv_dir = tmp_path / "venv"
    site_packages = venv_dir / "lib" / "python3.12" / "site-packages"
    site_packages.mkdir(parents=True)
    (venv_dir / "bin").mkdir()
    (venv_dir / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    dist_info = site_packages / f"{CONTRACT.name.replace('-', '_')}-{CONTRACT.version}.dist-info"
    dist_info.mkdir()
    (dist_info / "direct_url.json").write_text(
        json.dumps(
            {
                "url": f"file://{ROOT}",
                "dir_info": {"editable": True},
            }
        ),
        encoding="utf-8",
    )

    editable_marker = site_packages / f"__editable__.{CONTRACT.name.replace('-', '_')}-1.pth"
    editable_marker.write_text(f"{ROOT / 'src'}\n", encoding="utf-8")
    with pytest.raises(packaging._Classification) as marker_failure:
        packaging.verify_install_source(venv_dir, tmp_path / wheel_name, "0" * 64, CONTRACT)
    assert marker_failure.value.classification == "FAIL"
    assert marker_failure.value.code.startswith("editable_install_detected_in_isolated_environment")

    editable_marker.unlink()
    with pytest.raises(packaging._Classification) as dir_info_failure:
        packaging.verify_install_source(venv_dir, tmp_path / wheel_name, "0" * 64, CONTRACT)
    assert dir_info_failure.value.classification == "FAIL"
    assert dir_info_failure.value.code == "install_source_is_directory_not_wheel"


def test_preexisting_isolated_environment_is_rejected(work_dir: Path) -> None:
    venv_dir = work_dir / "venv"
    venv_dir.mkdir(parents=True)
    with pytest.raises(packaging._Classification) as failure:
        packaging.create_isolated_environment(venv_dir, scratch_dir=work_dir)
    assert failure.value.classification == "FAIL"
    assert failure.value.code == "isolated_environment_preexisting:venv"


def test_wheelhouse_files_must_be_lock_pinned_and_hash_listed(
    built_wheel: tuple[Path, str], tmp_path: Path
) -> None:
    pins = packaging.read_dependency_lock(DEPENDENCY_LOCK)
    assert len(pins) >= 4
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    name, (version, _) = next(iter(sorted(pins.items())))
    forged = wheelhouse / f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
    forged.write_bytes(b"not the locked artifact")
    with pytest.raises(packaging._Classification) as failure:
        packaging.verify_wheelhouse(wheelhouse, pins)
    assert failure.value.code == f"wheelhouse_wheel_hash_not_in_lock:{name}"

    forged.unlink()
    _copy_wheel(built_wheel[0], wheelhouse)
    with pytest.raises(packaging._Classification) as unpinned:
        packaging.verify_wheelhouse(wheelhouse, pins)
    assert unpinned.value.code == f"wheelhouse_wheel_not_in_lock:{CONTRACT.normalized_name}"


# --------------------------------------------------------------------------- #
# Evidence consumer: missing, malformed, UNKNOWN, forged or unbound evidence
# --------------------------------------------------------------------------- #


def test_red_control_missing_evidence_file_never_passes(source_repo: Path, tmp_path: Path) -> None:
    checked = _check(source_repo, tmp_path / "absent.json", tmp_path)
    assert checked.returncode == EXIT_FAIL
    assert "packaging evidence missing" in checked.stderr


def test_red_control_malformed_evidence_never_passes(source_repo: Path, tmp_path: Path) -> None:
    truncated = tmp_path / "truncated.json"
    truncated.write_text(
        '{"schema_version": "packaging-smoke-2.0.0", "source_sha":', encoding="utf-8"
    )
    checked = _check(source_repo, truncated, tmp_path)
    assert checked.returncode == EXIT_FAIL
    assert "unreadable" in checked.stderr

    not_object = tmp_path / "list.json"
    not_object.write_text("[]", encoding="utf-8")
    checked = _check(source_repo, not_object, tmp_path)
    assert checked.returncode == EXIT_FAIL
    assert "not a JSON object" in checked.stderr


def test_red_control_unknown_or_failed_classification_is_never_promoted_to_pass(
    honest_run: HonestRun, source_repo: Path, tmp_path: Path
) -> None:
    for classification in ("UNKNOWN", "FAIL", "PARTIAL", "NOT_RUN"):
        broken = tmp_path / f"classification-{classification}.json"
        mutated = copy.deepcopy(honest_run.document)
        mutated["overall_classification"] = classification
        broken.write_text(json.dumps(mutated), encoding="utf-8")
        checked = _check(source_repo, broken, honest_run.wheel_dir)
        assert checked.returncode == EXIT_FAIL, classification
        assert f"recorded_classification_not_pass:{classification}" in checked.stderr


def _set(path: tuple[str, ...], value: Any) -> Callable[[dict[str, Any]], None]:
    def mutate(document: dict[str, Any]) -> None:
        target = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return mutate


def _delete(key: str) -> Callable[[dict[str, Any]], None]:
    def mutate(document: dict[str, Any]) -> None:
        del document[key]

    return mutate


def _cli_nonzero(document: dict[str, Any]) -> None:
    name = next(iter(CONTRACT.scripts))
    for record in document["cli_entrypoints"]:
        if record["name"] == name:
            record["returncode"] = 1
    document["cli_entrypoint_results"][name]["returncode"] = 1


def _drop_cli_record(document: dict[str, Any]) -> None:
    name = next(iter(CONTRACT.scripts))
    document["cli_entrypoints"] = [
        record for record in document["cli_entrypoints"] if record["name"] != name
    ]
    del document["cli_entrypoint_results"][name]


def _undeclared_install(document: dict[str, Any]) -> None:
    document["dependency_closure"]["installed_distributions"]["jsonschema"] = "4.26.0"


def _contract_script_forged(document: dict[str, Any]) -> None:
    document["package_contract"]["declared_scripts"] = {}


_FORGERIES: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
    (
        "source_sha_not_head",
        _set(("source_sha",), "0" * 40),
        "evidence_source_sha_not_repository_head",
    ),
    (
        "source_tree_not_head_tree",
        _set(("source_tree",), "1" * 40),
        "evidence_source_tree_not_repository_tree",
    ),
    (
        "direct_url_digest_contradicts_wheel",
        _set(("install", "direct_url_sha256"), "f" * 64),
        "install_direct_url_sha256_not_wheel_sha256",
    ),
    ("editable_install", _set(("install", "editable"), True), "install_editable_not_false"),
    (
        "install_record_from_directory",
        _set(("install", "install_source"), "directory"),
        "install_record_source_not_wheel",
    ),
    (
        "top_level_install_from_directory",
        _set(("install_source",), "directory"),
        "install_source_not_wheel:directory",
    ),
    (
        "index_access_enabled",
        _set(("install", "index_access"), "enabled"),
        "install_index_access_not_disabled",
    ),
    (
        "system_site_packages_inherited",
        _set(("environment", "include_system_site_packages"), True),
        "environment_invariant_violated:include_system_site_packages",
    ),
    (
        "pythonpath_in_probe",
        _set(("environment", "pythonpath_in_probe_environment"), True),
        "environment_invariant_violated:pythonpath_in_probe_environment",
    ),
    (
        "pass_with_reasons",
        _set(("reasons",), ["installed_import_failed:ModuleNotFoundError"]),
        "pass_recorded_with_failure_reasons",
    ),
    (
        "expected_binding_mismatch",
        _set(("expected_bindings", "source_tree"), "1" * 40),
        "expected_binding_mismatch:source_tree",
    ),
    (
        "missing_cli_entrypoints",
        _delete("cli_entrypoints"),
        "evidence_required_key_missing:cli_entrypoints",
    ),
    ("missing_generated_by", _delete("generated_by"), "evidence_required_key_missing:generated_by"),
    ("missing_wheel_sha256", _delete("wheel_sha256"), "evidence_required_key_missing:wheel_sha256"),
    ("missing_reasons", _delete("reasons"), "evidence_required_key_missing:reasons"),
    (
        "missing_installed_import",
        _delete("installed_import"),
        "evidence_required_key_missing:installed_import",
    ),
    (
        "missing_package_contract",
        _delete("package_contract"),
        "evidence_required_key_missing:package_contract",
    ),
    ("unexpected_key", _set(("smuggled",), True), "evidence_unexpected_key:smuggled"),
    ("foreign_generator", _set(("generated_by",), "elsewhere"), "generated_by_not_this_consumer"),
    (
        "contract_forged",
        _contract_script_forged,
        "package_contract_not_the_current_contract",
    ),
    (
        "cli_nonzero_exit",
        _cli_nonzero,
        f"cli_entrypoint_nonzero_exit:{next(iter(CONTRACT.scripts))}",
    ),
    (
        "cli_record_missing",
        _drop_cli_record,
        f"cli_entrypoint_result_missing:{next(iter(CONTRACT.scripts))}",
    ),
    (
        "undeclared_distribution_installed",
        _undeclared_install,
        "dependency_closure_not_the_installed_set",
    ),
    (
        "binding_not_passed",
        _set(("wheel_source_binding", "different"), 1),
        "wheel_source_binding_not_passed",
    ),
    (
        "forged_import_provenance",
        _set(("installed_import", "resolved_in_isolated_environment"), False),
        "installed_import_not_proven_isolated",
    ),
    (
        "stale_version",
        _set(("package_version",), "0.0.1"),
        "package_version_not_the_current_declared_version",
    ),
    (
        "lock_digest_forged",
        _set(("install", "dependency_lock_sha256"), "e" * 64),
        "dependency_lock_digest_not_the_current_lock",
    ),
    (
        "dirty_tree_claimed_clean_false",
        _set(("source_working_tree_clean",), False),
        "evidence_working_tree_not_clean",
    ),
    (
        "python_version_forged",
        _set(("python_version",), "2.7.18"),
        "python_version_not_the_checking_interpreter",
    ),
]


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [pytest.param(mutate, code, id=name) for name, mutate, code in _FORGERIES],
)
def test_red_control_check_re_adjudicates_forged_or_contradictory_pass_evidence(
    honest_run: HonestRun,
    source_repo: Path,
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
    expected_code: str,
) -> None:
    """A PASS document with one forged field must be failed by ``check``."""
    assert honest_run.document["overall_classification"] == "PASS"
    forged = copy.deepcopy(honest_run.document)
    mutate(forged)
    forged_path = tmp_path / "forged.json"
    forged_path.write_text(json.dumps(forged), encoding="utf-8")
    checked = _check(source_repo, forged_path, honest_run.wheel_dir)
    assert checked.returncode == EXIT_FAIL, checked.stdout + checked.stderr
    assert expected_code in checked.stderr, checked.stderr


def test_red_control_evidence_bound_to_a_different_candidate_is_rejected(
    honest_run: HonestRun, source_repo: Path, undeclared_dependency_commit: ForeignCommit
) -> None:
    checked = _check(
        source_repo, honest_run.evidence, honest_run.wheel_dir, "--expect-source-sha", "0" * 40
    )
    assert checked.returncode == EXIT_FAIL
    assert "evidence_source_sha_not_the_expected_candidate" in checked.stderr

    # The same honest evidence, checked against another commit, is not current.
    checked = _check(undeclared_dependency_commit.repo, honest_run.evidence, honest_run.wheel_dir)
    assert checked.returncode == EXIT_FAIL
    assert "evidence_source_sha_not_repository_head" in checked.stderr
    assert "artifact_reverification_not_bound_to_source:wheel_payload_differs_from_source" in (
        checked.stderr
    )


# --------------------------------------------------------------------------- #
# Unit-level contract guards for the pure decisions
# --------------------------------------------------------------------------- #


def test_wheel_selection_requires_exactly_one_project_wheel(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    with pytest.raises(packaging._Classification) as missing:
        packaging.select_project_wheel(wheel_dir, CONTRACT)
    assert missing.value.code.startswith("project_wheel_missing")

    (wheel_dir / "other_package-1.0-py3-none-any.whl").write_bytes(b"")
    with pytest.raises(packaging._Classification) as still_missing:
        packaging.select_project_wheel(wheel_dir, CONTRACT)
    assert still_missing.value.code.startswith("project_wheel_missing")

    project = wheel_dir / f"{CONTRACT.name.replace('-', '_')}-{CONTRACT.version}-py3-none-any.whl"
    project.write_bytes(b"only-one")
    assert packaging.select_project_wheel(wheel_dir, CONTRACT) == project

    (wheel_dir / f"{CONTRACT.name.replace('-', '_')}-0.1-py3-none-any.whl").write_bytes(b"")
    with pytest.raises(packaging._Classification) as ambiguous:
        packaging.select_project_wheel(wheel_dir, CONTRACT)
    assert ambiguous.value.code.startswith("project_wheel_ambiguous")


def test_distribution_name_normalisation_matches_wheel_filename_spelling() -> None:
    assert (
        packaging.normalize_distribution_name("Commander_Playtest.Lab") == "commander-playtest-lab"
    )
    assert (
        packaging.normalize_distribution_name("commander-playtest-lab") == CONTRACT.normalized_name
    )


def test_package_contract_is_read_from_the_live_pyproject() -> None:
    assert CONTRACT.name == "commander-playtest-lab"
    assert CONTRACT.version
    assert CONTRACT.source_root == "src"
    assert CONTRACT.scripts, (
        "the project must declare console scripts for the smoke to prove anything"
    )
    for script_name, target in CONTRACT.scripts.items():
        module_name, separator, attribute = target.partition(":")
        assert separator == ":", (script_name, target)
        assert module_name and attribute, (script_name, target)
        module_path = ROOT / "src" / (module_name.replace(".", "/") + ".py")
        assert module_path.is_file(), (script_name, target)


# --------------------------------------------------------------------------- #
# CI trust boundary: the required quality context is extended, never weakened
# --------------------------------------------------------------------------- #


def _ci() -> dict[str, Any]:
    import yaml

    loaded: dict[str, Any] = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    return loaded


def test_packaging_smoke_runs_inside_the_required_quality_context() -> None:
    workflow = _ci()
    quality = workflow["jobs"]["quality"]
    names = [step.get("name") for step in quality["steps"]]
    assert "Build wheel" in names, names
    smoke_index = next(
        index
        for index, name in enumerate(names)
        if name == "Packaging smoke (isolated wheel install, import and CLI)"
    )
    # It runs after the wheel it consumes is actually built.
    assert smoke_index > names.index("Build wheel")
    smoke = quality["steps"][smoke_index]
    assert smoke["if"] == "${{ success() || failure() }}"
    assert "continue-on-error" not in smoke
    assert "scripts/verify_packaging_smoke.py smoke" in smoke["run"]
    assert "--wheel-dir dist" in smoke["run"]
    assert "artifacts/quality/PACKAGING_SMOKE.json" in smoke["run"]
    assert "$RUNNER_TEMP" in smoke["run"], (
        "the isolated environment must live outside the workspace"
    )
    assert "|| true" not in smoke["run"]
    assert "continue-on-error: true" not in CI_WORKFLOW.read_text(encoding="utf-8")


def test_packaging_evidence_is_independently_rechecked_and_uploaded() -> None:
    workflow = _ci()
    quality = workflow["jobs"]["quality"]
    names = [step.get("name") for step in quality["steps"]]
    check_index = names.index("Packaging smoke evidence check")
    check = quality["steps"][check_index]
    assert check["if"] == "${{ success() || failure() }}"
    assert "continue-on-error" not in check
    assert "scripts/verify_packaging_smoke.py check" in check["run"]
    assert "--wheel-dir dist" in check["run"]
    assert "--repo ." in check["run"]
    assert "|| true" not in check["run"]
    upload = quality["steps"][-1]
    assert "artifacts/quality/" in upload["with"]["path"]
    assert upload["with"]["name"] == "ci-evidence"


def test_existing_quality_gates_are_preserved() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    workflow = _ci()
    quality = workflow["jobs"]["quality"]
    names = [step.get("name") for step in quality["steps"]]
    for preserved in (
        "Install project and quality tools",
        "Ruff lint",
        "Ruff format",
        "Mypy strict",
        "Test suite",
        "Compile",
        "Secret-pattern scan",
        "Build wheel",
    ):
        assert preserved in names, preserved
    assert "python -m pip wheel --no-deps --wheel-dir dist ." in text
    assert "Potential secret material found" in text
    # Required contexts themselves are unchanged in name and job identity.
    assert set(workflow["jobs"]) == {"quality", "security"}
    for context in ("quality", "security"):
        assert workflow["jobs"][context].get("if") is None
        assert workflow["jobs"][context].get("needs") is None
        assert workflow["jobs"][context].get("continue-on-error") is None
        assert workflow["jobs"][context].get("name") in (None, context)
        assert workflow["jobs"][context].get("strategy") is None


def test_required_check_static_invariants_still_hold_for_the_candidate() -> None:
    """CI-02's own static policy must report every invariant PASS on this candidate.

    A legitimate required-gate definition change is reported separately as
    ``GATE_DEFINITION_CHANGED_REVIEW_REQUIRED``; that classification is expected
    evidence and is explicitly *not* a reason to weaken this policy.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import verify_required_check_definitions as gate

    head = packaging.read_source_identity(ROOT)[0]
    report = gate.inspect_required_check_definitions(ROOT, head, head)
    non_pass = [item for item in report["invariant_results"] if item["status"] != "PASS"]
    assert non_pass == [], non_pass
    assert "quality.category.package_wheel" in {
        item["id"] for item in report["invariant_results"] if item["status"] == "PASS"
    }
    assert report["candidate_code_executed"] is False
