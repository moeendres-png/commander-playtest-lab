"""B9 packaging-smoke contract tests (issue #490).

The suite proves three distinct things:

* the **positive control really passes** — a real wheel built from the current
  source installs into a clean isolated environment, the installed package imports
  from that installation, and every currently declared console entrypoint runs;
* every required **red control** kills its failure class instead of passing — a
  broken, missing, ambiguous or tampered wheel, a version mismatch, a missing
  entrypoint, a source-tree-import substitution, an editable/contaminated install,
  and missing, malformed, ``UNKNOWN`` or unbound machine-readable evidence;
* the packaging smoke is wired into the required ``quality`` context without
  weakening any required-check static invariant.

The full-consumer-path controls deliberately use the real script entry point
rather than a helper function, so a guard that only works in isolation cannot
produce a false PASS.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

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

# Full-consumer-path controls cost one isolated environment each. Keep them bounded
# so a hung probe fails the control instead of stalling the suite.
FULL_PATH_TIMEOUT_SECONDS = 2400

_PROVENANCE_FAILURE_CODES = (
    "source_tree_leaked_onto_isolated_sys_path",
    "installed_import_resolved_outside_isolated_environment",
)


def _source_identity() -> tuple[str, str]:
    return packaging.read_source_identity(ROOT)


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
    wheel_dir: Path,
    work_dir: Path,
    *,
    extra: tuple[str, ...] = (),
    env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    output = work_dir / "evidence" / "PACKAGING_SMOKE.json"
    completed = _run_script(
        "smoke",
        "--repo",
        str(ROOT),
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


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """Build the actual wheel artifact from the current candidate source."""
    wheel_dir = tmp_path_factory.mktemp("b9-wheel-dir")
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
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=FULL_PATH_TIMEOUT_SECONDS,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-4000:]
    wheels = sorted(wheel_dir.glob("*.whl"))
    assert len(wheels) == 1, wheels
    return wheels[0], packaging.sha256_file(wheels[0])


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


def _mutated_pyproject(destination: Path, *, extra_script: str | None = None) -> Path:
    """Copy the live pyproject, optionally declaring an entrypoint the wheel lacks."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if extra_script is not None:
        marker = f"{next(iter(CONTRACT.scripts))} ="
        assert marker in text, marker
        text = text.replace(
            marker,
            f'{extra_script} = "commander_lab.cli.main:app"\n{marker}',
            1,
        )
    destination.write_text(text, encoding="utf-8")
    return destination


# --------------------------------------------------------------------------- #
# Positive control
# --------------------------------------------------------------------------- #


