#!/usr/bin/env python3
"""Deterministic packaging smoke for the built wheel artifact (issue #490).

Wheel *construction* is not packaging evidence. This consumer proves that the
exact wheel the candidate built can be installed into a clean isolated Python
environment and that the *installed* package imports and exposes its officially
supported console entrypoints.

Two independent modes, both fail closed:

``smoke``
    Select exactly one project wheel from a wheel directory, bind it to the
    source SHA/TREE and to its own SHA-256 digest, install it into a freshly
    created virtual environment, prove the install came from the wheel (never an
    editable install, never the source tree, never an index), probe the installed
    package import, probe every declared console entrypoint, and write a small
    machine-readable evidence document.

``check``
    Independently consume a previously written evidence document and re-adjudicate
    it. Missing, truncated, malformed, unbound or ``UNKNOWN`` evidence is never
    promoted to ``PASS``.

Isolation invariants enforced here:

* the wheel set is resolved deterministically: exactly one project wheel, or the
  run fails closed. First-file selection is never used;
* the isolated environment is created by this run and must not pre-exist;
* ``pyvenv.cfg`` must declare ``include-system-site-packages = false``;
* the project is installed with ``--no-index --no-deps`` from the exact wheel
  path, so no dependency is resolved from an arbitrary index at install time;
* dependencies are exactly the wheel's own runtime closure: its non-extra
  ``Requires-Dist`` and theirs, pinned and hashed from the project lock
  (``requirements/lock.txt``) and installed with ``--require-hashes --no-deps``.
  Dev, API and OpenAI extras are never installed, so an undeclared runtime import
  fails the smoke; ``pip check`` then proves the closure complete;
* every file in the wheel equals its blob under ``src/`` at the source commit,
  and every tracked module of a packaged top-level package is in the wheel;
* the installed distribution must record a ``direct_url.json`` wheel archive
  whose SHA-256 equals the wheel digest bound before installing, and no editable
  install marker may exist in the isolated environment;
* the import probe runs the venv interpreter with ``-I`` (which implies ``-E``,
  ``-P`` and ``-s``), with ``PYTHONPATH``/``PYTHONHOME`` removed from the child
  environment, from a working directory outside the repository, and it must prove
  that the imported module resolves inside the venv's own ``purelib`` and that no
  repository path leaked onto ``sys.path``;
* the wheel's own non-extra ``Requires-Dist`` entries must be satisfied by the
  hash-pinned dependency install;
* the source SHA/TREE is re-read after the probes so mid-run source drift fails
  closed instead of producing evidence for a different tree.

No game state, no player data and no credential values are read or recorded, so
the evidence carries no hidden information.
"""

from __future__ import annotations

import argparse
import email.parser
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any, NoReturn

SCHEMA_VERSION = "packaging-smoke-1.1.0"
GENERATED_BY = "scripts/verify_packaging_smoke.py"

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"

EXIT_CODES: dict[str, int] = {PASS: 0, FAIL: 1, UNKNOWN: 3}

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Bounded so a hung entrypoint cannot turn the smoke into a timeout-only result.
DEFAULT_CLI_TIMEOUT_SECONDS = 120
DEFAULT_PROBE_TIMEOUT_SECONDS = 180
DEFAULT_INSTALL_TIMEOUT_SECONDS = 1800

# The minimum import that proves the installed *distribution* is importable: the
# distribution's own top-level package, never a worktree path.
DEFAULT_IMPORT_MODULE = "commander_lab"

# Every declared console script is probed with this argument. Both currently
# declared entrypoints implement it deterministically without external services.
CLI_SMOKE_ARGUMENT = "--help"


class _Classification(Exception):
    """Terminal fail-closed classification with a stable machine-readable code."""

    def __init__(self, code: str, classification: str) -> None:
        super().__init__(code)
        self.code = code
        self.classification = classification


def _fail(code: str, detail: str = "") -> NoReturn:
    raise _Classification(f"{code}:{detail}" if detail else code, FAIL)


def _unknown(code: str, detail: str = "") -> NoReturn:
    raise _Classification(f"{code}:{detail}" if detail else code, UNKNOWN)


# --------------------------------------------------------------------------- #
# Package contract: always read from the project pyproject.toml, never hardcoded.
# --------------------------------------------------------------------------- #


