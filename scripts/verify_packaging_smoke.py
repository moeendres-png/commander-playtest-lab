#!/usr/bin/env python3
"""Deterministic packaging smoke for the built wheel artifact (issue #490).

Wheel *construction* is not packaging evidence. This consumer proves that the
exact wheel the candidate built is a faithful build of the candidate source, that
it installs into a clean isolated Python environment together with *only* its own
declared runtime dependency closure, and that the *installed* package imports and
exposes its officially supported console entrypoints.

Two independent modes, both fail closed:

``smoke``
    Remove any previous evidence, select exactly one project wheel, bind it to the
    source SHA/TREE of a clean working tree and to its own SHA-256 digest, prove
    every packaged file is byte-identical to the git-tracked source at ``HEAD``,
    install it into a freshly created virtual environment from a hash-verified
    wheelhouse with no index, prove the install came from the wheel (never an
    editable install, never a directory, never an index), prove nothing outside the
    wheel's declared dependency closure is installed, probe the installed package
    import and every declared console entrypoint, and write a machine-readable
    evidence document. Every failure path - including the earliest ones - writes a
    ``FAIL``/``UNKNOWN`` evidence document, so an older ``PASS`` can never survive.

``check``
    Independently re-adjudicate a previously written evidence document. The
    checker recomputes everything it can from the repository and the wheel
    directory (current ``HEAD`` SHA/TREE, clean working tree, wheel digest, wheel
    to source binding, package contract, dependency lock digest and pins, the
    checking interpreter's Python version) and fails on any mismatch or on any
    internally contradictory, incomplete or unknown field. Missing, truncated,
    malformed, unbound or ``UNKNOWN`` evidence is never promoted to ``PASS``.

Isolation invariants enforced here:

* the wheel set is resolved deterministically: exactly one project wheel, or the
  run fails closed. First-file selection is never used;
* the working tree has no tracked modification and every file under the declared
  package source root of ``HEAD`` is in the wheel byte for byte, with no missing,
  extra or different file, so a wheel built from another commit (or from a stale
  build directory) fails closed;
* the isolated environment is created by this run, must not pre-exist, and its
  ``pyvenv.cfg`` must declare ``include-system-site-packages = false``;
* dependencies are downloaded with ``--require-hashes --no-deps --only-binary``
  from the project's own hash-pinned lock (``requirements/lock.txt``) into a fresh
  wheelhouse, and every wheelhouse file is re-verified against the lock pins and
  hashes; the project wheel is then installed by its exact path with
  ``--no-index --find-links <wheelhouse>``, so pip resolves *only* the wheel's own
  ``Requires-Dist`` closure and nothing is fetched from an index at install time;
* every installed distribution other than the venv's own baseline and the project
  must be in the wheel's declared dependency closure at the lock-pinned version, so
  an undeclared import of a merely-locked package (a dev/api/openai extra) fails;
* the installed distribution must record a ``direct_url.json`` wheel archive
  whose SHA-256 equals the wheel digest bound before installing, and no editable
  install marker may exist in the isolated environment;
* the import probe runs the venv interpreter with ``-I`` (which implies ``-E``,
  ``-P`` and ``-s``), with ``PYTHONPATH``/``PYTHONHOME`` removed from the child
  environment, from a working directory outside the repository, and it must prove
  that the imported module resolves inside the venv's own ``purelib`` and that no
  repository path leaked onto ``sys.path``;
* the installed ``console_scripts`` entry points must equal the pyproject contract
  and every declared console script must exit 0 on ``--help``;
* the source SHA/TREE and the working-tree state are re-read after the probes so
  mid-run source drift fails closed instead of producing evidence for a different
  tree.

No game state, no player data and no credential values are read or recorded, so
the evidence carries no hidden information.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path
from typing import Any, NoReturn

SCHEMA_VERSION = "packaging-smoke-2.0.0"
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

# A fresh ``python -m venv`` may only contain installer tooling before the project
# is installed. Anything else means the environment is not clean.
PERMITTED_BASELINE_DISTRIBUTIONS = frozenset({"pip", "setuptools", "wheel"})

# Network settings the *download* step may need to reach the index (proxy and CA
# trust only). They are never passed to the install, import or CLI probes.
NETWORK_PASSTHROUGH_VARIABLES = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "all_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "PIP_CERT",
    "PIP_INDEX_URL",
    "PIP_CACHE_DIR",
)

REPOSITORY_PLACEHOLDER = "<repository>"
WHEELHOUSE_PLACEHOLDER = "<wheelhouse>"
WHEEL_PLACEHOLDER = "<wheel>"
LOCK_PLACEHOLDER = "<dependency lock>"

HIDDEN_INFORMATION = "none_no_game_state_or_player_data_collected"
PRODUCTION_PROVIDER = "NOT_SELECTED"
ARCHITECTURE_FREEZE = "NOT_CLAIMED"
WHEEL_SELECTION_POLICY = "exactly_one_project_wheel_or_fail_closed"


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

    def __init__(
        self,
        name: str,
        version: str,
        scripts: dict[str, str],
        source: Path,
        source_root: str = "src",
    ) -> None:
        self.name = name
        self.version = version
        self.scripts = dict(sorted(scripts.items()))
        self.source = source
        self.source_root = source_root

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
            "package_source_root": self.source_root,
        }


def read_package_contract(pyproject: Path) -> PackageContract:
    try:
        document = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _unknown("package_contract_unreadable", type(exc).__name__)
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
    where = (
        document.get("tool", {})
        .get("setuptools", {})
        .get("packages", {})
        .get("find", {})
        .get("where")
    )
    if not isinstance(where, list) or len(where) != 1 or not isinstance(where[0], str):
        _fail("package_contract_source_root_not_uniquely_declared")
    source_root = where[0].strip().strip("/")
    if not source_root or source_root.startswith(".") or "\\" in source_root:
        _fail("package_contract_source_root_invalid")
    return PackageContract(
        name=name, version=version, scripts=scripts, source=pyproject, source_root=source_root
    )


# --------------------------------------------------------------------------- #
# Source identity
# --------------------------------------------------------------------------- #


def _git_bytes(repo: Path, *args: str) -> bytes | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout


def _git_text(repo: Path, *args: str) -> str | None:
    raw = _git_bytes(repo, *args)
    if raw is None:
        return None
    return raw.decode("utf-8", errors="replace").strip()


def read_source_identity(repo: Path) -> tuple[str, str]:
    sha = _git_text(repo, "rev-parse", "HEAD")
    tree = _git_text(repo, "rev-parse", "HEAD^{tree}")
    if sha is None or not SHA_RE.match(sha):
        _unknown("source_sha_not_resolvable")
    if tree is None or not SHA_RE.match(tree):
        _unknown("source_tree_not_resolvable")
    return sha, tree


def assert_clean_working_tree(repo: Path) -> None:
    """No tracked file may differ from ``HEAD`` (staged or unstaged).

    Untracked files are not ignored silently: any untracked file that reaches the
    wheel payload is caught by the wheel-to-source binding as an extra file.
    """
    status = _git_text(repo, "status", "--porcelain=v1", "--untracked-files=no")
    if status is None:
        _unknown("source_working_tree_status_unavailable")
    if status:
        _fail("source_working_tree_dirty", f"tracked_changes={len(status.splitlines())}")


def assert_source_binding(
    sha: str, tree: str, expected_sha: str | None, expected_tree: str | None
) -> None:
    if expected_sha is not None and expected_sha != sha:
        _fail("source_sha_mismatch", f"expected={expected_sha} observed={sha}")
    if expected_tree is not None and expected_tree != tree:
        _fail("source_tree_mismatch", f"expected={expected_tree} observed={tree}")


def read_tracked_source_files(repo: Path, source_root: str) -> dict[str, str]:
    """Map wheel-relative path -> git blob object id for every file under the root."""
    raw = _git_bytes(repo, "ls-tree", "-r", "-z", "--full-tree", "HEAD", "--", source_root)
    if raw is None:
        _unknown("source_tree_listing_unavailable")
    prefix = f"{source_root}/"
    tracked: dict[str, str] = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        meta, _, path_bytes = entry.partition(b"\t")
        fields = meta.split()
        if len(fields) != 3:
            _unknown("source_tree_listing_malformed")
        mode, kind, object_id = (field.decode("ascii", errors="replace") for field in fields)
        path = path_bytes.decode("utf-8", errors="surrogateescape")
        if kind != "blob" or mode == "120000":
            _fail("source_tree_entry_unsupported", f"{kind}:{mode}")
        if not path.startswith(prefix):
            _unknown("source_tree_listing_outside_root")
        tracked[path.removeprefix(prefix)] = object_id
    if not tracked:
        _fail("source_tree_has_no_package_files", source_root)
    return tracked


def _git_blob_id(data: bytes, object_id_length: int) -> str:
    algorithm = "sha256" if object_id_length == 64 else "sha1"
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.new(algorithm, header + data).hexdigest()


def verify_wheel_source_binding(
    repo: Path, wheel: Path, contract: PackageContract
) -> dict[str, Any]:
    """Prove the wheel's package payload is exactly the git-tracked source at HEAD."""
    tracked = read_tracked_source_files(repo, contract.source_root)
    try:
        with zipfile.ZipFile(wheel) as archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            names = [info.filename for info in members]
            if len(set(names)) != len(names):
                _fail("wheel_archive_has_duplicate_members")
            dist_info_dirs = sorted(
                {
                    name.split("/", 1)[0]
                    for name in names
                    if "/" in name and name.split("/", 1)[0].endswith(".dist-info")
                }
            )
            project_dist_info = [
                directory
                for directory in dist_info_dirs
                if normalize_distribution_name(directory.split("-", 1)[0])
                == contract.normalized_name
            ]
            if len(dist_info_dirs) != 1 or len(project_dist_info) != 1:
                _fail("wheel_dist_info_not_uniquely_resolved", str(len(dist_info_dirs)))
            dist_info_dir = _only_text(
                project_dist_info, code="wheel_dist_info_not_uniquely_resolved"
            )
            dist_info_prefix = f"{dist_info_dir}/"
            payload: dict[str, bytes] = {
                info.filename: archive.read(info)
                for info in members
                if not info.filename.startswith(dist_info_prefix)
            }
    except (OSError, zipfile.BadZipFile) as exc:
        _fail("wheel_archive_unreadable", type(exc).__name__)

    different = sorted(
        path
        for path, data in payload.items()
        if path in tracked and _git_blob_id(data, len(tracked[path])) != tracked[path]
    )
    extra = sorted(set(payload) - set(tracked))
    missing = sorted(set(tracked) - set(payload))
    counts = f"different={len(different)},extra={len(extra)},missing={len(missing)}"
    if different:
        _fail("wheel_payload_differs_from_source", counts)
    if extra:
        _fail("wheel_payload_has_files_not_in_source", counts)
    if missing:
        _fail("wheel_payload_missing_source_files", counts)
    return {
        "status": PASS,
        "package_source_root": contract.source_root,
        "compared_files": len(tracked),
        "different": 0,
        "extra": 0,
        "missing": 0,
        "comparison": "git_blob_object_id_of_each_wheel_member_vs_HEAD",
    }


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
        _unknown("artifact_not_readable", type(exc).__name__)
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
# Dependency lock
# --------------------------------------------------------------------------- #