def test_positive_control_installs_imports_and_runs_every_declared_entrypoint(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    """A real wheel from the current source must PASS the whole consumer path."""
    wheel, wheel_sha256 = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    wheel_copy = wheel_dir / wheel.name
    wheel_copy.write_bytes(wheel.read_bytes())
    source_sha, source_tree = _source_identity()

    completed, document = _smoke(
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
    )

    assert completed.returncode == EXIT_PASS, completed.stdout + completed.stderr
    assert document["overall_classification"] == "PASS"
    assert document["reasons"] == ["all_packaging_smoke_invariants_satisfied"]
    # Bound to the exact candidate and the exact artifact.
    assert document["source_sha"] == source_sha
    assert document["source_tree"] == source_tree
    assert document["wheel_filename"] == wheel.name
    assert document["wheel_sha256"] == wheel_sha256
    assert document["wheel_sha256"] == packaging.sha256_file(wheel_copy)
    assert document["package_name"] == CONTRACT.name
    assert document["package_version"] == CONTRACT.version
    assert document["install_source"] == "wheel"
    assert document["python_version"].count(".") == 2
    # Installed from the wheel artifact, never an editable install or a directory.
    assert document["install"]["direct_url_sha256"] == wheel_sha256
    assert document["install"]["index_access"] == "disabled"
    assert document["install"]["editable"] is False
    assert document["install"]["dependency_lock_sha256"] == packaging.sha256_file(DEPENDENCY_LOCK)
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
    # The wheel's own runtime dependency closure is satisfied.
    satisfied = {
        item["requirement"]
        for item in document["installed_import"]["runtime_requirements_satisfied"]
    }
    assert satisfied, document["installed_import"]
    # No absolute temporary path is used as a semantic identity.
    rendered = json.dumps(document)
    assert str(work_dir) not in rendered
    assert "<repository>" in rendered

    checked = _run_script(
        "check",
        "--repo",
        str(ROOT),
        "--evidence",
        str(work_dir / "evidence" / "PACKAGING_SMOKE.json"),
        "--wheel-dir",
        str(wheel_dir),
        "--expect-source-sha",
        source_sha,
        "--expect-wheel-sha256",
        wheel_sha256,
    )
    assert checked.returncode == EXIT_PASS, checked.stdout + checked.stderr


def test_source_tree_exposure_in_the_ambient_environment_cannot_substitute_for_the_installation(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    """A maximally polluted caller environment must not be mistaken for the install.

    ``PYTHONPATH`` is pointed at the repository ``src`` and the caller runs from the
    repository root. The smoke still passes *and* still attests the installation,
    which is what makes the provenance guard in the decoy-wheel control meaningful:
    the guard is not a red-only assertion.
    """
    wheel, _ = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())

    polluted_env = dict(os.environ)
    polluted_env["PYTHONPATH"] = str(ROOT / "src")
    completed, document = _smoke(wheel_dir, work_dir, env=polluted_env)

    assert completed.returncode == EXIT_PASS, completed.stdout + completed.stderr
    assert document["environment"]["pythonpath_scrubbed"] is True
    assert document["installed_import"]["resolved_in_isolated_environment"] is True
    assert document["install_source"] == "wheel"


# --------------------------------------------------------------------------- #
# Red control 1: missing wheel
# --------------------------------------------------------------------------- #


def test_red_control_missing_project_wheel_fails_closed(work_dir: Path, tmp_path: Path) -> None:
    wheel_dir = tmp_path / "empty-dist"
    wheel_dir.mkdir()
    completed, _ = _smoke(wheel_dir, work_dir)
    assert completed.returncode == EXIT_FAIL
    assert "project_wheel_missing" in completed.stderr
    assert "packaging smoke FAIL" in completed.stderr


# --------------------------------------------------------------------------- #
# Red control 2: ambiguous wheel set
# --------------------------------------------------------------------------- #


def test_red_control_ambiguous_project_wheels_fail_instead_of_first_file_selection(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    wheel, _ = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())
    # A second, different artifact for the same project distribution.
    decoy = wheel_dir / f"{wheel.name.split('-')[0]}-9.99.9-py3-none-any.whl"
    decoy.write_bytes(wheel.read_bytes())

    completed, _ = _smoke(wheel_dir, work_dir)
    assert completed.returncode == EXIT_FAIL
    assert "project_wheel_ambiguous" in completed.stderr
    assert wheel.name in completed.stderr
    assert decoy.name in completed.stderr
    assert not (work_dir / "venv").exists(), (
        "no environment may be created for an ambiguous wheel set"
    )


# --------------------------------------------------------------------------- #
# Red control 3: tampered wheel after digest/source binding
# --------------------------------------------------------------------------- #


def test_red_control_expected_digest_mismatch_fails_closed(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    wheel, wheel_sha256 = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())

    completed, _ = _smoke(wheel_dir, work_dir, extra=("--expect-wheel-sha256", "0" * 64))
    assert completed.returncode == EXIT_FAIL
    assert "wheel_digest_mismatch" in completed.stderr
    assert wheel_sha256 in completed.stderr


def test_red_control_wheel_tampered_after_binding_is_detected_by_the_evidence_consumer(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    """Bind evidence to a real wheel, then mutate the artifact behind the evidence."""
    wheel, wheel_sha256 = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    artifact = wheel_dir / wheel.name
    artifact.write_bytes(wheel.read_bytes())

    completed, document = _smoke(wheel_dir, work_dir, extra=("--expect-wheel-sha256", wheel_sha256))
    assert completed.returncode == EXIT_PASS, completed.stdout + completed.stderr
    assert document["wheel_sha256"] == wheel_sha256

    checked = _run_script(
        "check",
        "--repo",
        str(ROOT),
        "--evidence",
        str(work_dir / "evidence" / "PACKAGING_SMOKE.json"),
        "--wheel-dir",
        str(wheel_dir),
    )
    assert checked.returncode == EXIT_PASS, checked.stdout + checked.stderr

    # Tamper with the artifact *after* the evidence was bound to its digest.
    payload = artifact.read_bytes()
    artifact.write_bytes(payload[:-1] + bytes([payload[-1] ^ 0xFF]))

    reverified = _run_script(
        "check",
        "--repo",
        str(ROOT),
        "--evidence",
        str(work_dir / "evidence" / "PACKAGING_SMOKE.json"),
        "--wheel-dir",
        str(wheel_dir),
    )
    assert reverified.returncode == EXIT_FAIL
    assert "artifact_reverification_digest_mismatch" in reverified.stderr


def test_red_control_source_identity_binding_mismatch_fails_closed(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    wheel, _ = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())

    completed, _ = _smoke(wheel_dir, work_dir, extra=("--expect-source-sha", "0" * 40))
    assert completed.returncode == EXIT_FAIL
    assert "source_sha_mismatch" in completed.stderr

    completed, _ = _smoke(
        wheel_dir,
        work_dir.parent / "other",
        extra=("--expect-source-tree", "1" * 40),
    )
    assert completed.returncode == EXIT_FAIL
    assert "source_tree_mismatch" in completed.stderr


# --------------------------------------------------------------------------- #
# Red control 4: package/version mismatch (full consumer path)
# --------------------------------------------------------------------------- #


def test_red_control_package_version_mismatch_fails_after_isolated_install(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    wheel, _ = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())

    completed, document = _smoke(wheel_dir, work_dir, extra=("--expect-version", "9.99.99"))
    assert completed.returncode == EXIT_FAIL
    assert "package_version_mismatch" in completed.stderr
    # The mismatch was detected only after a real isolated install of the wheel.
    assert document["install"]["direct_url_sha256"] == packaging.sha256_file(wheel_dir / wheel.name)
    assert document["installed_import"] == {
        "status": "FAIL",
        "module": packaging.DEFAULT_IMPORT_MODULE,
    }
    assert document["overall_classification"] == "FAIL"


# --------------------------------------------------------------------------- #
# Red control 5: missing expected CLI entrypoint (full consumer path)
# --------------------------------------------------------------------------- #


def test_red_control_missing_expected_cli_entrypoint_fails_after_install(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    wheel, _ = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())
    ghost = tmp_path / "pyproject-with-ghost-entrypoint.toml"
    _mutated_pyproject(ghost, extra_script="commander-lab-ghost-entrypoint")

    completed, document = _smoke(wheel_dir, work_dir, extra=("--pyproject", str(ghost)))
    assert completed.returncode == EXIT_FAIL
    assert "cli_entrypoint_smoke_failed" in completed.stderr
    assert "commander-lab-ghost-entrypoint" in completed.stderr
    # The genuinely installed entrypoints are still recorded, and the ghost is not.
    results = document["cli_entrypoint_results"]
    assert results["commander-lab-ghost-entrypoint"]["status"] == "FAIL"
    assert results["commander-lab-ghost-entrypoint"]["reason"] == "cli_entrypoint_missing"
    for name in CONTRACT.scripts:
        assert results[name]["status"] == "PASS", (name, results[name])
    assert document["installed_import"]["status"] == "PASS"


# --------------------------------------------------------------------------- #
# Red control 6: source-tree import must not count as packaging PASS
# --------------------------------------------------------------------------- #


def test_red_control_source_tree_import_substitution_fails_closed(
    work_dir: Path, tmp_path: Path
) -> None:
    """A wheel that only proxies imports to the worktree must never PASS.

    The decoy installs cleanly, declares the current version, satisfies the
    dependency install, and ``import commander_lab`` genuinely succeeds — so a
    naive import smoke would call this a PASS. The provenance contract must not.
    """
    wheel_dir = tmp_path / "dist"
    _write_source_proxy_wheel(
        wheel_dir,
        name=CONTRACT.name,
        version=CONTRACT.version,
        proxied_source_root=ROOT / "src",
    )

    completed, document = _smoke(wheel_dir, work_dir)
    assert completed.returncode == EXIT_FAIL, completed.stdout + completed.stderr
    # The stronger source binding rejects this foreign, incomplete artifact
    # before installation. The following source-locked control exercises the
    # isolated import guard itself through the full execution path.
    assert "wheel_dependencies_differ_from_source" in completed.stderr
    assert document["overall_classification"] == "FAIL"
    assert not (work_dir / "venv").exists()


def test_source_locked_candidate_import_cannot_add_its_worktree(tmp_path):
    child = tmp_path / "candidate"
    subprocess.run(
        ["git", "clone", "--local", "--no-hardlinks", str(ROOT), str(child)],
        check=True,
        capture_output=True,
    )
    init = child / "src/commander_lab/__init__.py"
    init.write_text(
        init.read_text() + f"\nimport sys\nsys.path.insert(0, {str(child / 'src')!r})\n"
    )
    subprocess.run(["git", "-C", str(child), "add", "src/commander_lab/__init__.py"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(child),
            "-c",
            "user.name=Packaging Control",
            "-c",
            "user.email=control@example.invalid",
            "commit",
            "-m",
            "Control: source-path injection",
        ],
        check=True,
        capture_output=True,
    )
    wheels = tmp_path / "wheels"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheels),
            ".",
        ],
        cwd=child,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    output = tmp_path / "evidence.json"
    result = _run_script(
        "smoke",
        "--repo",
        str(child),
        "--wheel-dir",
        str(wheels),
        "--venv-dir",
        str(tmp_path / "venv"),
        "--scratch-dir",
        str(tmp_path / "scratch"),
        "--output",
        str(output),
    )
    assert result.returncode == EXIT_FAIL, result.stdout + result.stderr
    document = json.loads(output.read_text())
    assert document["wheel_source_binding"]["status"] == "PASS", document
    assert any(reason.startswith(_PROVENANCE_FAILURE_CODES) for reason in document["reasons"]), (
        document
    )


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