def normalize_distribution_name(name: str) -> str:
    """PEP 503 normalisation, so wheel filename spellings compare equal."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


class PackageContract:
    """The officially supported packaging contract, read from pyproject.toml."""

    def __init__(self, name: str, version: str, scripts: dict[str, str], source: Path) -> None:
        self.name = name
        self.version = version
        self.scripts = dict(sorted(scripts.items()))
        self.source = source

    @property
    def normalized_name(self) -> str:
        return normalize_distribution_name(self.name)

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "normalized_name": self.normalized_name,
            "declared_version": self.version,
            "declared_scripts": dict(self.scripts),
            "contract_source": self.source.name,
        }


def read_package_contract(pyproject: Path) -> PackageContract:
    try:
        document = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _unknown("package_contract_unreadable", str(exc))
    project = document.get("project")
    if not isinstance(project, dict):
        _fail("package_contract_missing_project_table")
    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str) or not name.strip():
        _fail("package_contract_missing_name")
    if not isinstance(version, str) or not version.strip():
        _fail("package_contract_missing_version")
    raw_scripts = project.get("scripts")
    scripts: dict[str, str] = {}
    if isinstance(raw_scripts, dict):
        for script_name, target in raw_scripts.items():
            if isinstance(script_name, str) and isinstance(target, str):
                scripts[script_name] = target
    if not scripts:
        _fail("package_contract_declares_no_console_scripts")
    return PackageContract(name=name, version=version, scripts=scripts, source=pyproject)


# --------------------------------------------------------------------------- #
# Source identity
# --------------------------------------------------------------------------- #


def _git_text(repo: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def read_source_identity(repo: Path) -> tuple[str, str]:
    sha = _git_text(repo, "rev-parse", "HEAD")
    tree = _git_text(repo, "rev-parse", "HEAD^{tree}")
    if sha is None or not SHA_RE.match(sha):
        _unknown("source_sha_not_resolvable")
    if tree is None or not SHA_RE.match(tree):
        _unknown("source_tree_not_resolvable")
    return sha, tree


def assert_source_binding(
    sha: str, tree: str, expected_sha: str | None, expected_tree: str | None
) -> None:
    if expected_sha is not None and expected_sha != sha:
        _fail("source_sha_mismatch", f"expected={expected_sha} observed={sha}")
    if expected_tree is not None and expected_tree != tree:
        _fail("source_tree_mismatch", f"expected={expected_tree} observed={tree}")


# --------------------------------------------------------------------------- #
# Wheel selection and digest binding
# --------------------------------------------------------------------------- #


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        _unknown("artifact_not_readable", str(exc))
    return digest.hexdigest()


def select_project_wheel(wheel_dir: Path, contract: PackageContract) -> Path:
    """Exactly one project wheel, or fail closed. Never first-file selection."""
    if not wheel_dir.is_dir():
        _fail("wheel_directory_missing", wheel_dir.name)
    stems = {
        contract.normalized_name,
        contract.normalized_name.replace("-", "_"),
    }
    candidates = sorted(
        path
        for path in wheel_dir.glob("*.whl")
        if path.is_file() and path.name.split("-", 1)[0].lower() in stems
    )
    if not candidates:
        _fail("project_wheel_missing", contract.normalized_name)
    if len(candidates) > 1:
        _fail("project_wheel_ambiguous", ",".join(path.name for path in candidates))
    return _only(candidates, code="project_wheel_ambiguous")


# --------------------------------------------------------------------------- #
# Isolated environment
# --------------------------------------------------------------------------- #


def _only(items: list[Path], *, code: str) -> Path:
    """Return the single element of ``items``, or fail closed.

    The isolation contract requires a *uniquely* determined environment. An
    ambiguous set is never resolved by taking whichever element happens to sort
    first, because that would silently substitute one interpreter layout or one
    site-packages tree for another and would make the evidence non-reproducible.
    """
    if len(items) != 1:
        _fail(code, str(len(items)))
    return items[0]


def isolated_child_environment() -> dict[str, str]:
    """A child environment with no inherited interpreter path injection."""
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONHASHSEED": "0",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_INPUT": "1",
    }


def _diagnostic_tail(completed: subprocess.CompletedProcess[str], *, limit: int = 600) -> str:
    """A bounded, single-purpose failure excerpt for the step log.

    This is written to stderr only. It is never stored in the evidence document,
    which must not carry absolute temporary paths as semantic identity.
    """
    text = (completed.stderr or completed.stdout or "").strip()
    if not text:
        return "<no diagnostic output>"
    collapsed = " | ".join(line.strip() for line in text.splitlines() if line.strip())
    return collapsed[-limit:]


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    diagnose: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _fail("command_timed_out", command[0])
    except OSError as exc:
        _unknown("command_not_executable", str(exc))
    if diagnose and completed.returncode != 0:
        print(
            f"  [diagnostic] {Path(command[0]).name} exit={completed.returncode}: "
            f"{_diagnostic_tail(completed)}",
            file=sys.stderr,
        )
    return completed


def _under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def venv_bin(venv_dir: Path, program: str) -> Path:
    scripts_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    return scripts_dir / program


def _venv_python(venv_dir: Path) -> Path:
    layouts = sorted(venv_dir.glob("lib/python*/site-packages"))
    if len(layouts) > 1:
        _fail("isolated_environment_layout_ambiguous", str(len(layouts)))
    if layouts:
        suffix = _only(
            layouts, code="isolated_environment_layout_ambiguous"
        ).parent.name.removeprefix("python")
        interpreter = venv_bin(venv_dir, f"python{suffix}")
        if interpreter.is_file():
            return interpreter
    interpreter = venv_bin(venv_dir, "python")
    if interpreter.is_file():
        return interpreter
    _fail("isolated_environment_interpreter_missing")


def _venv_site_packages(venv_dir: Path) -> Path:
    candidates = sorted(venv_dir.glob("lib/python*/site-packages")) or sorted(
        venv_dir.glob("Lib/site-packages")
    )
    return _only(candidates, code="isolated_environment_site_packages_not_uniquely_resolved")


def create_isolated_environment(venv_dir: Path, *, scratch_dir: Path) -> None:
    if venv_dir.exists():
        _fail("isolated_environment_preexisting", venv_dir.name)
    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    completed = _run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        cwd=scratch_dir,
        env=isolated_child_environment(),
        timeout=DEFAULT_INSTALL_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        _fail("isolated_environment_creation_failed", f"exit={completed.returncode}")
    config = venv_dir / "pyvenv.cfg"
    if not config.is_file():
        _fail("isolated_environment_config_missing")
    include_system: str | None = None
    for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
        key, _, value = line.partition("=")
        if key.strip().lower() == "include-system-site-packages":
            include_system = value.strip().lower()
    if include_system != "false":
        _fail("isolated_environment_inherits_system_site_packages", str(include_system))
    if not venv_bin(venv_dir, "python").is_file():
        _fail("isolated_environment_interpreter_missing")


def install_pinned_dependencies(
    interpreter: Path, dependency_lock: Path, *, scratch_dir: Path
) -> None:
    if not dependency_lock.is_file():
        _fail("dependency_lock_missing", dependency_lock.name)
    completed = _run(
        [
            str(interpreter),
            "-m",
            "pip",
            "install",
            "--require-hashes",
            "--no-deps",
            "--requirement",
            str(dependency_lock),
        ],
        cwd=scratch_dir,
        env=isolated_child_environment(),
        timeout=DEFAULT_INSTALL_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        _fail("dependency_install_failed", f"exit={completed.returncode}")


def install_wheel_from_artifact(interpreter: Path, wheel: Path, *, scratch_dir: Path) -> None:
    completed = _run(
        [
            str(interpreter),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--force-reinstall",
            str(wheel),
        ],
        cwd=scratch_dir,
        env=isolated_child_environment(),
        timeout=DEFAULT_INSTALL_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        _fail("wheel_install_failed", f"exit={completed.returncode}")


_LOCK_PIN = re.compile(r"^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?==([^\s\\;]+)")


def lock_blocks(lock_text: str) -> dict[str, tuple[str, str]]:
    """Each pinned block of a pip-compile lock: name -> (version, block text)."""
    blocks: dict[str, tuple[str, str]] = {}
    name: str | None = None
    version = ""
    lines: list[str] = []
    for line in [*lock_text.splitlines(), ""]:
        if line.strip().startswith("--hash=") and name is not None:
            lines.append(line)
            continue
        if not line or line.startswith("#") or line[0].isspace():
            continue
        if name is not None:
            blocks[name] = (version, "\n".join(lines))
        match = _LOCK_PIN.match(line)
        if match is None:
            _fail("dependency_lock_entry_not_pinned", line[:80])
        name, version, lines = normalize_distribution_name(match.group(1)), match.group(2), [line]
    if name is not None:
        blocks[name] = (version, "\n".join(lines))
    return blocks


def wheel_runtime_requirements(wheel: Path) -> list[str]:
    """The wheel's own Requires-Dist, read from the artifact itself."""
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = [Path(name) for name in archive.namelist()]
            metadata = _only(
                [name for name in names if name.match("*.dist-info/METADATA")],
                code="wheel_metadata_not_unique",
            )
            text = archive.read(metadata.as_posix()).decode("utf-8")
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError) as exc:
        _fail("wheel_metadata_unreadable", str(exc))
    return email.parser.Parser().parsestr(text).get_all("Requires-Dist") or []


