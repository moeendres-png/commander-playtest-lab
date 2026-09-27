"""WS223 environment-identity regression battery (no network, no Docker).

Locks the S15 surface so it cannot silently regress:

* ``PYTHONHASHSEED: "0"`` in every Python-executing workflow (exact
  exemption list);
* explicit lock-bound pip cache keys (plus the documented Windows key);
* locked installs in every ubuntu lane (documented Windows exception);
* digest-pinned container bases matching the recorded contract digest;
* JDK coherence (Temurin 17 in JVM lanes, ``release=17`` floor in the pom);
* dependency-lock offline verification green;
* environment-receipt schema + identity-digest self-consistency.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import yaml

WORKFLOWS_DIR = ".github/workflows"
HASHSEED_EXEMPT = {"opencode.yml"}
RANGE_INSTALL_EXEMPT = {"windows-runtime.yml", "opencode.yml"}
CONTAINER_DIGEST = "sha256:1f79c73404fb0cccf9a3459eda22892f368d994b1028d6fb1ae871c1f49749a6"

LOCKED_INSTALL_MARKERS = (
    "pip install --require-hashes -r requirements/lock.txt",
    "pip install --no-deps --no-build-isolation -e .",
)


def _workflow_files(repo_root: Path) -> list[Path]:
    return sorted((repo_root / WORKFLOWS_DIR).glob("*.yml"))


def test_hashseed_pinned_everywhere_except_documented_exemption(repo_root: Path) -> None:
    for path in _workflow_files(repo_root):
        text = path.read_text(encoding="utf-8")
        runs_python = "setup-python" in text
        if path.name in HASHSEED_EXEMPT:
            assert not runs_python, f"{path.name} is exempt but runs Python"
            continue
        assert runs_python, f"{path.name} has no setup-python; classify it"
        assert 'PYTHONHASHSEED: "0"' in text, f"{path.name} lacks the hashseed pin"


def test_hashseed_value_is_zero_not_arbitrary(repo_root: Path) -> None:
    for path in _workflow_files(repo_root):
        for line in path.read_text(encoding="utf-8").splitlines():
            if "PYTHONHASHSEED" in line and ":" in line:
                assert '"0"' in line, f"{path.name} uses a non-canonical hashseed: {line.strip()}"


def test_pip_cache_keys_are_explicit_and_lock_bound(repo_root: Path) -> None:
    for path in _workflow_files(repo_root):
        if path.name in HASHSEED_EXEMPT:
            continue
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in (workflow.get("jobs") or {}).values():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                uses = str(step.get("uses") or "")
                with_block = step.get("with") or {}
                if "setup-python" in uses and with_block.get("cache") == "pip":
                    key = with_block.get("cache-dependency-path")
                    assert key, f"{path.name} pip cache has no explicit key"
                    if path.name in RANGE_INSTALL_EXEMPT:
                        assert "pyproject.toml" in str(key), path.name
                    else:
                        assert "requirements/lock.txt" in str(key), (
                            f"{path.name} pip cache is not lock-bound"
                        )


def test_locked_install_in_every_ubuntu_lane(repo_root: Path) -> None:
    for path in _workflow_files(repo_root):
        if path.name in RANGE_INSTALL_EXEMPT:
            continue
        text = path.read_text(encoding="utf-8")
        if "setup-python" not in text or "runs-on: windows" in text:
            continue
        for marker in LOCKED_INSTALL_MARKERS:
            assert marker in text, f"{path.name} lacks locked-install marker: {marker}"
        range_installs = [
            line.strip()
            for line in text.splitlines()
            if re.search(r"pip install (-e |.*\[dev|.*\[api|.*\[openai|build$)", line)
            and "--require-hashes" not in line
            and "wheel-verify" not in line
            and "release/" not in line
        ]
        assert not range_installs, f"{path.name} keeps range installs: {range_installs}"


def test_windows_exception_is_documented(repo_root: Path) -> None:
    text = (repo_root / WORKFLOWS_DIR / "windows-runtime.yml").read_text(encoding="utf-8")
    assert "WS223 scope exception" in text
    assert "pyproject.toml" in text


def test_container_bases_are_digest_pinned(repo_root: Path) -> None:
    for name in ("docker/xmage/Dockerfile", "docker/forge/Dockerfile"):
        text = (repo_root / name).read_text(encoding="utf-8")
        assert f"FROM eclipse-temurin:21-jdk@{CONTAINER_DIGEST}" in text, name
        assert "FROM eclipse-temurin:21-jdk\n" not in text, f"{name} still floats"
        assert 'org.commander-lab.base-image-digest="' + CONTAINER_DIGEST + '"' in text, name
        assert 'org.commander-lab.base-image-tag="eclipse-temurin:21-jdk"' in text, name


def test_no_hardcoded_engine_commit_outside_base_image_digest(repo_root: Path) -> None:
    """WS-A1D/WS223 domain split: base-image digests are allowed in Dockerfiles;
    hardcoded 40-hex engine commits anywhere else still fail."""
    for name in ("docker/xmage/Dockerfile", "docker/forge/Dockerfile"):
        for line in (repo_root / name).read_text(encoding="utf-8").splitlines():
            stripped = re.sub(r"sha256:[0-9a-f]{64}", "", line)
            assert not re.search(r"[0-9a-f]{40}", stripped), (name, line.strip())


def test_container_digest_matches_recorded_contract(repo_root: Path) -> None:
    contract = (
        repo_root / "qualification/ws223-ci-cardinality-environment-lock/CONTAINER_IDENTITY.md"
    ).read_text(encoding="utf-8")
    assert CONTAINER_DIGEST in contract


def test_jdk_identity_is_coherent(repo_root: Path) -> None:
    pom = (repo_root / "engine-bridge/pom.xml").read_text(encoding="utf-8")
    assert "<maven.compiler.release>17</maven.compiler.release>" in pom
    for name in (
        "xmage-full-game-conformance.yml",
        "external-engine-integration.yml",
        "h4-docker-materialization.yml",
    ):
        text = (repo_root / WORKFLOWS_DIR / name).read_text(encoding="utf-8")
        assert "distribution: temurin" in text, name
        assert 'java-version: "17"' in text, name


def test_dependency_lock_verifies_offline(repo_root: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "ws223_verify_lock", repo_root / "scripts/verify_dependency_lock.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = (repo_root / "requirements/lock.txt").read_text(encoding="utf-8")
    compiler_entries, appendix_entries = module._parse_lock(text)
    assert len(compiler_entries) >= 100
    assert len(appendix_entries) == 2
    assert all(entry["hashes"] for entry in compiler_entries + appendix_entries)
    recorded = (
        (repo_root / "qualification/ws223-ci-cardinality-environment-lock/DEPENDENCY_LOCK_DIGEST")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert hashlib.sha256(text.encode()).hexdigest() == recorded


def test_environment_receipt_schema_and_identity(tmp_path: Path, repo_root: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "ws223_receipt", repo_root / "scripts/write_environment_receipt.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "receipt.json"
    assert module.main(["--lane", "unit-test", "--output", str(output)]) == 0
    receipt: dict[str, Any] = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "ws223-environment-receipt-1.0.0"
    for key in (
        "python_implementation",
        "python_version",
        "dependency_lock_digest",
        "resolved_dependency_set_digest",
        "java",
        "pythonhashseed",
        "tool_versions",
        "engine_pins",
        "identity_sha256",
    ):
        assert key in receipt, f"receipt missing {key}"
    canonical = {key: value for key, value in receipt.items() if key != "generated_at"}
    identity = canonical.pop("identity_sha256")
    recomputed = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert recomputed == identity
    assert "sk-" not in json.dumps(receipt)