def read_dependency_lock(lock: Path) -> dict[str, tuple[str, frozenset[str]]]:
    """Parse the hash-pinned lock into ``{normalized name: (version, sha256 set)}``."""
    if not lock.is_file():
        _fail("dependency_lock_missing", lock.name)
    try:
        text = lock.read_text(encoding="utf-8")
    except OSError as exc:
        _unknown("dependency_lock_unreadable", type(exc).__name__)
    logical: list[str] = []
    buffer = ""
    for raw_line in text.splitlines():
        line = raw_line.split(" #", 1)[0].rstrip() if not raw_line.lstrip().startswith("#") else ""
        if line.endswith("\\"):
            buffer += line[:-1] + " "
            continue
        buffer += line
        if buffer.strip():
            logical.append(buffer.strip())
        buffer = ""
    if buffer.strip():
        logical.append(buffer.strip())

    pins: dict[str, tuple[str, frozenset[str]]] = {}
    for entry in logical:
        tokens = entry.split()
        requirement = tokens[0] if tokens else ""
        if requirement.startswith("-") or "==" not in requirement:
            _fail("dependency_lock_entry_not_pinned", requirement[:80])
        name, _, version = requirement.partition("==")
        version = version.split(";", 1)[0].strip()
        hashes = frozenset(
            token.removeprefix("--hash=sha256:")
            for token in tokens[1:]
            if token.startswith("--hash=sha256:")
        )
        if not hashes or not all(SHA256_RE.match(value) for value in hashes):
            _fail("dependency_lock_entry_not_hash_pinned", name)
        key = normalize_distribution_name(name.split("[", 1)[0])
        if key in pins:
            _fail("dependency_lock_entry_duplicated", key)
        pins[key] = (version, hashes)
    if not pins:
        _fail("dependency_lock_empty", lock.name)
    return pins


def verify_wheelhouse(
    wheelhouse: Path, pins: dict[str, tuple[str, frozenset[str]]]
) -> dict[str, str]:
    """Every wheelhouse file must be a lock-pinned wheel with a lock-listed hash."""
    files = sorted(path for path in wheelhouse.iterdir())
    observed: dict[str, str] = {}
    for path in files:
        if not path.is_file() or path.suffix != ".whl":
            _fail("wheelhouse_contains_non_wheel", path.name)
        parts = path.name.split("-")
        if len(parts) < 5:
            _fail("wheelhouse_wheel_filename_malformed", path.name)
        key = normalize_distribution_name(parts[0])
        version = parts[1].replace("_", "-")
        pin = pins.get(key)
        if pin is None:
            _fail("wheelhouse_wheel_not_in_lock", key)
        if version != pin[0]:
            _fail("wheelhouse_wheel_version_not_lock_pinned", f"{key}={version}")
        if sha256_file(path) not in pin[1]:
            _fail("wheelhouse_wheel_hash_not_in_lock", key)
        if key in observed:
            _fail("wheelhouse_wheel_ambiguous", key)
        observed[key] = version
    return observed


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


def _only_text(items: list[str], *, code: str) -> str:
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