def test_preexisting_isolated_environment_is_rejected(work_dir: Path, tmp_path: Path) -> None:
    venv_dir = work_dir / "venv"
    venv_dir.mkdir(parents=True)
    with pytest.raises(packaging._Classification) as failure:
        packaging.create_isolated_environment(venv_dir, scratch_dir=work_dir)
    assert failure.value.classification == "FAIL"
    assert failure.value.code.startswith("isolated_environment_preexisting")


# --------------------------------------------------------------------------- #
# Red control 7/8: missing, malformed, UNKNOWN or unbound evidence
# --------------------------------------------------------------------------- #


def test_red_control_missing_evidence_file_never_passes(tmp_path: Path) -> None:
    checked = _run_script("check", "--repo", str(ROOT), "--evidence", str(tmp_path / "absent.json"))
    assert checked.returncode == EXIT_FAIL
    assert "packaging evidence missing" in checked.stderr


def test_red_control_malformed_evidence_never_passes(tmp_path: Path) -> None:
    truncated = tmp_path / "truncated.json"
    truncated.write_text(
        '{"schema_version": "packaging-smoke-1.0.0", "source_sha":', encoding="utf-8"
    )
    checked = _run_script("check", "--repo", str(ROOT), "--evidence", str(truncated))
    assert checked.returncode == EXIT_FAIL
    assert "unreadable" in checked.stderr

    not_object = tmp_path / "list.json"
    not_object.write_text("[]", encoding="utf-8")
    checked = _run_script("check", "--repo", str(ROOT), "--evidence", str(not_object))
    assert checked.returncode == EXIT_FAIL
    assert "not a JSON object" in checked.stderr


