"""Unit tests for ``commander_lab.studio.doctor`` and CLI ``doctor`` subcommand."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary.bridge_launcher import (
    canonical_xmage_engine_pin,
)
from commander_lab.studio import __main__ as studio_cli
from commander_lab.studio import doctor, launch


def _write_fake_jar_and_pin(data_dir: Path, pin: str) -> Path:
    engine_dir = data_dir / "engine"
    engine_dir.mkdir(parents=True, exist_ok=True)
    jar = engine_dir / "xmage-engine-bridge.jar"
    jar.write_bytes(b"fake-bridge-jar-payload")
    (engine_dir / "ENGINE_PIN.txt").write_text(f"{pin}\n", encoding="utf-8")
    return jar


def test_doctor_passes_when_all_prerequisites_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pin = canonical_xmage_engine_pin()
    jar = _write_fake_jar_and_pin(tmp_path, pin)
    jar.with_suffix(".jsa").write_bytes(b"fake-jsa")
    sqlite3.connect(tmp_path / "studio.sqlite3").close()

    monkeypatch.delenv(launch.ENGINE_COMMAND_ENV, raising=False)
    monkeypatch.setattr(launch, "_java_executable", lambda: "/usr/bin/java")
    monkeypatch.setattr(launch, "_java_major", lambda _java: 17)
    monkeypatch.setattr("commander_lab.studio.builder.sim_readiness_available", lambda: True)

    code = studio_cli.main(["--data", str(tmp_path), "doctor", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["status"] == "PASS"
    assert payload["summary"] == {"pass": 8, "warn": 0, "fail": 0}


def test_doctor_fails_when_bridge_jar_or_java_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(launch.ENGINE_COMMAND_ENV, raising=False)
    monkeypatch.setattr(launch, "_java_executable", lambda: None)
    monkeypatch.setattr("commander_lab.studio.builder.sim_readiness_available", lambda: True)

    code = studio_cli.main(["--data", str(tmp_path), "doctor"])
    assert code == 1
    out = capsys.readouterr().out
    assert "[FAIL] java:" in out
    assert "[FAIL] engine_bridge:" in out


def test_doctor_fails_on_java_too_old_or_pin_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_fake_jar_and_pin(tmp_path, "0" * 40)
    monkeypatch.delenv(launch.ENGINE_COMMAND_ENV, raising=False)
    monkeypatch.setattr(launch, "_java_executable", lambda: "/usr/bin/java")
    monkeypatch.setattr(launch, "_java_major", lambda _java: 11)
    monkeypatch.setattr("commander_lab.studio.builder.sim_readiness_available", lambda: True)

    report = doctor.run_doctor(tmp_path, check_dependencies=False)
    assert report["ok"] is False
    checks = report["checks"]
    assert isinstance(checks, list)
    by_name = {c["name"]: c for c in checks}
    assert by_name["java"]["status"] == "FAIL"
    assert by_name["engine_pin"]["status"] == "FAIL"
    assert by_name["appcds_archive"]["status"] == "WARN"
    assert "build-appcds" in str(by_name["appcds_archive"]["remediation"])


def test_doctor_reports_missing_dependencies_and_env_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom_script = tmp_path / "run_bridge.sh"
    custom_script.write_text("#!/bin/sh\n", encoding="utf-8")
    custom_script.chmod(0o755)
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, str(custom_script))
    monkeypatch.setattr("commander_lab.studio.builder.sim_readiness_available", lambda: True)

    # Normal run with valid non-java executable passes engine_bridge + java checks
    report = doctor.run_doctor(tmp_path, check_dependencies=False)
    checks = report["checks"]
    assert isinstance(checks, list)
    by_name = {c["name"]: c for c in checks}
    assert by_name["java"]["status"] == "PASS"
    assert by_name["engine_bridge"]["status"] == "PASS"
    assert report["ok"] is True

    # Dependency failure check
    def _fail_fastapi(name: str) -> object:
        if name == "fastapi":
            raise ImportError("no fastapi")
        return object()

    dep_check = doctor._check_dependencies(_fail_fastapi)
    assert dep_check["status"] == "FAIL"
    assert dep_check["missing"] == ["fastapi"]


def test_doctor_warns_without_crashing_when_data_dir_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("COMMANDER_LAB_STUDIO_DATA", raising=False)
    monkeypatch.delenv("COMMANDER_LAB_OWNER_DATA", raising=False)
    monkeypatch.delenv(launch.ENGINE_COMMAND_ENV, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(launch, "_java_executable", lambda: "/usr/bin/java")
    monkeypatch.setattr(launch, "_java_major", lambda _java: 17)
    monkeypatch.setattr("commander_lab.studio.builder.sim_readiness_available", lambda: True)

    report = doctor.run_doctor(None, check_dependencies=False)
    checks = report["checks"]
    assert isinstance(checks, list)
    by_name = {c["name"]: c for c in checks}
    assert by_name["studio_data"]["status"] == "WARN"
    assert by_name["engine_bridge"]["status"] == "FAIL"


def test_doctor_fails_on_incomplete_jar_env_and_invalid_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = launch._repository_root()
    monkeypatch.setenv("COMMANDER_LAB_STUDIO_DATA", str(repo_root / "tmp_studio_data_test"))
    monkeypatch.delenv("COMMANDER_LAB_OWNER_DATA", raising=False)
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, "java -jar")
    monkeypatch.setattr(launch, "_java_executable", lambda: "/usr/bin/java")
    monkeypatch.setattr(launch, "_java_major", lambda _java: 17)
    monkeypatch.setattr("commander_lab.studio.builder.sim_readiness_available", lambda: True)

    report = doctor.run_doctor(None, check_dependencies=False)
    checks = report["checks"]
    assert isinstance(checks, list)
    by_name = {c["name"]: c for c in checks}
    assert by_name["engine_bridge"]["status"] == "FAIL"
    assert by_name["studio_data"]["status"] == "FAIL"
    assert report["ok"] is False


def test_doctor_appcds_warns_on_missing_mismatched_or_older_archive(tmp_path: Path) -> None:
    import hashlib
    import os

    jar = _write_fake_jar_and_pin(tmp_path, canonical_xmage_engine_pin())
    jar_sha = hashlib.sha256(jar.read_bytes()).hexdigest()

    # 1. Missing archive -> WARN (recommended, not required)
    missing = doctor._check_appcds(jar)
    assert missing["status"] == "WARN"
    assert missing["required"] is False
    assert "Empfohlen" in str(missing["detail"])
    assert "build-appcds" in str(missing["remediation"])

    # 2. Matching archive + matching sidecar -> PASS
    archive = launch.appcds_archive_path(jar)
    sidecar = launch.appcds_jar_sha256_path(archive)
    archive.write_bytes(b"fake-jsa-bytes")
    sidecar.write_text(f"{jar_sha}\n", encoding="utf-8")
    matching = doctor._check_appcds(jar)
    assert matching["status"] == "PASS"
    assert matching["archive_matches_jar"] is True
    assert matching["remediation"] is None

    # 3. JAR replaced (sidecar digest mismatch even if archive mtime is newer) -> WARN
    jar.write_bytes(b"replaced-bridge-jar-payload")
    archive_mtime = jar.stat().st_mtime + 10.0
    os.utime(archive, (archive_mtime, archive_mtime))
    mismatched = doctor._check_appcds(jar)
    assert mismatched["status"] == "WARN"
    assert mismatched["archive_matches_jar"] is False
    assert "passt nicht" in str(mismatched["detail"])
    assert "build-appcds" in str(mismatched["remediation"])

    # 4. Legacy archive without sidecar that is older than the JAR -> WARN
    sidecar.unlink()
    older_mtime = jar.stat().st_mtime - 60.0
    os.utime(archive, (older_mtime, older_mtime))
    stale = doctor._check_appcds(jar)
    assert stale["status"] == "WARN"
    assert stale["archive_matches_jar"] is False
    assert "älter" in str(stale["detail"])
    assert "build-appcds" in str(stale["remediation"])