def download_child_environment() -> dict[str, str]:
    """The isolated environment plus proxy/CA settings, for the download step only."""
    environment = isolated_child_environment()
    for variable in NETWORK_PASSTHROUGH_VARIABLES:
        value = os.environ.get(variable)
        if value:
            environment[variable] = value
    return environment


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
        _fail("command_timed_out", Path(command[0]).name)
    except OSError as exc:
        _unknown("command_not_executable", type(exc).__name__)
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


def read_include_system_site_packages(venv_dir: Path) -> bool | None:
    """The observed ``include-system-site-packages`` value, or ``None`` if absent."""
    config = venv_dir / "pyvenv.cfg"
    if not config.is_file():
        _fail("isolated_environment_config_missing")
    observed: bool | None = None
    for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
        key, _, value = line.partition("=")
        if key.strip().lower() == "include-system-site-packages":
            normalized = value.strip().lower()
            observed = True if normalized == "true" else False if normalized == "false" else None
    return observed


def create_isolated_environment(venv_dir: Path, *, scratch_dir: Path) -> bool | None:
    """Create the venv and return the observed system-site-packages flag."""
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
    include_system = read_include_system_site_packages(venv_dir)
    if include_system is not False:
        _fail("isolated_environment_inherits_system_site_packages", str(include_system))
    if not venv_bin(venv_dir, "python").is_file():
        _fail("isolated_environment_interpreter_missing")
    return include_system


def download_command(interpreter: str, dependency_lock: str, wheelhouse: str) -> list[str]:
    return [
        interpreter,
        "-m",
        "pip",
        "download",
        "--no-deps",
        "--require-hashes",
        "--only-binary=:all:",
        "--requirement",
        dependency_lock,
        "--dest",
        wheelhouse,
    ]


def project_install_command(interpreter: str, wheelhouse: str, wheel: str) -> list[str]:
    return [
        interpreter,
        "-m",
        "pip",
        "--isolated",
        "install",
        "--no-index",
        "--only-binary=:all:",
        "--find-links",
        wheelhouse,
        wheel,
    ]


def _redacted(command: list[str], replacements: dict[str, str]) -> list[str]:
    """The command with absolute paths replaced by stable placeholders."""
    rendered = [replacements.get(token, token) for token in command]
    rendered[0] = "<isolated python>"
    return rendered