def test_red_control_incomplete_evidence_document_never_passes(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    wheel, wheel_sha256 = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())
    _, document = _smoke(wheel_dir, work_dir, extra=("--expect-wheel-sha256", wheel_sha256))
    assert document["overall_classification"] == "PASS"
    source_path = work_dir / "evidence" / "PACKAGING_SMOKE.json"

    for dropped in ("wheel_sha256", "cli_entrypoint_results", "installed_import", "reasons"):
        broken = tmp_path / f"missing-{dropped}.json"
        mutated = dict(document)
        del mutated[dropped]
        broken.write_text(json.dumps(mutated), encoding="utf-8")
        checked = _run_script("check", "--repo", str(ROOT), "--evidence", str(broken))
        assert checked.returncode == EXIT_FAIL, dropped
        assert dropped in checked.stderr, dropped

    assert source_path.is_file()


def test_red_control_unknown_or_failed_classification_is_never_promoted_to_pass(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    wheel, wheel_sha256 = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())
    _, document = _smoke(wheel_dir, work_dir, extra=("--expect-wheel-sha256", wheel_sha256))

    for classification in ("UNKNOWN", "FAIL", "PARTIAL", "NOT_RUN"):
        broken = tmp_path / f"classification-{classification}.json"
        mutated = dict(document)
        mutated["overall_classification"] = classification
        broken.write_text(json.dumps(mutated), encoding="utf-8")
        checked = _run_script("check", "--repo", str(ROOT), "--evidence", str(broken))
        assert checked.returncode == EXIT_FAIL, classification
        assert "recorded_classification_not_pass" in checked.stderr, classification