def runtime_dependency_closure(wheel: Path, dependency_lock: Path) -> list[tuple[str, str]]:
    """The wheel's non-extra runtime closure, pinned by the lock.

    Requirements are expanded from the lock-pinned distributions' own metadata
    (the caller's environment was installed from the same lock; any version
    difference is UNKNOWN, never guessed). Extras are followed only where a
    requirement requests them.
    """
    try:
        from packaging.requirements import InvalidRequirement, Requirement
    except ImportError:
        _unknown("packaging_library_unavailable")
    if not dependency_lock.is_file():
        _fail("dependency_lock_missing", dependency_lock.name)
    blocks = lock_blocks(dependency_lock.read_text(encoding="utf-8"))
    closure: dict[str, str] = {}
    requested: dict[str, set[str]] = {}
    try:
        pending = [(Requirement(raw), {""}) for raw in wheel_runtime_requirements(wheel)]
        while pending:
            requirement, context = pending.pop()
            if requirement.marker is not None and not any(
                requirement.marker.evaluate({"extra": extra}) for extra in context
            ):
                continue
            name = normalize_distribution_name(requirement.name)
            extras = {""} | set(requirement.extras)
            if name in closure and extras <= requested[name]:
                continue
            if name not in blocks:
                _fail("runtime_dependency_not_in_lock", name)
            version = blocks[name][0]
            if requirement.specifier and not requirement.specifier.contains(
                version, prereleases=True
            ):
                _fail("runtime_dependency_lock_pin_unsatisfying", f"{requirement} lock={version}")
            try:
                distribution = importlib.metadata.distribution(name)
            except importlib.metadata.PackageNotFoundError:
                _unknown("runtime_dependency_metadata_unavailable", name)
            if distribution.version != version:
                _unknown(
                    "runtime_dependency_metadata_not_the_lock_pin",
                    f"{name} lock={version} metadata={distribution.version}",
                )
            closure[name] = version
            requested[name] = requested.get(name, set()) | extras
            pending.extend(
                (Requirement(raw), requested[name]) for raw in distribution.requires or []
            )
    except InvalidRequirement as exc:
        _fail("runtime_requirement_unparseable", str(exc))
    return sorted(closure.items())


def write_runtime_lock(
    closure: list[tuple[str, str]], dependency_lock: Path, destination: Path
) -> Path:
    blocks = lock_blocks(dependency_lock.read_text(encoding="utf-8"))
    destination.write_text(
        "\n".join(blocks[name][1] for name, _version in closure) + "\n", encoding="utf-8"
    )
    return destination