def provision_wheelhouse(
    interpreter: Path,
    dependency_lock: Path,
    wheelhouse: Path,
    pins: dict[str, tuple[str, frozenset[str]]],
    *,
    scratch_dir: Path,
) -> dict[str, str]:
    if wheelhouse.exists():
        _fail("wheelhouse_preexisting", wheelhouse.name)
    wheelhouse.mkdir(parents=True)
    completed = _run(
        download_command(str(interpreter), str(dependency_lock), str(wheelhouse)),
        cwd=scratch_dir,
        env=download_child_environment(),
        timeout=DEFAULT_INSTALL_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        _fail("dependency_download_failed", f"exit={completed.returncode}")
    return verify_wheelhouse(wheelhouse, pins)


def install_wheel_from_artifact(
    interpreter: Path, wheel: Path, wheelhouse: Path, *, scratch_dir: Path
) -> None:
    completed = _run(
        project_install_command(str(interpreter), str(wheelhouse), str(wheel)),
        cwd=scratch_dir,
        env=isolated_child_environment(),
        timeout=DEFAULT_INSTALL_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        _fail("wheel_install_failed", f"exit={completed.returncode}")


def verify_install_source(
    venv_dir: Path, wheel: Path, wheel_sha256: str, contract: PackageContract
) -> dict[str, Any]:
    """Prove the installed distribution came from this wheel, not a source tree.

    Every returned field is observed from the installed environment.
    """
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
    dist_info = _only(dist_infos, code="installed_distribution_not_uniquely_resolved")

    direct_url = dist_info / "direct_url.json"
    if not direct_url.is_file():
        _fail("install_source_not_recorded", "direct_url.json_absent")
    try:
        payload = json.loads(direct_url.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _unknown("install_source_record_unreadable", type(exc).__name__)
    if not isinstance(payload, dict):
        _fail("install_source_record_malformed")
    dir_info = payload.get("dir_info")
    if dir_info:
        _fail("install_source_is_directory_not_wheel")
    archive_info = payload.get("archive_info")
    if not isinstance(archive_info, dict):
        _fail("install_source_record_has_no_archive_info")
    url = payload.get("url")
    recorded_filename = os.path.basename(url) if isinstance(url, str) else None
    if not isinstance(recorded_filename, str) or recorded_filename != wheel.name:
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
    observed_source = "wheel" if recorded_filename.endswith(".whl") else "archive"
    return {
        "dist_info": dist_info.name,
        "direct_url_filename": recorded_filename,
        "direct_url_sha256": recorded_sha,
        "editable": bool(editable_markers) or bool(dir_info),
        "install_source": observed_source,
    }


# --------------------------------------------------------------------------- #
# Probe programs executed inside the isolated environment.
# --------------------------------------------------------------------------- #

_PROBE_COMMON = r"""
import json
import os
import re
import sys
import sysconfig
import importlib
import importlib.metadata as metadata


def canonical(name):
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def distributions():
    found = {}
    duplicates = []
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if not name:
            continue
        key = canonical(name)
        if key in found:
            duplicates.append(key)
        found[key] = dist.version
    return found, sorted(duplicates)


payload = {
    "sys_path": list(sys.path),
    "sys_prefix": sys.prefix,
    "purelib": sysconfig.get_paths()["purelib"],
    "python_version": sys.version.split()[0],
    "python_implementation": sys.implementation.name,
    "isolated_flag": sys.flags.isolated,
    "pythonpath_present": "PYTHONPATH" in os.environ,
    "pythonhome_present": "PYTHONHOME" in os.environ,
}
payload["distributions"], payload["duplicate_distributions"] = distributions()
"""

BASELINE_PROBE_PROGRAM = (
    _PROBE_COMMON
    + r"""
print(json.dumps(payload))
"""
)

PROBE_PROGRAM = (
    _PROBE_COMMON
    + r"""
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
    project = metadata.distribution(distribution)
except metadata.PackageNotFoundError:
    project = None
payload["dist_name"] = project.metadata["Name"] if project is not None else None
payload["dist_version"] = project.version if project is not None else None
payload["console_scripts"] = (
    {ep.name: ep.value for ep in project.entry_points if ep.group == "console_scripts"}
    if project is not None
    else None
)

try:
    from pip._vendor.packaging.requirements import Requirement
except Exception:
    Requirement = None

if Requirement is None or project is None:
    payload["dependency_check"] = "unavailable"
else:
    declared = []
    satisfied = []
    unresolved = []
    closure = {}
    queue = [(canonical(distribution), ("",), True)]
    seen = set()
    while queue:
        name, extras, top_level = queue.pop()
        if (name, extras) in seen:
            continue
        seen.add((name, extras))
        try:
            requirements = metadata.requires(name) or []
        except metadata.PackageNotFoundError:
            unresolved.append({"requirement": name, "reason": "not_installed"})
            continue
        for raw in requirements:
            requirement = Requirement(raw)
            if requirement.marker is not None and not any(
                requirement.marker.evaluate({"extra": extra}) for extra in extras
            ):
                continue
            if top_level:
                declared.append(raw)
            dependency = canonical(requirement.name)
            try:
                installed_version = metadata.version(dependency)
            except metadata.PackageNotFoundError:
                unresolved.append({"requirement": raw, "reason": "not_installed"})
                continue
            if requirement.specifier and not requirement.specifier.contains(
                installed_version, prereleases=True
            ):
                unresolved.append(
                    {
                        "requirement": raw,
                        "reason": "version_not_satisfied",
                        "installed_version": installed_version,
                    }
                )
                continue
            if top_level:
                satisfied.append({"requirement": raw, "installed_version": installed_version})
            closure[dependency] = installed_version
            requested = tuple(sorted({""} | {canonical(extra) for extra in requirement.extras}))
            queue.append((dependency, requested, False))
    payload["dependency_check"] = "complete"
    payload["declared_requirements"] = sorted(declared)
    payload["runtime_requirements_satisfied"] = satisfied
    payload["runtime_requirements_unresolved"] = unresolved
    payload["closure"] = dict(sorted(closure.items()))

print(json.dumps(payload))
"""
)


def _run_probe(
    venv_dir: Path, program: str, arguments: list[str], *, scratch_dir: Path
) -> dict[str, Any]:
    completed = _run(
        [str(_venv_python(venv_dir)), "-I", "-c", program, *arguments],
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
        _unknown("installed_import_probe_output_not_json", type(exc).__name__)
    if not isinstance(payload, dict):
        _unknown("installed_import_probe_output_not_object")
    return payload


def run_baseline_probe(venv_dir: Path, *, scratch_dir: Path) -> dict[str, Any]:
    """Observe the fresh environment before anything is installed into it."""
    payload = _run_probe(venv_dir, BASELINE_PROBE_PROGRAM, [], scratch_dir=scratch_dir)
    if str(payload.get("sys_prefix")) != str(venv_dir.resolve()):
        _fail("probe_interpreter_is_not_the_isolated_environment")
    baseline = payload.get("distributions")
    if not isinstance(baseline, dict):
        _unknown("isolated_environment_baseline_not_observable")
    unexpected = sorted(set(baseline) - PERMITTED_BASELINE_DISTRIBUTIONS)
    if unexpected:
        _fail("isolated_environment_baseline_not_clean", ",".join(unexpected))
    return payload


def run_installed_probe(
    venv_dir: Path,
    *,
    module_name: str,
    distribution: str,
    forbidden_roots: list[Path],
    scratch_dir: Path,
) -> dict[str, Any]:
    """Run the import/closure probe and adjudicate import provenance.

    Returns the raw probe payload together with the adjudicated import record under
    ``"installed_import"``. Dependency-closure adjudication is done by the caller,
    which owns the lock and the baseline.
    """
    payload = probe_installed_environment(
        venv_dir, module_name=module_name, distribution=distribution, scratch_dir=scratch_dir
    )
    return adjudicate_installed_import(
        payload, venv_dir, module_name=module_name, forbidden_roots=forbidden_roots
    )


def probe_installed_environment(
    venv_dir: Path, *, module_name: str, distribution: str, scratch_dir: Path
) -> dict[str, Any]:
    """The raw observation of the installed environment, not yet adjudicated."""
    return _run_probe(venv_dir, PROBE_PROGRAM, [module_name, distribution], scratch_dir=scratch_dir)


def adjudicate_installed_import(
    payload: dict[str, Any], venv_dir: Path, *, module_name: str, forbidden_roots: list[Path]
) -> dict[str, Any]:
    """Fail closed unless the import came from the isolated installation."""
    purelib = Path(str(payload.get("purelib", "")))
    module_file_raw = payload.get("module_file")
    if payload.get("import_ok") is not True or not isinstance(module_file_raw, str):
        _fail(
            "installed_import_failed", str(payload.get("import_error_type") or "module_file_absent")
        )
    module_file = Path(module_file_raw).resolve()
    leaked = [
        entry
        for entry in payload.get("sys_path", [])
        if any(_under(Path(entry).resolve(), root) for root in forbidden_roots)
    ]
    if leaked:
        _fail("source_tree_leaked_onto_isolated_sys_path", f"entries={len(leaked)}")
    if not _under(module_file, purelib):
        _fail("installed_import_resolved_outside_isolated_environment", module_file.name)
    if str(payload.get("sys_prefix")) != str(venv_dir.resolve()):
        _fail("probe_interpreter_is_not_the_isolated_environment")
    if payload.get("isolated_flag") != 1:
        _fail("probe_interpreter_not_isolated")
    if (
        payload.get("pythonpath_present") is not False
        or payload.get("pythonhome_present") is not False
    ):
        _fail("probe_environment_not_scrubbed")
    if payload.get("dependency_check") != "complete":
        _fail("runtime_dependency_satisfaction_not_verifiable")
    unresolved = payload.get("runtime_requirements_unresolved")
    if unresolved:
        _fail("runtime_dependencies_unresolved", json.dumps(unresolved, sort_keys=True))
    payload["installed_import"] = {
        "status": PASS,
        "module": module_name,
        "module_file_relative_to_purelib": module_file.relative_to(purelib).as_posix(),
        "resolved_in_isolated_environment": True,
        "python_version": payload.get("python_version"),
        "python_implementation": payload.get("python_implementation"),
        "dist_version": payload.get("dist_version"),
        "sys_path_entry_count": len(payload.get("sys_path", [])),
    }
    return payload


def adjudicate_dependency_closure(
    payload: dict[str, Any],
    *,
    baseline: dict[str, str],
    project: str,
    pins: dict[str, tuple[str, frozenset[str]]],
) -> dict[str, Any]:
    """Nothing outside the wheel's declared closure, everything at the lock pin."""
    installed = payload.get("distributions")
    closure = payload.get("closure")
    if not isinstance(installed, dict) or not isinstance(closure, dict):
        _fail("runtime_dependency_satisfaction_not_verifiable")
    if payload.get("duplicate_distributions"):
        _fail("installed_distributions_duplicated", ",".join(payload["duplicate_distributions"]))
    added = {
        name: version
        for name, version in installed.items()
        if name != project and not (name in baseline and baseline[name] == version)
    }
    outside = sorted(set(added) - set(closure))
    not_pinned = sorted(
        name for name, version in closure.items() if name not in pins or pins[name][0] != version
    )
    record = {
        "status": PASS,
        "declared_requirements": payload.get("declared_requirements", []),
        "runtime_requirements_satisfied": payload.get("runtime_requirements_satisfied", []),
        "closure": dict(sorted(closure.items())),
        "installed_distributions": dict(sorted(installed.items())),
        "baseline_distributions": dict(sorted(baseline.items())),
        "outside_declared_closure": outside,
        "not_lock_pinned": not_pinned,
    }
    if outside:
        _fail("installed_distributions_outside_declared_closure", ",".join(outside))
    if not_pinned:
        _fail("installed_dependency_not_lock_pinned", ",".join(not_pinned))
    return record


def probe_console_entrypoints(
    venv_dir: Path,
    contract: PackageContract,
    *,
    installed_console_scripts: dict[str, str] | None,
    scratch_dir: Path,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    installed = installed_console_scripts or {}
    for script_name, target in contract.scripts.items():
        executable = venv_bin(venv_dir, script_name)
        record: dict[str, Any] = {
            "status": PASS,
            "name": script_name,
            "target": target,
            "installed_target": installed.get(script_name),
        }
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
        if record["installed_target"] != target:
            record["status"] = FAIL
            record["reason"] = "cli_entrypoint_target_mismatch"
        elif completed.returncode != 0:
            record["status"] = FAIL
            record["reason"] = "cli_entrypoint_failed"
        results.append(record)
    return results


# --------------------------------------------------------------------------- #
# Evidence document
# --------------------------------------------------------------------------- #

EVIDENCE_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "generated_by",
        "source_sha",
        "source_tree",
        "source_working_tree_clean",
        "wheel_filename",
        "wheel_sha256",
        "wheel_source_binding",
        "package_name",
        "package_version",
        "declared_version",
        "python_version",
        "install_source",
        "install",
        "environment",
        "dependency_closure",
        "installed_import",
        "cli_entrypoints",
        "cli_entrypoint_results",
        "package_contract",
        "expected_bindings",
        "overall_classification",
        "reasons",
        "hidden_information",
        "production_provider",
        "architecture_freeze",
    }
)

INSTALL_KEYS = frozenset(
    {
        "dist_info",
        "direct_url_filename",
        "direct_url_sha256",
        "editable",
        "install_source",
        "index_access",
        "project_install_command",
        "dependency_provisioning_command",
        "dependency_lock",
        "dependency_lock_sha256",
        "wheelhouse",
    }
)
ENVIRONMENT_KEYS = frozenset(
    {
        "created_by_this_run",
        "include_system_site_packages",
        "python_isolated_flag",
        "pythonpath_in_probe_environment",
        "pythonhome_in_probe_environment",
        "probe_cwd_outside_repository",
        "sys_prefix_is_isolated_environment",
        "forbidden_import_roots",
        "wheel_selection",
    }
)
INSTALLED_IMPORT_KEYS = frozenset(
    {
        "status",
        "module",
        "module_file_relative_to_purelib",
        "resolved_in_isolated_environment",
        "python_version",
        "python_implementation",
        "dist_version",
        "sys_path_entry_count",
    }
)
CLI_RECORD_KEYS = frozenset(
    {
        "status",
        "name",
        "target",
        "installed_target",
        "returncode",
        "argument",
        "stdout_bytes",
        "stdout_sha256",
        "stderr_bytes",
    }
)
BINDING_KEYS = frozenset(
    {
        "status",
        "package_source_root",
        "compared_files",
        "different",
        "extra",
        "missing",
        "comparison",
    }
)
CLOSURE_KEYS = frozenset(
    {
        "status",
        "declared_requirements",
        "runtime_requirements_satisfied",
        "closure",
        "installed_distributions",
        "baseline_distributions",
        "outside_declared_closure",
        "not_lock_pinned",
    }
)
EXPECTED_BINDING_KEYS = frozenset({"source_sha", "source_tree", "wheel_sha256", "package_version"})
CONTRACT_KEYS = frozenset(
    {
        "name",
        "normalized_name",
        "declared_version",
        "declared_scripts",
        "contract_source",
        "package_source_root",
    }
)


class SmokeState:
    """Everything the smoke observed so far; unobserved fields stay ``None``."""

    def __init__(self) -> None:
        self.contract: PackageContract | None = None
        self.source_sha: str | None = None
        self.source_tree: str | None = None
        self.working_tree_clean: bool | None = None
        self.wheel_filename: str | None = None
        self.wheel_sha256: str | None = None
        self.wheel_source_binding: dict[str, Any] | None = None
        self.installed_name: str | None = None
        self.installed_version: str | None = None
        self.python_version: str | None = None
        self.install: dict[str, Any] = {key: None for key in INSTALL_KEYS}
        self.environment: dict[str, Any] = {key: None for key in ENVIRONMENT_KEYS}
        self.dependency_closure: dict[str, Any] | None = None
        self.installed_import: dict[str, Any] | None = None
        self.cli_entrypoints: list[dict[str, Any]] | None = None
        self.expected_binding: dict[str, Any] | None = None


def build_evidence(
    state: SmokeState, *, import_module: str, classification: str, reasons: list[str]
) -> dict[str, Any]:
    contract = state.contract
    cli_entrypoints = state.cli_entrypoints or []
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "source_sha": state.source_sha,
        "source_tree": state.source_tree,
        "source_working_tree_clean": state.working_tree_clean,
        "wheel_filename": state.wheel_filename,
        "wheel_sha256": state.wheel_sha256,
        "wheel_source_binding": state.wheel_source_binding,
        "package_name": state.installed_name,
        "package_version": state.installed_version,
        "declared_version": contract.version if contract is not None else None,
        "python_version": state.python_version,
        "install_source": state.install.get("install_source"),
        "install": dict(state.install),
        "environment": dict(state.environment),
        "dependency_closure": state.dependency_closure,
        "installed_import": state.installed_import or {"status": FAIL, "module": import_module},
        "cli_entrypoints": cli_entrypoints,
        "cli_entrypoint_results": {
            record["name"]: record for record in cli_entrypoints if isinstance(record, dict)
        },
        "package_contract": contract.to_json() if contract is not None else None,
        "expected_bindings": state.expected_binding,
        "overall_classification": classification,
        "reasons": list(reasons),
        "hidden_information": HIDDEN_INFORMATION,
        "production_provider": PRODUCTION_PROVIDER,
        "architecture_freeze": ARCHITECTURE_FREEZE,
    }


def write_evidence(output: Path, evidence: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_name(output.name + ".tmp")
    staging.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(staging, output)


def remove_previous_evidence(output: Path) -> None:
    """A previous evidence document must never survive into this run."""
    if output.is_dir():
        _fail("evidence_output_is_a_directory", output.name)
    try:
        output.unlink(missing_ok=True)
    except OSError as exc:
        _unknown("previous_evidence_not_removable", type(exc).__name__)


# --------------------------------------------------------------------------- #
# mode: smoke
# --------------------------------------------------------------------------- #


def _smoke_body(args: argparse.Namespace, state: SmokeState) -> None:
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
    wheelhouse = scratch_dir / f"{venv_dir.name}-wheelhouse"

    if any(
        value is not None
        for value in (
            args.expect_source_sha,
            args.expect_source_tree,
            args.expect_wheel_sha256,
            args.expect_version,
        )
    ):
        state.expected_binding = {
            "source_sha": args.expect_source_sha,
            "source_tree": args.expect_source_tree,
            "wheel_sha256": args.expect_wheel_sha256,
            "package_version": args.expect_version,
        }

    state.environment["wheel_selection"] = WHEEL_SELECTION_POLICY
    state.environment["probe_cwd_outside_repository"] = not _under(scratch_dir, repo)
    if _under(scratch_dir, repo):
        _fail("scratch_dir_inside_repository")
    if _under(venv_dir, repo):
        _fail("isolated_environment_inside_repository")

    state.source_sha, state.source_tree = read_source_identity(repo)
    assert_clean_working_tree(repo)
    state.working_tree_clean = True
    state.contract = contract = read_package_contract(pyproject)
    forbidden_roots = [repo, repo / contract.source_root]
    state.environment["forbidden_import_roots"] = [
        REPOSITORY_PLACEHOLDER,
        f"{REPOSITORY_PLACEHOLDER}/{contract.source_root}",
    ]
    pins = read_dependency_lock(dependency_lock)
    state.install["dependency_lock"] = dependency_lock.name
    state.install["dependency_lock_sha256"] = sha256_file(dependency_lock)

    wheel = select_project_wheel(wheel_dir, contract)
    state.wheel_filename = wheel.name
    state.wheel_sha256 = wheel_sha256 = sha256_file(wheel)
    if args.expect_wheel_sha256 is not None and args.expect_wheel_sha256 != wheel_sha256:
        _fail(
            "wheel_digest_mismatch", f"expected={args.expect_wheel_sha256} observed={wheel_sha256}"
        )
    assert_source_binding(
        state.source_sha, state.source_tree, args.expect_source_sha, args.expect_source_tree
    )
    state.wheel_source_binding = verify_wheel_source_binding(repo, wheel, contract)

    scratch_dir.mkdir(parents=True, exist_ok=True)
    venv_preexisting = venv_dir.exists()
    state.environment["created_by_this_run"] = not venv_preexisting
    state.environment["include_system_site_packages"] = create_isolated_environment(
        venv_dir, scratch_dir=scratch_dir
    )
    interpreter = _venv_python(venv_dir)

    baseline_payload = run_baseline_probe(venv_dir, scratch_dir=scratch_dir)
    state.python_version = str(baseline_payload.get("python_version") or "") or None
    if not state.python_version:
        _unknown("isolated_python_version_not_resolvable")
    baseline: dict[str, str] = dict(baseline_payload["distributions"])

    replacements = {
        str(interpreter): "<isolated python>",
        str(dependency_lock): LOCK_PLACEHOLDER,
        str(wheelhouse): WHEELHOUSE_PLACEHOLDER,
        str(wheel): WHEEL_PLACEHOLDER,
    }
    state.install["dependency_provisioning_command"] = _redacted(
        download_command(str(interpreter), str(dependency_lock), str(wheelhouse)), replacements
    )
    install_command = project_install_command(str(interpreter), str(wheelhouse), str(wheel))
    state.install["project_install_command"] = _redacted(install_command, replacements)
    state.install["index_access"] = "disabled" if "--no-index" in install_command else "enabled"

    wheelhouse_files = provision_wheelhouse(
        interpreter, dependency_lock, wheelhouse, pins, scratch_dir=scratch_dir
    )
    state.install["wheelhouse"] = {
        "files": len(wheelhouse_files),
        "every_file_lock_pinned_and_hash_listed": True,
    }
    install_wheel_from_artifact(interpreter, wheel, wheelhouse, scratch_dir=scratch_dir)
    state.install.update(verify_install_source(venv_dir, wheel, wheel_sha256, contract))

    payload = probe_installed_environment(
        venv_dir,
        module_name=args.import_module,
        distribution=contract.normalized_name,
        scratch_dir=scratch_dir,
    )
    observed = payload.get("distributions")
    state.dependency_closure = {key: None for key in CLOSURE_KEYS}
    state.dependency_closure["status"] = "NOT_ADJUDICATED"
    state.dependency_closure["baseline_distributions"] = dict(sorted(baseline.items()))
    state.dependency_closure["installed_distributions"] = (
        dict(sorted(observed.items())) if isinstance(observed, dict) else None
    )
    state.environment["python_isolated_flag"] = payload.get("isolated_flag")
    state.environment["pythonpath_in_probe_environment"] = payload.get("pythonpath_present")
    state.environment["pythonhome_in_probe_environment"] = payload.get("pythonhome_present")
    state.environment["sys_prefix_is_isolated_environment"] = str(payload.get("sys_prefix")) == str(
        venv_dir.resolve()
    )
    adjudicate_installed_import(
        payload, venv_dir, module_name=args.import_module, forbidden_roots=forbidden_roots
    )
    state.installed_name = payload.get("dist_name")
    state.installed_version = installed_version = payload.get("dist_version")
    if installed_version is None or state.installed_name is None:
        _fail("installed_distribution_metadata_not_resolvable")
    if normalize_distribution_name(str(state.installed_name)) != contract.normalized_name:
        _fail("installed_distribution_name_mismatch", str(state.installed_name))
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
    state.installed_import = payload["installed_import"]
    state.dependency_closure = adjudicate_dependency_closure(
        payload, baseline=baseline, project=contract.normalized_name, pins=pins
    )

    state.cli_entrypoints = probe_console_entrypoints(
        venv_dir,
        contract,
        installed_console_scripts=payload.get("console_scripts"),
        scratch_dir=scratch_dir,
    )
    broken = sorted(
        f"{record['name']}:{record.get('reason', 'failed')}"
        for record in state.cli_entrypoints
        if record.get("status") != PASS
    )
    undeclared = sorted(set(payload.get("console_scripts") or {}) - set(contract.scripts))
    broken.extend(f"{name}:cli_entrypoint_not_declared" for name in undeclared)
    if broken:
        _fail("cli_entrypoint_smoke_failed", ",".join(broken))

    final_sha, final_tree = read_source_identity(repo)
    if (final_sha, final_tree) != (state.source_sha, state.source_tree):
        _fail("source_identity_drift_during_smoke")
    assert_clean_working_tree(repo)


def run_smoke(args: argparse.Namespace) -> int:
    output = Path(args.output).resolve()
    remove_previous_evidence(output)
    state = SmokeState()
    classification = PASS
    reasons: list[str] = []
    try:
        _smoke_body(args, state)
    except _Classification as failure:
        classification = failure.classification
        reasons.append(failure.code)
    except Exception as exc:  # fail closed: never leave a run without evidence
        classification = UNKNOWN
        reasons.append(f"unexpected_error:{type(exc).__name__}")

    write_evidence(
        output,
        build_evidence(
            state,
            import_module=args.import_module,
            classification=classification,
            reasons=reasons,
        ),
    )
    if classification == PASS:
        print(f"packaging smoke PASS: {state.wheel_filename} sha256={state.wheel_sha256}")
        return EXIT_CODES[PASS]
    print(f"packaging smoke {classification}: {', '.join(reasons)}", file=sys.stderr)
    return EXIT_CODES[classification]


# --------------------------------------------------------------------------- #
# mode: check
# --------------------------------------------------------------------------- #


def _mapping(
    document: dict[str, Any], key: str, required: frozenset[str], reasons: list[str]
) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        reasons.append(f"{key}_not_a_mapping")
        return {}
    for missing in sorted(required - set(value)):
        reasons.append(f"{key}_key_missing:{missing}")
    for unexpected in sorted(set(value) - required):
        reasons.append(f"{key}_key_unexpected:{unexpected}")
    return value


def _structural_reasons(document: dict[str, Any], import_module: str) -> list[str]:
    reasons: list[str] = []
    if document["schema_version"] != SCHEMA_VERSION:
        reasons.append(f"schema_version_unsupported:{document['schema_version']}")
    if document["generated_by"] != GENERATED_BY:
        reasons.append("generated_by_not_this_consumer")
    classification = document["overall_classification"]
    if classification != PASS:
        reasons.append(f"recorded_classification_not_pass:{classification}")
    recorded_reasons = document["reasons"]
    if not isinstance(recorded_reasons, list):
        reasons.append("reasons_not_a_list")
    elif classification == PASS and recorded_reasons:
        reasons.append("pass_recorded_with_failure_reasons")
    elif classification != PASS and not recorded_reasons:
        reasons.append("non_pass_recorded_without_reasons")
    for key, expected in (
        ("hidden_information", HIDDEN_INFORMATION),
        ("production_provider", PRODUCTION_PROVIDER),
        ("architecture_freeze", ARCHITECTURE_FREEZE),
    ):
        if document[key] != expected:
            reasons.append(f"{key}_claim_changed")
    if not SHA_RE.match(str(document["source_sha"])):
        reasons.append("source_sha_malformed")
    if not SHA_RE.match(str(document["source_tree"])):
        reasons.append("source_tree_malformed")
    if document["source_working_tree_clean"] is not True:
        reasons.append("evidence_working_tree_not_clean")
    if not SHA256_RE.match(str(document["wheel_sha256"])):
        reasons.append("wheel_sha256_malformed")
    if document["install_source"] != "wheel":
        reasons.append(f"install_source_not_wheel:{document['install_source']}")
    if not isinstance(document["python_version"], str) or not document["python_version"]:
        reasons.append("python_version_missing")
    elif document["python_version"] != sys.version.split()[0]:
        reasons.append("python_version_not_the_checking_interpreter")
    if document["package_version"] != document["declared_version"]:
        reasons.append("package_version_does_not_match_declared_version")
    filename = str(document["wheel_filename"])
    if not filename or "/" in filename or "\\" in filename or not filename.endswith(".whl"):
        reasons.append("wheel_filename_not_a_wheel_basename")

    install = _mapping(document, "install", INSTALL_KEYS, reasons)
    if install:
        if install.get("install_source") != "wheel":
            reasons.append("install_record_source_not_wheel")
        if install.get("install_source") != document["install_source"]:
            reasons.append("install_source_inconsistent")
        if install.get("editable") is not False:
            reasons.append("install_editable_not_false")
        if install.get("index_access") != "disabled":
            reasons.append("install_index_access_not_disabled")
        command = install.get("project_install_command")
        if not isinstance(command, list) or "--no-index" not in command:
            reasons.append("install_command_not_index_free")
        if install.get("direct_url_sha256") != document["wheel_sha256"]:
            reasons.append("install_direct_url_sha256_not_wheel_sha256")
        if install.get("direct_url_filename") != document["wheel_filename"]:
            reasons.append("install_direct_url_filename_not_wheel_filename")
        wheelhouse = install.get("wheelhouse")
        if (
            not isinstance(wheelhouse, dict)
            or wheelhouse.get("every_file_lock_pinned_and_hash_listed") is not True
        ):
            reasons.append("install_wheelhouse_not_hash_verified")

    environment = _mapping(document, "environment", ENVIRONMENT_KEYS, reasons)
    if environment:
        for key, required in (
            ("created_by_this_run", True),
            ("include_system_site_packages", False),
            ("python_isolated_flag", 1),
            ("pythonpath_in_probe_environment", False),
            ("pythonhome_in_probe_environment", False),
            ("probe_cwd_outside_repository", True),
            ("sys_prefix_is_isolated_environment", True),
        ):
            value = environment.get(key)
            if not (type(value) is type(required) and value == required):
                reasons.append(f"environment_invariant_violated:{key}")
        if environment.get("wheel_selection") != WHEEL_SELECTION_POLICY:
            reasons.append("environment_invariant_violated:wheel_selection")

    imported = _mapping(document, "installed_import", INSTALLED_IMPORT_KEYS, reasons)
    if imported:
        if imported.get("status") != PASS:
            reasons.append(f"installed_import_not_passed:{imported.get('status')}")
        if imported.get("resolved_in_isolated_environment") is not True:
            reasons.append("installed_import_not_proven_isolated")
        if imported.get("module") != import_module:
            reasons.append("installed_import_module_not_the_expected_module")
        module_path = import_module.replace(".", "/")
        relative = str(imported.get("module_file_relative_to_purelib") or "")
        if not (relative == f"{module_path}.py" or relative.startswith(f"{module_path}/")):
            reasons.append("installed_import_provenance_missing")
        if imported.get("python_version") != document["python_version"]:
            reasons.append("installed_import_python_version_inconsistent")
        if imported.get("dist_version") != document["package_version"]:
            reasons.append("installed_import_dist_version_inconsistent")

    binding = _mapping(document, "wheel_source_binding", BINDING_KEYS, reasons)
    if binding and (
        binding.get("status") != PASS
        or any(binding.get(key) != 0 for key in ("different", "extra", "missing"))
    ):
        reasons.append("wheel_source_binding_not_passed")

    closure = _mapping(document, "dependency_closure", CLOSURE_KEYS, reasons)
    if closure:
        if closure.get("status") != PASS:
            reasons.append("dependency_closure_not_passed")
        if closure.get("outside_declared_closure") != [] or closure.get("not_lock_pinned") != []:
            reasons.append("dependency_closure_violation_recorded")
        if not closure.get("runtime_requirements_satisfied"):
            reasons.append("dependency_closure_has_no_satisfied_requirements")

    expected = document["expected_bindings"]
    if expected is not None:
        if not isinstance(expected, dict) or set(expected) != EXPECTED_BINDING_KEYS:
            reasons.append("expected_bindings_malformed")
        else:
            for key in sorted(EXPECTED_BINDING_KEYS):
                if expected[key] is not None and expected[key] != document[key]:
                    reasons.append(f"expected_binding_mismatch:{key}")
    return reasons


def _cli_reasons(document: dict[str, Any], contract: PackageContract) -> list[str]:
    reasons: list[str] = []
    entrypoints = document["cli_entrypoints"]
    results = document["cli_entrypoint_results"]
    if not isinstance(entrypoints, list) or not all(
        isinstance(record, dict) for record in entrypoints
    ):
        return ["cli_entrypoints_not_a_list_of_records"]
    if not isinstance(results, dict):
        return ["cli_entrypoint_results_not_a_mapping"]
    by_name = {str(record.get("name")): record for record in entrypoints}
    if len(by_name) != len(entrypoints) or by_name != results:
        reasons.append("cli_entrypoint_results_inconsistent_with_cli_entrypoints")
    for script_name, target in contract.scripts.items():
        record = by_name.get(script_name)
        if record is None:
            reasons.append(f"cli_entrypoint_result_missing:{script_name}")
            continue
        for missing in sorted(CLI_RECORD_KEYS - set(record)):
            reasons.append(f"cli_entrypoint_record_key_missing:{script_name}:{missing}")
        for unexpected in sorted(set(record) - CLI_RECORD_KEYS):
            reasons.append(f"cli_entrypoint_record_key_unexpected:{script_name}:{unexpected}")
        if record.get("status") != PASS:
            reasons.append(f"cli_entrypoint_not_passed:{script_name}")
        if record.get("returncode") != 0 or isinstance(record.get("returncode"), bool):
            reasons.append(f"cli_entrypoint_nonzero_exit:{script_name}")
        if record.get("argument") != CLI_SMOKE_ARGUMENT:
            reasons.append(f"cli_entrypoint_argument_unexpected:{script_name}")
        if record.get("target") != target or record.get("installed_target") != target:
            reasons.append(f"cli_entrypoint_target_not_the_declared_target:{script_name}")
        if not SHA256_RE.match(str(record.get("stdout_sha256"))):
            reasons.append(f"cli_entrypoint_output_digest_malformed:{script_name}")
    unexpected_names = sorted(set(by_name) - set(contract.scripts))
    if unexpected_names:
        reasons.append(f"cli_entrypoint_result_unexpected:{','.join(unexpected_names)}")
    return reasons


def _contract_reasons(document: dict[str, Any], contract: PackageContract) -> list[str]:
    reasons: list[str] = []
    if normalize_distribution_name(str(document["package_name"])) != contract.normalized_name:
        reasons.append("package_name_not_the_project_distribution")
    if document["package_version"] != contract.version:
        reasons.append("package_version_not_the_current_declared_version")
    if document["declared_version"] != contract.version:
        reasons.append("declared_version_not_the_current_declared_version")
    recorded_contract = document["package_contract"]
    if not isinstance(recorded_contract, dict) or set(recorded_contract) != CONTRACT_KEYS:
        reasons.append("package_contract_malformed")
    elif recorded_contract != contract.to_json():
        reasons.append("package_contract_not_the_current_contract")
    reasons.extend(_cli_reasons(document, contract))
    return reasons


def _recomputed_reasons(
    document: dict[str, Any],
    *,
    repo: Path,
    contract: PackageContract,
    wheel_dir: Path,
    dependency_lock: Path,
) -> list[str]:
    """Everything the checker can recompute independently of the evidence."""
    reasons: list[str] = []
    try:
        head_sha, head_tree = read_source_identity(repo)
    except _Classification as failure:
        reasons.append(f"repository_identity_unavailable:{failure.code}")
    else:
        if document["source_sha"] != head_sha:
            reasons.append("evidence_source_sha_not_repository_head")
        if document["source_tree"] != head_tree:
            reasons.append("evidence_source_tree_not_repository_tree")
    try:
        assert_clean_working_tree(repo)
    except _Classification as failure:
        reasons.append(f"repository_not_clean:{failure.code}")

    try:
        pins = read_dependency_lock(dependency_lock)
        lock_sha256 = sha256_file(dependency_lock)
    except _Classification as failure:
        reasons.append(f"dependency_lock_unusable:{failure.code}")
    else:
        install = document["install"]
        if isinstance(install, dict):
            if install.get("dependency_lock_sha256") != lock_sha256:
                reasons.append("dependency_lock_digest_not_the_current_lock")
            if install.get("dependency_lock") != dependency_lock.name:
                reasons.append("dependency_lock_name_not_the_current_lock")
        closure = document["dependency_closure"]
        if isinstance(closure, dict):
            recorded = closure.get("closure")
            installed = closure.get("installed_distributions")
            baseline = closure.get("baseline_distributions")
            if not (
                isinstance(recorded, dict)
                and isinstance(installed, dict)
                and isinstance(baseline, dict)
            ):
                reasons.append("dependency_closure_malformed")
            else:
                unpinned = sorted(
                    name
                    for name, version in recorded.items()
                    if name not in pins or pins[name][0] != version
                )
                if unpinned:
                    reasons.append(f"dependency_closure_not_lock_pinned:{','.join(unpinned)}")
                added = {
                    name
                    for name, version in installed.items()
                    if name != contract.normalized_name and baseline.get(name) != version
                }
                if added != set(recorded):
                    reasons.append("dependency_closure_not_the_installed_set")
                if contract.normalized_name not in installed:
                    reasons.append("dependency_closure_missing_project_distribution")
                if set(baseline) - PERMITTED_BASELINE_DISTRIBUTIONS:
                    reasons.append("dependency_closure_baseline_not_clean")

    try:
        observed = select_project_wheel(wheel_dir, contract)
    except _Classification as failure:
        reasons.append(f"artifact_reverification_failed:{failure.code}")
        return reasons
    if observed.name != str(document["wheel_filename"]):
        reasons.append("artifact_reverification_filename_mismatch")
    observed_sha256 = sha256_file(observed)
    if observed_sha256 != str(document["wheel_sha256"]):
        reasons.append("artifact_reverification_digest_mismatch")
    install = document["install"]
    if isinstance(install, dict) and install.get("direct_url_sha256") != observed_sha256:
        reasons.append("artifact_reverification_install_digest_mismatch")
    try:
        binding = verify_wheel_source_binding(repo, observed, contract)
    except _Classification as failure:
        reasons.append(f"artifact_reverification_not_bound_to_source:{failure.code}")
    else:
        recorded_binding = document["wheel_source_binding"]
        if not isinstance(recorded_binding, dict) or recorded_binding != binding:
            reasons.append("wheel_source_binding_not_reproduced")
    return reasons


def check_evidence(args: argparse.Namespace) -> int:
    path = Path(args.evidence).resolve()
    if not path.is_file():
        print(f"packaging evidence missing: {path.name}", file=sys.stderr)
        return EXIT_CODES[FAIL]
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"packaging evidence unreadable: {type(exc).__name__}", file=sys.stderr)
        return EXIT_CODES[FAIL]
    if not isinstance(document, dict):
        print("packaging evidence is not a JSON object", file=sys.stderr)
        return EXIT_CODES[FAIL]

    missing = sorted(EVIDENCE_KEYS - set(document))
    unexpected = sorted(set(document) - EVIDENCE_KEYS)
    if missing or unexpected:
        problems = [f"evidence_required_key_missing:{key}" for key in missing]
        problems += [f"evidence_unexpected_key:{key}" for key in unexpected]
        print(
            "packaging evidence check FAIL: missing required keys or unexpected keys: "
            + "; ".join(problems),
            file=sys.stderr,
        )
        return EXIT_CODES[FAIL]

    repo = Path(args.repo).resolve()
    reasons = _structural_reasons(document, args.import_module)

    contract: PackageContract | None = None
    try:
        contract = read_package_contract(
            Path(args.pyproject).resolve() if args.pyproject else repo / "pyproject.toml"
        )
    except _Classification as failure:
        reasons.append(f"package_contract_unusable:{failure.code}")
    if contract is not None:
        reasons.extend(_contract_reasons(document, contract))
        reasons.extend(
            _recomputed_reasons(
                document,
                repo=repo,
                contract=contract,
                wheel_dir=Path(args.wheel_dir).resolve(),
                dependency_lock=(
                    Path(args.dependency_lock).resolve()
                    if args.dependency_lock
                    else repo / "requirements" / "lock.txt"
                ),
            )
        )

    if args.expect_source_sha is not None and str(document["source_sha"]) != args.expect_source_sha:
        reasons.append("evidence_source_sha_not_the_expected_candidate")
    if (
        args.expect_wheel_sha256 is not None
        and str(document["wheel_sha256"]) != args.expect_wheel_sha256
    ):
        reasons.append("evidence_wheel_digest_not_the_expected_artifact")

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

    check = subparsers.add_parser("check", help="independently re-adjudicate packaging evidence")
    check.add_argument("--evidence", required=True)
    check.add_argument("--repo", default=".")
    check.add_argument("--pyproject", default=None)
    check.add_argument("--dependency-lock", default=None)
    check.add_argument(
        "--wheel-dir",
        required=True,
        help="re-verify the bound wheel artifact digest and its binding to the source",
    )
    check.add_argument("--import-module", default=DEFAULT_IMPORT_MODULE)
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