def test_red_control_evidence_bound_to_a_different_candidate_is_rejected(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    wheel, wheel_sha256 = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())
    _, document = _smoke(wheel_dir, work_dir, extra=("--expect-wheel-sha256", wheel_sha256))

    checked = _run_script(
        "check",
        "--repo",
        str(ROOT),
        "--evidence",
        str(work_dir / "evidence" / "PACKAGING_SMOKE.json"),
        "--expect-source-sha",
        "0" * 40,
    )
    assert checked.returncode == EXIT_FAIL
    assert "evidence_source_sha_not_the_expected_candidate" in checked.stderr

    stale_version = dict(document)
    stale_version["package_version"] = "0.0.1"
    stale_version["declared_version"] = "0.0.1"
    stale_path = tmp_path / "stale-version.json"
    stale_path.write_text(json.dumps(stale_version), encoding="utf-8")
    checked = _run_script("check", "--repo", str(ROOT), "--evidence", str(stale_path))
    assert checked.returncode == EXIT_FAIL
    assert "package_version_not_the_current_declared_version" in checked.stderr


def test_red_control_evidence_claiming_a_source_tree_import_is_rejected(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    wheel, wheel_sha256 = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())
    _, document = _smoke(wheel_dir, work_dir, extra=("--expect-wheel-sha256", wheel_sha256))

    forged = dict(document)
    forged_import = dict(document["installed_import"])
    forged_import["resolved_in_isolated_environment"] = False
    forged["installed_import"] = forged_import
    forged_path = tmp_path / "forged-import.json"
    forged_path.write_text(json.dumps(forged), encoding="utf-8")
    checked = _run_script("check", "--repo", str(ROOT), "--evidence", str(forged_path))
    assert checked.returncode == EXIT_FAIL
    assert "installed_import_not_proven_isolated" in checked.stderr


def test_red_control_non_wheel_install_source_claim_is_rejected(
    built_wheel: tuple[Path, str], work_dir: Path, tmp_path: Path
) -> None:
    wheel, wheel_sha256 = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())
    _, document = _smoke(wheel_dir, work_dir, extra=("--expect-wheel-sha256", wheel_sha256))

    forged = dict(document)
    forged["install_source"] = "source_tree"
    forged_path = tmp_path / "forged-source.json"
    forged_path.write_text(json.dumps(forged), encoding="utf-8")
    checked = _run_script("check", "--repo", str(ROOT), "--evidence", str(forged_path))
    assert checked.returncode == EXIT_FAIL
    assert "install_source_not_wheel" in checked.stderr


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
    assert CONTRACT.scripts, (
        "the project must declare console scripts for the smoke to prove anything"
    )
    for script_name, target in CONTRACT.scripts.items():
        module_name, separator, attribute = target.partition(":")
        assert separator == ":", (script_name, target)
        assert module_name and attribute, (script_name, target)
        module_path = ROOT / "src" / (module_name.replace(".", "/") + ".py")
        assert module_path.is_file(), (script_name, target)