def check_isolated_dependencies(interpreter: Path, *, scratch_dir: Path) -> None:
    """pip's own consistency check: the installed closure satisfies every Requires-Dist."""
    completed = _run(
        [str(interpreter), "-m", "pip", "check"],
        cwd=scratch_dir,
        env=isolated_child_environment(),
        timeout=DEFAULT_PROBE_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        _fail("isolated_environment_dependency_check_failed", _diagnostic_tail(completed))


def _git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def verify_wheel_matches_source(wheel: Path, repo: Path, source_sha: str) -> dict[str, Any]:
    """Bind code, dependencies and entrypoints to the exact Git source, not wheel claims."""
    import configparser

    from packaging.requirements import Requirement

    listed = _git_text(repo, "ls-tree", "-r", "-z", source_sha, "--", "src")
    if listed is None:
        _unknown("source_tree_listing_unavailable")
    source: dict[str, str] = {}
    for entry in filter(None, listed.split("\0")):
        meta, _, path = entry.partition("\t")
        mode, kind, blob = meta.split()
        if kind != "blob" or mode not in {"100644", "100755"}:
            _fail("source_package_entry_not_regular", path)
        source[path.removeprefix("src/")] = blob
    project_text = _git_text(repo, "show", f"{source_sha}:pyproject.toml")
    if project_text is None:
        _unknown("source_package_contract_unavailable")
    project = tomllib.loads(project_text)["project"]
    expected_requirements = {str(Requirement(raw)) for raw in project.get("dependencies", [])}
    for extra, requirements in project.get("optional-dependencies", {}).items():
        for raw in requirements:
            requirement = Requirement(raw)
            marker = f"({requirement.marker}) and " if requirement.marker else ""
            requirement.marker = None
            expected_requirements.add(
                str(Requirement(f'{requirement}; {marker}extra == "{extra}"'))
            )
    packaged: set[str] = set()
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                _fail("wheel_duplicate_entries")
            metadata_name = _only(
                [Path(name) for name in names if name.endswith(".dist-info/METADATA")],
                code="wheel_metadata_not_unique",
            )
            metadata = email.parser.Parser().parsestr(
                archive.read(metadata_name.as_posix()).decode("utf-8")
            )
            if (
                normalize_distribution_name(metadata.get("Name", ""))
                != normalize_distribution_name(project["name"])
                or metadata.get("Version") != project["version"]
            ):
                _fail("wheel_metadata_identity_differs_from_source")
            if {
                str(Requirement(raw)) for raw in metadata.get_all("Requires-Dist") or []
            } != expected_requirements:
                _fail("wheel_dependencies_differ_from_source")
            if metadata.get("Requires-Python") != project.get("requires-python"):
                _fail("wheel_python_requirement_differs_from_source")
            entrypoints = configparser.ConfigParser(interpolation=None)
            entrypoints.optionxform = str
            entrypoints.read_string(
                archive.read(str(metadata_name.parent / "entry_points.txt")).decode("utf-8")
            )
            actual_scripts = (
                dict(entrypoints.items("console_scripts"))
                if entrypoints.has_section("console_scripts")
                else {}
            )
            if actual_scripts != project.get("scripts", {}):
                _fail("wheel_entrypoints_differ_from_source")
            for info in archive.infolist():
                top = info.filename.split("/", 1)[0]
                if info.is_dir() or top.endswith(".dist-info"):
                    continue
                if top.endswith(".data"):
                    _fail("wheel_unexpected_data_payload", info.filename)
                blob = _git_blob_id(archive.read(info))
                if info.filename not in source:
                    _fail("wheel_file_not_in_source", info.filename)
                if source[info.filename] != blob:
                    _fail("wheel_file_differs_from_source", info.filename)
                packaged.add(info.filename)
    except (
        OSError,
        zipfile.BadZipFile,
        KeyError,
        UnicodeError,
        ValueError,
        configparser.Error,
    ) as exc:
        _fail("wheel_unreadable", str(exc))
    missing = sorted(path for path in source if path.endswith(".py") and path not in packaged)
    if missing:
        _fail("wheel_missing_source_module", ",".join(missing[:10]))
    if not packaged:
        _fail("wheel_carries_no_package_files")
    return {
        "status": PASS,
        "files": len(packaged),
        "packages": sorted({name.split("/", 1)[0] for name in packaged}),
        "source_sha": source_sha,
        "metadata_bound_to_source": True,
    }


def installed_distribution_version(
    interpreter: Path, distribution: str, *, scratch_dir: Path
) -> str | None:
    program = f"import importlib.metadata as m; print(m.version({distribution!r}))"
    completed = _run(
        [str(interpreter), "-I", "-c", program],
        cwd=scratch_dir,
        env=isolated_child_environment(),
        timeout=DEFAULT_PROBE_TIMEOUT_SECONDS,
        diagnose=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def verify_install_source(
    venv_dir: Path, wheel: Path, wheel_sha256: str, contract: PackageContract
) -> dict[str, Any]:
    """Prove the installed distribution came from this wheel, not a source tree."""
    site_packages = _venv_site_packages(venv_dir)

    # Contamination is detected before distribution identity so an editable install
    # is reported as an editable install rather than as a missing distribution.
    editable_markers = sorted(
        path.name
        for pattern in ("__editable__*", "*.egg-link")
        for path in site_packages.glob(pattern)
    )
    if editable_markers:
        _fail("editable_install_detected_in_isolated_environment", ",".join(editable_markers))

    dist_infos = sorted(
        path
        for path in site_packages.glob("*.dist-info")
        if path.is_dir()
        and normalize_distribution_name(path.name.split("-", 1)[0]) == contract.normalized_name
    )
    if len(dist_infos) != 1:
        _fail("installed_distribution_not_uniquely_resolved", str(len(dist_infos)))
    dist_info = dist_infos[0]

    direct_url = dist_info / "direct_url.json"
    if not direct_url.is_file():
        _fail("install_source_not_recorded", "direct_url.json_absent")
    try:
        payload = json.loads(direct_url.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _unknown("install_source_record_unreadable", str(exc))
    if not isinstance(payload, dict):
        _fail("install_source_record_malformed")
    if payload.get("dir_info"):
        _fail("install_source_is_directory_not_wheel")
    archive_info = payload.get("archive_info")
    if not isinstance(archive_info, dict):
        _fail("install_source_record_has_no_archive_info")
    url = payload.get("url")
    if not isinstance(url, str) or os.path.basename(url) != wheel.name:
        _fail("install_source_wheel_filename_mismatch", wheel.name)
    recorded_sha = None
    hashes = archive_info.get("hashes")
    if isinstance(hashes, dict):
        recorded_sha = hashes.get("sha256")
    if recorded_sha is None and isinstance(archive_info.get("hash"), str):
        prefix, _, value = archive_info["hash"].partition("=")
        if prefix.lower() == "sha256":
            recorded_sha = value
    if not isinstance(recorded_sha, str) or not SHA256_RE.match(recorded_sha):
        _fail("install_source_record_has_no_sha256")
    if recorded_sha != wheel_sha256:
        _fail("install_source_digest_mismatch", f"wheel={wheel_sha256} installed={recorded_sha}")
    return {
        "dist_info": dist_info.name,
        "direct_url_sha256": recorded_sha,
        "index_access": "disabled",
        "editable": False,
        "install_source": "wheel",
    }


# --------------------------------------------------------------------------- #
# Probe program executed inside the isolated environment.
# --------------------------------------------------------------------------- #

PROBE_PROGRAM = r"""
import json
import sys
import sysconfig
import importlib
import importlib.metadata

payload = {
    "sys_path": list(sys.path),
    "sys_prefix": sys.prefix,
    "base_prefix": sys.base_prefix,
    "purelib": sysconfig.get_paths()["purelib"],
    "python_version": sys.version.split()[0],
    "python_implementation": sys.implementation.name,
}

module_name = sys.argv[1]
distribution = sys.argv[2]
try:
    module = importlib.import_module(module_name)
except Exception as exc:
    payload["import_ok"] = False
    payload["import_error_type"] = type(exc).__name__
    payload["module_file"] = None
else:
    payload["import_ok"] = True
    payload["module_file"] = getattr(module, "__file__", None)

try:
    payload["dist_version"] = importlib.metadata.version(distribution)
except importlib.metadata.PackageNotFoundError:
    payload["dist_version"] = None

try:
    requirements = importlib.metadata.requires(distribution) or []
except importlib.metadata.PackageNotFoundError:
    requirements = []

payload["sys_path"] = list(sys.path)  # Recheck after importing candidate code.
payload["runtime_requirements"] = requirements
payload["installed_versions"] = {
    dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()
}

print(json.dumps(payload))
"""


def run_installed_probe(
    venv_dir: Path,
    *,
    module_name: str,
    distribution: str,
    forbidden_roots: list[Path],
    scratch_dir: Path,
) -> dict[str, Any]:
    completed = _run(
        [str(_venv_python(venv_dir)), "-I", "-c", PROBE_PROGRAM, module_name, distribution],
        cwd=scratch_dir,
        env=isolated_child_environment(),
        timeout=DEFAULT_PROBE_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        _fail("installed_import_probe_failed", f"exit={completed.returncode}")
    stdout = completed.stdout.strip()
    if not stdout:
        _fail("installed_import_probe_empty_output")
    try:
        payload = json.loads(stdout.splitlines()[-1])
    except ValueError as exc:
        _unknown("installed_import_probe_output_not_json", str(exc))
    if not isinstance(payload, dict):
        _unknown("installed_import_probe_output_not_object")

    purelib = Path(str(payload.get("purelib", "")))
    module_file_raw = payload.get("module_file")
    if payload.get("import_ok") is not True or not isinstance(module_file_raw, str):
        _fail(
            "installed_import_failed", str(payload.get("import_error_type") or "module_file_absent")
        )
    module_file = Path(module_file_raw).resolve()
    leaked = sorted(
        str(entry)
        for entry in payload.get("sys_path", [])
        if any(_under(Path(entry).resolve(), root) for root in forbidden_roots)
    )
    if leaked:
        _fail("source_tree_leaked_onto_isolated_sys_path", ",".join(leaked))
    if not _under(module_file, purelib):
        _fail("installed_import_resolved_outside_isolated_environment", module_file.name)
    if str(payload.get("sys_prefix")) != str(venv_dir.resolve()):
        _fail("probe_interpreter_is_not_the_isolated_environment")
    # The parser is audit tooling, so keep it outside the product-only venv.
    from packaging.requirements import Requirement

    versions = {
        normalize_distribution_name(name): value
        for name, value in payload.get("installed_versions", {}).items()
    }
    satisfied, unresolved = [], []
    for raw in payload.get("runtime_requirements", []):
        requirement = Requirement(raw)
        if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
            continue
        version = versions.get(normalize_distribution_name(requirement.name))
        if version is None or (
            requirement.specifier and not requirement.specifier.contains(version, prereleases=True)
        ):
            unresolved.append({"requirement": raw, "reason": "not_installed_or_unsatisfying"})
        else:
            satisfied.append({"requirement": raw, "installed_version": version})
    payload["dependency_check"] = "complete"
    payload["runtime_requirements_satisfied"] = satisfied
    payload["runtime_requirements_unresolved"] = unresolved
    if payload.get("dependency_check") != "complete":
        _fail("runtime_dependency_satisfaction_not_verifiable")
    if unresolved:
        _fail("runtime_dependencies_unresolved", json.dumps(unresolved, sort_keys=True))
    return {
        "status": PASS,
        "module": module_name,
        "module_file_relative_to_purelib": module_file.relative_to(purelib).as_posix(),
        "resolved_in_isolated_environment": True,
        "python_version": payload.get("python_version"),
        "python_implementation": payload.get("python_implementation"),
        "dist_version": payload.get("dist_version"),
        "runtime_requirements_satisfied": payload.get("runtime_requirements_satisfied", []),
        "sys_path_entry_count": len(payload.get("sys_path", [])),
    }


def probe_console_entrypoints(
    venv_dir: Path, contract: PackageContract, *, scratch_dir: Path
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for script_name, target in contract.scripts.items():
        executable = venv_bin(venv_dir, script_name)
        record: dict[str, Any] = {"status": PASS, "name": script_name, "target": target}
        if not executable.is_file():
            record["status"] = FAIL
            record["reason"] = "cli_entrypoint_missing"
            results.append(record)
            continue
        completed = _run(
            [str(executable), CLI_SMOKE_ARGUMENT],
            cwd=scratch_dir,
            env=isolated_child_environment(),
            timeout=DEFAULT_CLI_TIMEOUT_SECONDS,
        )
        stdout = completed.stdout.encode("utf-8", errors="replace")
        stderr = completed.stderr.encode("utf-8", errors="replace")
        record["returncode"] = completed.returncode
        record["argument"] = CLI_SMOKE_ARGUMENT
        record["stdout_bytes"] = len(stdout)
        record["stdout_sha256"] = hashlib.sha256(stdout).hexdigest()
        record["stderr_bytes"] = len(stderr)
        if completed.returncode != 0:
            record["status"] = FAIL
            record["reason"] = "cli_entrypoint_failed"
        results.append(record)
    return results


# --------------------------------------------------------------------------- #
# Evidence document
# --------------------------------------------------------------------------- #

REQUIRED_EVIDENCE_KEYS: tuple[str, ...] = (
    "schema_version",
    "source_sha",
    "source_tree",
    "wheel_filename",
    "wheel_sha256",
    "package_name",
    "package_version",
    "declared_version",
    "python_version",
    "install_source",
    "installed_import",
    "cli_entrypoint_results",
    "overall_classification",
    "reasons",
    "package_contract",
    "environment",
    "install",
    "cli_entrypoints",
    "wheel_source_binding",
    "dependency_closure",
    "expected_bindings",
)


def build_evidence(
    *,
    contract: PackageContract,
    source_sha: str,
    source_tree: str,
    wheel: Path,
    wheel_sha256: str,
    import_module: str,
    installed_version: str | None,
    python_version: str | None,
    dependency_lock: Path,
    dependency_lock_sha256: str | None,
    install_record: dict[str, Any] | None,
    installed_import: dict[str, Any] | None,
    cli_entrypoints: list[dict[str, Any]] | None,
    isolation: dict[str, Any],
    expected_binding: dict[str, Any] | None,
    classification: str,
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "source_sha": source_sha,
        "source_tree": source_tree,
        "wheel_filename": wheel.name,
        "wheel_sha256": wheel_sha256,
        "package_name": contract.name,
        "package_version": installed_version or contract.version,
        "declared_version": contract.version,
        "python_version": python_version,
        "install_source": "wheel",
        "install": {
            **(install_record or {}),
            "dependency_install": "pip install --require-hashes --requirement <dependency lock>",
            "dependency_lock": dependency_lock.name,
            "dependency_lock_sha256": dependency_lock_sha256,
        },
        "environment": isolation,
        "installed_import": installed_import or {"status": FAIL, "module": import_module},
        "cli_entrypoints": cli_entrypoints or [],
        "cli_entrypoint_results": {
            record["name"]: record for record in (cli_entrypoints or []) if isinstance(record, dict)
        },
        "package_contract": contract.to_json(),
        "expected_bindings": expected_binding,
        "overall_classification": classification,
        "reasons": reasons or ["all_packaging_smoke_invariants_satisfied"],
        "hidden_information": "none_no_game_state_or_player_data_collected",
        "production_provider": "NOT_SELECTED",
        "architecture_freeze": "NOT_CLAIMED",
    }


def write_evidence(output: Path, evidence: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# mode: smoke
# --------------------------------------------------------------------------- #


def _run_smoke_bound(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    wheel_dir = Path(args.wheel_dir).resolve()
    pyproject = Path(args.pyproject).resolve() if args.pyproject else repo / "pyproject.toml"
    dependency_lock = (
        Path(args.dependency_lock).resolve()
        if args.dependency_lock
        else repo / "requirements" / "lock.txt"
    )
    venv_dir = Path(args.venv_dir).resolve()
    scratch_dir = Path(args.scratch_dir).resolve() if args.scratch_dir else venv_dir.parent
    output = Path(args.output).resolve()

    if _under(scratch_dir, repo):
        _fail("scratch_dir_inside_repository")
    source_sha, source_tree = read_source_identity(repo)
    contract = read_package_contract(pyproject)
    if not dependency_lock.is_file():
        _fail("dependency_lock_missing", dependency_lock.name)
    if not args.dependency_lock:
        committed_lock = _git_text(repo, "show", f"{source_sha}:requirements/lock.txt")
        if committed_lock is None or dependency_lock.read_text().strip() != committed_lock:
            _fail("dependency_lock_not_the_source_input")
    wheel = select_project_wheel(wheel_dir, contract)
    wheel_sha256 = sha256_file(wheel)
    if args.expect_wheel_sha256 is not None and args.expect_wheel_sha256 != wheel_sha256:
        _fail(
            "wheel_digest_mismatch", f"expected={args.expect_wheel_sha256} observed={wheel_sha256}"
        )
    assert_source_binding(source_sha, source_tree, args.expect_source_sha, args.expect_source_tree)

    expected_binding: dict[str, Any] | None = None
    if any(
        value is not None
        for value in (
            args.expect_source_sha,
            args.expect_source_tree,
            args.expect_wheel_sha256,
            args.expect_version,
        )
    ):
        expected_binding = {
            "source_sha": args.expect_source_sha,
            "source_tree": args.expect_source_tree,
            "wheel_sha256": args.expect_wheel_sha256,
            "package_version": args.expect_version,
        }

    isolation = {
        "isolated_environment": True,
        "created_by_this_run": True,
        "preexisting_environment_rejected": True,
        "include_system_site_packages": False,
        "pythonpath_scrubbed": True,
        "pythonhome_scrubbed": True,
        "probe_isolated_flag": "-I",
        "probe_cwd_outside_repository": True,
        "forbidden_import_roots": ["<repository>", "<repository>/src"],
        "wheel_selection": "exactly_one_project_wheel_or_fail_closed",
    }

    state: dict[str, Any] = {
        "installed_version": None,
        "python_version": None,
        "install_record": None,
        "installed_import": None,
        "cli_entrypoints": None,
    }
    classification = PASS
    reasons: list[str] = []
    closure_record: dict[str, Any] = {"status": "NOT_RUN"}
    source_record: dict[str, Any] = {"status": "NOT_RUN"}
    try:
        source_record = verify_wheel_matches_source(wheel, repo, source_sha)
        closure = runtime_dependency_closure(wheel, dependency_lock)
        scratch_dir.mkdir(parents=True, exist_ok=True)
        subset = write_runtime_lock(
            closure, dependency_lock, scratch_dir / "runtime-requirements.lock"
        )
        closure_record = {
            "status": PASS,
            "requirements": [f"{name}=={version}" for name, version in closure],
            "lock_subset_sha256": sha256_file(subset),
            "scope": "wheel_declared_base_runtime_only",
        }
        scratch_dir.mkdir(parents=True, exist_ok=True)
        create_isolated_environment(venv_dir, scratch_dir=scratch_dir)
        interpreter = _venv_python(venv_dir)

        version_probe = _run(
            [str(interpreter), "-I", "-c", "import sys; print(sys.version.split()[0])"],
            cwd=scratch_dir,
            env=isolated_child_environment(),
            timeout=DEFAULT_PROBE_TIMEOUT_SECONDS,
        )
        state["python_version"] = version_probe.stdout.strip() or None
        if version_probe.returncode != 0 or not state["python_version"]:
            _unknown("isolated_python_version_not_resolvable")

        install_pinned_dependencies(interpreter, subset, scratch_dir=scratch_dir)
        install_wheel_from_artifact(interpreter, wheel, scratch_dir=scratch_dir)
        check_isolated_dependencies(interpreter, scratch_dir=scratch_dir)
        state["install_record"] = verify_install_source(venv_dir, wheel, wheel_sha256, contract)

        installed_version = installed_distribution_version(
            interpreter, contract.normalized_name, scratch_dir=scratch_dir
        )
        state["installed_version"] = installed_version
        if installed_version is None:
            _fail("installed_distribution_metadata_not_resolvable")
        if installed_version != contract.version:
            _fail(
                "package_version_mismatch",
                f"declared={contract.version} installed={installed_version}",
            )
        if args.expect_version is not None and installed_version != args.expect_version:
            _fail(
                "package_version_mismatch",
                f"expected={args.expect_version} installed={installed_version}",
            )

        state["installed_import"] = run_installed_probe(
            venv_dir,
            module_name=args.import_module,
            distribution=contract.normalized_name,
            forbidden_roots=[repo, repo / "src"],
            scratch_dir=scratch_dir,
        )
        state["cli_entrypoints"] = probe_console_entrypoints(
            venv_dir, contract, scratch_dir=scratch_dir
        )
        broken = sorted(
            f"{record['name']}:{record.get('reason', 'failed')}"
            for record in state["cli_entrypoints"]
            if record.get("status") != PASS
        )
        if broken:
            _fail("cli_entrypoint_smoke_failed", ",".join(broken))

        final_sha, final_tree = read_source_identity(repo)
        if (final_sha, final_tree) != (source_sha, source_tree):
            _fail("source_identity_drift_during_smoke")
    except _Classification as failure:
        classification = failure.classification
        reasons.append(failure.code)

    evidence = build_evidence(
        contract=contract,
        source_sha=source_sha,
        source_tree=source_tree,
        wheel=wheel,
        wheel_sha256=wheel_sha256,
        import_module=args.import_module,
        installed_version=state["installed_version"],
        python_version=state["python_version"],
        dependency_lock=dependency_lock,
        dependency_lock_sha256=sha256_file(dependency_lock) if dependency_lock.is_file() else None,
        install_record=state["install_record"],
        installed_import=state["installed_import"],
        cli_entrypoints=state["cli_entrypoints"],
        isolation=isolation,
        expected_binding=expected_binding,
        classification=classification,
        reasons=reasons,
    )
    evidence["dependency_closure"] = closure_record
    evidence["wheel_source_binding"] = source_record
    write_evidence(output, evidence)
    if classification == PASS:
        print(f"packaging smoke PASS: {wheel.name} sha256={wheel_sha256}")
        return EXIT_CODES[PASS]
    print(f"packaging smoke {classification}: {', '.join(reasons)}", file=sys.stderr)
    return EXIT_CODES[classification]


def run_smoke(args: argparse.Namespace) -> int:
    output = Path(args.output).resolve()
    # An interrupted/early failure can never leave an older PASS available.
    write_evidence(
        output,
        {
            "schema_version": SCHEMA_VERSION,
            "overall_classification": "NOT_RUN",
            "reasons": ["smoke_started_no_verdict_yet"],
        },
    )
    try:
        return _run_smoke_bound(args)
    except _Classification as failure:
        write_evidence(
            output,
            {
                "schema_version": SCHEMA_VERSION,
                "overall_classification": failure.classification,
                "reasons": [failure.code],
            },
        )
        print(f"packaging smoke {failure.classification}: {failure.code}", file=sys.stderr)
        return EXIT_CODES[failure.classification]
    except (OSError, UnicodeError, ValueError) as error:
        write_evidence(
            output,
            {
                "schema_version": SCHEMA_VERSION,
                "overall_classification": UNKNOWN,
                "reasons": ["smoke_input_unreadable:" + type(error).__name__],
            },
        )
        print("packaging smoke UNKNOWN: smoke_input_unreadable", file=sys.stderr)
        return EXIT_CODES[UNKNOWN]


# --------------------------------------------------------------------------- #
# mode: check
# --------------------------------------------------------------------------- #


def _structural_reasons(document: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if document["schema_version"] != SCHEMA_VERSION:
        reasons.append(f"schema_version_unsupported:{document['schema_version']}")
    if document["overall_classification"] != PASS:
        reasons.append(f"recorded_classification_not_pass:{document['overall_classification']}")
    if not isinstance(document["reasons"], list):
        reasons.append("reasons_not_a_list")
    if not SHA_RE.match(str(document["source_sha"])):
        reasons.append("source_sha_malformed")
    if not SHA_RE.match(str(document["source_tree"])):
        reasons.append("source_tree_malformed")
    if not SHA256_RE.match(str(document["wheel_sha256"])):
        reasons.append("wheel_sha256_malformed")
    if document["install_source"] != "wheel":
        reasons.append(f"install_source_not_wheel:{document['install_source']}")
    if not isinstance(document["python_version"], str) or not document["python_version"]:
        reasons.append("python_version_missing")
    if document["package_version"] != document["declared_version"]:
        reasons.append("package_version_does_not_match_declared_version")
    filename = str(document["wheel_filename"])
    if not filename or "/" in filename or "\\" in filename or not filename.endswith(".whl"):
        reasons.append("wheel_filename_not_a_wheel_basename")

    imported = document["installed_import"]
    if not isinstance(imported, dict):
        reasons.append("installed_import_not_a_mapping")
    else:
        if imported.get("status") != PASS:
            reasons.append(f"installed_import_not_passed:{imported.get('status')}")
        if imported.get("resolved_in_isolated_environment") is not True:
            reasons.append("installed_import_not_proven_isolated")
        if not str(imported.get("module_file_relative_to_purelib", "")):
            reasons.append("installed_import_provenance_missing")
    return reasons


def _contract_reasons(document: dict[str, Any], contract: PackageContract) -> list[str]:
    reasons: list[str] = []
    if normalize_distribution_name(str(document["package_name"])) != contract.normalized_name:
        reasons.append("package_name_not_the_project_distribution")
    if document["package_version"] != contract.version:
        reasons.append("package_version_not_the_current_declared_version")
    results = document["cli_entrypoint_results"]
    if not isinstance(results, dict):
        return [*reasons, "cli_entrypoint_results_not_a_mapping"]
    for script_name in contract.scripts:
        record = results.get(script_name)
        if not isinstance(record, dict):
            reasons.append(f"cli_entrypoint_result_missing:{script_name}")
            continue
        if record.get("status") != PASS:
            reasons.append(f"cli_entrypoint_not_passed:{script_name}")
        elif record.get("returncode") != 0:
            reasons.append(f"cli_entrypoint_nonzero_exit:{script_name}")
    unexpected = sorted(set(results) - set(contract.scripts))
    if unexpected:
        reasons.append(f"cli_entrypoint_result_unexpected:{','.join(unexpected)}")
    return reasons


def check_evidence(args: argparse.Namespace) -> int:
    path = Path(args.evidence).resolve()
    if not path.is_file():
        print(f"packaging evidence missing: {path.name}", file=sys.stderr)
        return EXIT_CODES[FAIL]
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"packaging evidence unreadable: {exc}", file=sys.stderr)
        return EXIT_CODES[FAIL]
    if not isinstance(document, dict):
        print("packaging evidence is not a JSON object", file=sys.stderr)
        return EXIT_CODES[FAIL]

    missing = sorted(key for key in REQUIRED_EVIDENCE_KEYS if key not in document)
    if missing:
        print(f"packaging evidence missing required keys: {','.join(missing)}", file=sys.stderr)
        return EXIT_CODES[FAIL]

    reasons = _structural_reasons(document)
    if document["reasons"] != ["all_packaging_smoke_invariants_satisfied"]:
        reasons.append("pass_carries_failure_reasons")
    try:
        actual_sha, actual_tree = read_source_identity(Path(args.repo))
        if document["source_sha"] != actual_sha or document["source_tree"] != actual_tree:
            reasons.append("evidence_source_identity_not_current")
    except _Classification as failure:
        reasons.append(failure.code)
    install = document.get("install")
    if not isinstance(install, dict):
        reasons.append("install_not_a_mapping")
    else:
        for key, expected in {
            "direct_url_sha256": document["wheel_sha256"],
            "editable": False,
            "install_source": "wheel",
            "index_access": "disabled",
        }.items():
            if install.get(key) != expected or (
                key == "editable" and install.get(key) is not False
            ):
                reasons.append("install_binding_invalid:" + key)
        try:
            if install.get("dependency_lock_sha256") != sha256_file(
                Path(args.repo) / "requirements/lock.txt"
            ):
                reasons.append("dependency_lock_binding_invalid")
        except _Classification as failure:
            reasons.append(failure.code)
    environment = document.get("environment")
    if not isinstance(environment, dict):
        reasons.append("environment_not_a_mapping")
    else:
        for key, expected in {
            "include_system_site_packages": False,
            "isolated_environment": True,
            "created_by_this_run": True,
            "pythonpath_scrubbed": True,
            "pythonhome_scrubbed": True,
            "probe_cwd_outside_repository": True,
            "probe_isolated_flag": "-I",
        }.items():
            if environment.get(key) != expected or (
                isinstance(expected, bool) and environment.get(key) is not expected
            ):
                reasons.append("environment_binding_invalid:" + key)
    bindings = document.get("expected_bindings")
    if bindings is not None:
        if not isinstance(bindings, dict):
            reasons.append("expected_bindings_not_mapping")
        else:
            for key, expected in bindings.items():
                if key not in {"source_sha", "source_tree", "wheel_sha256", "package_version"} or (
                    expected is not None and document.get(key) != expected
                ):
                    reasons.append("expected_binding_mismatch:" + key)
    entries = document.get("cli_entrypoints")
    if not isinstance(entries, list) or any(not isinstance(row, dict) for row in entries):
        reasons.append("cli_entrypoints_not_records")
    elif any(not isinstance(row.get("name"), str) for row in entries):
        reasons.append("cli_entrypoint_name_not_string")
    elif len({row.get("name") for row in entries}) != len(entries) or {
        row.get("name"): row for row in entries
    } != document.get("cli_entrypoint_results"):
        reasons.append("cli_entrypoint_sections_inconsistent")
    for key in ("wheel_source_binding", "dependency_closure"):
        if not isinstance(document.get(key), dict) or document[key].get("status") != PASS:
            reasons.append(key + "_not_pass")
    if not args.wheel_dir:
        reasons.append("artifact_reverification_required")

    contract: PackageContract | None = None
    try:
        contract = read_package_contract(
            Path(args.pyproject) if args.pyproject else Path(args.repo) / "pyproject.toml"
        )
    except _Classification as failure:
        reasons.append(f"package_contract_unusable:{failure.code}")
    if contract is not None:
        reasons.extend(_contract_reasons(document, contract))
        if document.get("package_contract") != contract.to_json():
            reasons.append("package_contract_not_current")
        if args.wheel_dir:
            try:
                observed = select_project_wheel(Path(args.wheel_dir), contract)
            except _Classification as failure:
                reasons.append(f"artifact_reverification_failed:{failure.code}")
            else:
                if observed.name != str(document["wheel_filename"]):
                    reasons.append("artifact_reverification_filename_mismatch")
                elif sha256_file(observed) != str(document["wheel_sha256"]):
                    reasons.append("artifact_reverification_digest_mismatch")
                else:
                    try:
                        source_record = verify_wheel_matches_source(
                            observed, Path(args.repo), str(document["source_sha"])
                        )
                        if document.get("wheel_source_binding") != source_record:
                            reasons.append("wheel_source_binding_invalid")
                        lock = Path(args.repo) / "requirements/lock.txt"
                        closure = runtime_dependency_closure(observed, lock)
                        blocks = lock_blocks(lock.read_text())
                        subset = "\n".join(blocks[name][1] for name, _ in closure) + "\n"
                        expected = {
                            "status": PASS,
                            "requirements": [f"{name}=={version}" for name, version in closure],
                            "lock_subset_sha256": hashlib.sha256(subset.encode()).hexdigest(),
                            "scope": "wheel_declared_base_runtime_only",
                        }
                        if document.get("dependency_closure") != expected:
                            reasons.append("runtime_dependency_closure_invalid")
                    except _Classification as failure:
                        reasons.append("artifact_reverification_failed:" + failure.code)

    if args.expect_source_sha is not None and str(document["source_sha"]) != args.expect_source_sha:
        reasons.append("evidence_source_sha_not_the_expected_candidate")
    if (
        args.expect_wheel_sha256 is not None
        and str(document["wheel_sha256"]) != args.expect_wheel_sha256
    ):
        reasons.append("evidence_wheel_digest_not_the_expected_artifact")

    # Recorded runtime results are unsigned observations. Re-execute the full
    # wheel-only installation and probes in a new environment before crediting
    # PASS; source/artifact hashes alone cannot prove an import or CLI ran.
    if not reasons:
        with tempfile.TemporaryDirectory(prefix="b9-independent-check-") as directory:
            root = Path(directory)
            fresh_output = root / "RUNTIME_REVERIFICATION.json"
            probe_args = argparse.Namespace(
                repo=args.repo,
                wheel_dir=args.wheel_dir,
                pyproject=args.pyproject,
                dependency_lock=None,
                venv_dir=str(root / "venv"),
                scratch_dir=str(root / "scratch"),
                output=str(fresh_output),
                import_module=DEFAULT_IMPORT_MODULE,
                expect_source_sha=str(document["source_sha"]),
                expect_source_tree=str(document["source_tree"]),
                expect_wheel_sha256=str(document["wheel_sha256"]),
                expect_version=str(document["package_version"]),
            )
            result = run_smoke(probe_args)
            if result != EXIT_CODES[PASS]:
                observed = json.loads(fresh_output.read_text())
                reasons.append(
                    "runtime_reverification_failed:"
                    + ",".join(observed.get("reasons", ["no_verdict"]))
                )

    if reasons:
        print("packaging evidence check FAIL: " + "; ".join(reasons), file=sys.stderr)
        return EXIT_CODES[FAIL]
    print(
        "packaging evidence check PASS: "
        f"{document['wheel_filename']} sha256={document['wheel_sha256']} source={document['source_sha']}"
    )
    return EXIT_CODES[PASS]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    smoke = subparsers.add_parser("smoke", help="run the packaging smoke and write evidence")
    smoke.add_argument("--repo", default=".", help="repository root holding the source lock")
    smoke.add_argument("--wheel-dir", required=True, help="directory holding the built wheel")
    smoke.add_argument("--pyproject", default=None, help="package contract source")
    smoke.add_argument("--dependency-lock", default=None, help="hash-pinned dependency lock")
    smoke.add_argument(
        "--venv-dir", required=True, help="isolated environment to create; must not exist"
    )
    smoke.add_argument(
        "--scratch-dir", default=None, help="working directory outside the repository"
    )
    smoke.add_argument("--output", required=True, help="machine-readable evidence output path")
    smoke.add_argument("--import-module", default=DEFAULT_IMPORT_MODULE)
    smoke.add_argument("--expect-source-sha", default=None)
    smoke.add_argument("--expect-source-tree", default=None)
    smoke.add_argument("--expect-wheel-sha256", default=None)
    smoke.add_argument("--expect-version", default=None)
    smoke.set_defaults(handler=run_smoke)

    check = subparsers.add_parser("check", help="independently consume packaging evidence")
    check.add_argument("--evidence", required=True)
    check.add_argument("--repo", default=".")
    check.add_argument("--pyproject", default=None)
    check.add_argument(
        "--wheel-dir", default=None, help="re-verify the bound wheel artifact digest"
    )
    check.add_argument("--expect-source-sha", default=None)
    check.add_argument("--expect-wheel-sha256", default=None)
    check.set_defaults(handler=check_evidence)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except _Classification as failure:
        print(f"packaging smoke {failure.classification}: {failure.code}", file=sys.stderr)
        return EXIT_CODES[failure.classification]


if __name__ == "__main__":
    raise SystemExit(main())