def test_scratch_dir_inside_the_repository_is_rejected(built_wheel, tmp_path) -> None:
    wheel, _ = built_wheel
    output = tmp_path / "failure.json"
    result = _run_script(
        "smoke",
        "--repo",
        str(ROOT),
        "--wheel-dir",
        str(wheel.parent),
        "--venv-dir",
        str(ROOT / "b9-should-not-exist"),
        "--scratch-dir",
        str(ROOT / "artifacts"),
        "--output",
        str(output),
    )
    assert result.returncode == EXIT_FAIL, result.stdout + result.stderr
    document = json.loads(output.read_text())
    assert document["overall_classification"] == "FAIL"
    assert document["reasons"] == ["scratch_dir_inside_repository"]
    assert not (ROOT / "b9-should-not-exist").exists()


# --------------------------------------------------------------------------- #
# CI trust boundary: the required quality context is extended, never weakened
# --------------------------------------------------------------------------- #


def _ci() -> dict:
    import yaml

    return yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))


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


def test_early_failure_overwrites_stale_pass(work_dir, tmp_path):
    output = work_dir / "evidence" / "PACKAGING_SMOKE.json"
    output.parent.mkdir()
    output.write_text(json.dumps({"overall_classification": "PASS"}))
    missing = tmp_path / "missing-wheels"
    missing.mkdir()
    completed, document = _smoke(missing, work_dir)
    assert completed.returncode == EXIT_FAIL
    assert document.get("overall_classification") != "PASS"
    assert document.get("reasons"), document


_FIRST_SCRIPT = next(iter(CONTRACT.scripts))


def test_every_forged_binding_is_rejected_independently(built_wheel, work_dir, tmp_path):
    import copy

    wheel, _ = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())
    completed, valid = _smoke(wheel_dir, work_dir)
    assert completed.returncode == EXIT_PASS, completed.stderr
    controls = [
        (("source_sha",), "0" * 40),
        (("installed_import", "module"), "commander_lab.__b9_missing__"),
        (("installed_import", "module"), None),
        (("installed_import", "module"), 123),
        (("installed_import", "module"), "invalid-name"),
        (("source_tree",), "0" * 40),
        (("install", "direct_url_sha256"), "0" * 64),
        (("install", "editable"), True),
        (("install", "install_source"), "directory"),
        (("install", "index_access"), "enabled"),
        (("environment", "include_system_site_packages"), True),
        (("environment", "created_by_this_run"), False),
        (("reasons",), ["unresolved_failure"]),
        (("package_contract",), {}),
        (("cli_entrypoints",), []),
        (("expected_bindings",), {"source_sha": "0" * 40}),
        # Recorded runtime observations are re-observed, not just re-run.
        (("installed_import", "module"), "yaml"),
        (("python_version",), "2.7.18"),
        (("installed_import", "python_version"), "2.7.18"),
        (("installed_import", "dist_version"), "9.9.9"),
        (
            ("installed_import", "module_file_relative_to_purelib"),
            "../src/commander_lab/__init__.py",
        ),
        (("installed_import", "runtime_requirements_satisfied"), []),
        (("installed_import", "sys_path_entry_count"), 999),
        (("cli_entrypoint_results", _FIRST_SCRIPT, "stdout_sha256"), "0" * 64),
        (("cli_entrypoint_results", _FIRST_SCRIPT, "stdout_bytes"), 1),
        (("cli_entrypoint_results", _FIRST_SCRIPT, "target"), "forged:app"),
    ]
    for keys, value in controls:
        forged = copy.deepcopy(valid)
        target = forged
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value
        evidence = tmp_path / "forged.json"
        evidence.write_text(json.dumps(forged))
        checked = _run_script(
            "check", "--repo", str(ROOT), "--evidence", str(evidence), "--wheel-dir", str(wheel_dir)
        )
        assert checked.returncode == EXIT_FAIL, (keys, checked.stdout, checked.stderr)
    for key in ("package_contract", "environment", "install", "cli_entrypoints"):
        forged = copy.deepcopy(valid)
        del forged[key]
        evidence.write_text(json.dumps(forged))
        checked = _run_script(
            "check", "--repo", str(ROOT), "--evidence", str(evidence), "--wheel-dir", str(wheel_dir)
        )
        assert checked.returncode == EXIT_FAIL, key


def test_wheel_from_foreign_source_fails_binding(built_wheel, work_dir, tmp_path):
    wheel, _ = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    foreign = wheel_dir / wheel.name
    with zipfile.ZipFile(wheel) as original, zipfile.ZipFile(foreign, "w") as out:
        for info in original.infolist():
            data = original.read(info.filename)
            if info.filename == "commander_lab/__init__.py":
                data += b"\n# foreign source revision\n"
            out.writestr(info, data)
    completed, document = _smoke(wheel_dir, work_dir)
    assert completed.returncode == EXIT_FAIL, completed.stdout
    assert any(
        reason.startswith("wheel_file_differs_from_source:")
        for reason in document.get("reasons", [])
    ), document


def test_undeclared_dependency_is_not_supplied_by_tooling(tmp_path):
    child = tmp_path / "candidate"
    result = subprocess.run(
        ["git", "clone", "--local", "--no-hardlinks", str(ROOT), str(child)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    init = child / "src/commander_lab/__init__.py"
    init.write_text(
        init.read_text() + "\nimport jsonschema  # deliberately undeclared runtime dependency\n"
    )
    subprocess.run(["git", "-C", str(child), "add", "src/commander_lab/__init__.py"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(child),
            "-c",
            "user.name=Packaging Control",
            "-c",
            "user.email=control@example.invalid",
            "commit",
            "-m",
            "Control: undeclared runtime import",
        ],
        check=True,
        capture_output=True,
    )
    wheels = tmp_path / "wheels"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheels),
            ".",
        ],
        cwd=child,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    scratch = tmp_path / "scratch"
    output = tmp_path / "failure.json"
    result = _run_script(
        "smoke",
        "--repo",
        str(child),
        "--wheel-dir",
        str(wheels),
        "--venv-dir",
        str(tmp_path / "venv"),
        "--scratch-dir",
        str(scratch),
        "--output",
        str(output),
    )
    assert result.returncode == EXIT_FAIL, result.stdout + result.stderr
    document = json.loads(output.read_text())
    assert document["reasons"] == ["installed_import_failed:ModuleNotFoundError"], document
    assert document["wheel_source_binding"]["status"] == "PASS", document
    assert all(
        not entry.startswith("jsonschema==")
        for entry in document["dependency_closure"]["requirements"]
    )

    # Forge a structurally consistent PASS for the same source-bound artifact
    # whose undeclared import actually failed above. The consumer must execute
    # its own probes rather than accept these unsigned recorded observations.
    document["overall_classification"] = "PASS"
    document["reasons"] = ["all_packaging_smoke_invariants_satisfied"]
    document["installed_import"] = {
        "status": "PASS",
        "module": "commander_lab",
        "resolved_in_isolated_environment": True,
        "module_file_relative_to_purelib": "commander_lab/__init__.py",
    }
    document["cli_entrypoints"] = [
        {"name": name, "status": "PASS", "returncode": 0} for name in CONTRACT.scripts
    ]
    document["cli_entrypoint_results"] = {row["name"]: row for row in document["cli_entrypoints"]}
    output.write_text(json.dumps(document))
    checked = _run_script(
        "check", "--repo", str(child), "--evidence", str(output), "--wheel-dir", str(wheels)
    )
    assert checked.returncode == EXIT_FAIL, checked.stdout + checked.stderr
    assert "runtime_reverification_failed" in checked.stderr


def test_import_proof_must_come_from_the_project_wheel(built_wheel, work_dir, tmp_path):
    """A dependency's module resolves in the isolated purelib but proves nothing."""
    wheel, _ = built_wheel
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    (wheel_dir / wheel.name).write_bytes(wheel.read_bytes())
    completed, document = _smoke(wheel_dir, work_dir, extra=("--import-module", "yaml"))
    assert completed.returncode == EXIT_FAIL, completed.stdout + completed.stderr
    assert document["overall_classification"] == "FAIL"
    assert any(
        reason.startswith("installed_import_module_not_from_project_wheel")
        for reason in document["reasons"]
    )
