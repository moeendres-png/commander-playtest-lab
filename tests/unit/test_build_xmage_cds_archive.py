from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _script() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts/build_xmage_cds_archive.py"
    spec = importlib.util.spec_from_file_location("build_xmage_cds_archive", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bridge_command_keeps_jvm_logging_off_stdout() -> None:
    script = _script()
    command = script.bridge_command(Path("/b/bridge.jar"), Path("/b/bridge.jsa"))
    assert command[0] == "java"
    assert command[-3:] == ("-jar", "/b/bridge.jar", "full-game")
    jvm_options = command[1:-3]
    # The JVM warns on stdout when the archive does not match the jar; stdout is
    # the bridge protocol, so every JVM log line must go to stderr.
    assert jvm_options[:2] == ("-Xlog:disable", "-Xlog:all=warning:stderr")
    assert "-XX:SharedArchiveFile=/b/bridge.jsa" in jvm_options
    assert "-XX:+UseSerialGC" in jvm_options


def test_missing_jar_is_refused_before_any_game(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    script = _script()
    assert script.main(["--jar", str(tmp_path / "absent.jar")]) == 2
    assert "bridge jar not found" in capsys.readouterr().err


def test_studio_build_appcds_cli_writes_archive_and_refuses_missing_jar(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    import json

    from commander_lab.studio import __main__ as studio_cli
    from commander_lab.studio import launch

    assert studio_cli.main(["build-appcds", "--jar", str(tmp_path / "absent.jar")]) == 2
    assert "Bridge-JAR nicht gefunden" in capsys.readouterr().err

    jar = tmp_path / "xmage-engine-bridge.jar"
    jar.write_bytes(b"fake-jar")
    seen_cmds: list[tuple[str, ...]] = []

    class _FakeRunner:
        def __init__(self, cmd: tuple[str, ...], shutdown_grace_seconds: float = 0.0) -> None:
            seen_cmds.append(tuple(cmd))
            self.cmd = cmd

        def run_smoke(self, **_kwargs: object) -> None:
            for part in self.cmd:
                if part.startswith("-XX:ArchiveClassesAtExit="):
                    archive_path = Path(part.split("=", 1)[1])
                    archive_path.write_bytes(b"fake-jsa-archive")

    monkeypatch.setattr(launch, "_java_executable", lambda: "/usr/bin/java")
    monkeypatch.setattr(launch, "_java_major", lambda _java: 17)
    monkeypatch.setattr(
        "commander_lab.engine.rules.full_game.XmageFullGameRunner",
        _FakeRunner,
    )

    code = studio_cli.main(["build-appcds", "--jar", str(jar), "--decisions", "12", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "built"
    assert payload["archive_path"] == str(jar.with_suffix(".jsa"))
    assert jar.with_suffix(".jsa").is_file()
    assert "-XX:+UseSerialGC" in seen_cmds[0]
    assert "-Xlog:all=warning:stderr" in seen_cmds[0]
    assert f"-XX:ArchiveClassesAtExit={jar.with_suffix('.jsa')}" in seen_cmds[0]


def test_provision_engine_bridge_with_appcds(tmp_path: Path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    import importlib.util
    import json

    prov_path = Path(__file__).resolve().parents[2] / "scripts/provision_engine_bridge.py"
    spec = importlib.util.spec_from_file_location("provision_engine_bridge", prov_path)
    assert spec is not None and spec.loader is not None
    prov = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prov)

    src_jar = tmp_path / "built.jar"
    src_jar.write_bytes(b"bridge-bytes")
    data_dir = tmp_path / "studio_data"

    monkeypatch.setattr(
        prov,
        "build_appcds_archive",
        lambda _dir, jar=None, decisions=40: {
            "status": "built",
            "jar_path": str(jar),
            "archive_path": str(Path(str(jar)).with_suffix(".jsa")),
        },
    )

    code = prov.main(
        ["--source", str(src_jar), "--data-dir", str(data_dir), "--appcds", "--decisions", "25"]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "provisioned"
    assert out["appcds"]["status"] == "built"
    assert Path(out["appcds"]["archive_path"]).name == "xmage-engine-bridge.jsa"


def test_build_appcds_writes_jar_sha256_sidecar_for_doctor(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    import hashlib

    from commander_lab.studio import doctor, launch

    jar = tmp_path / "xmage-engine-bridge.jar"
    jar.write_bytes(b"fake-bridge-jar-v1")

    class _FakeRunner:
        def __init__(self, cmd: tuple[str, ...], shutdown_grace_seconds: float = 0.0) -> None:
            self.cmd = cmd

        def run_smoke(self, **_kwargs: object) -> None:
            for part in self.cmd:
                if part.startswith("-XX:ArchiveClassesAtExit="):
                    Path(part.split("=", 1)[1]).write_bytes(b"fake-jsa-v1")

    monkeypatch.setattr(launch, "_java_executable", lambda: "/usr/bin/java")
    monkeypatch.setattr(launch, "_java_major", lambda _java: 17)
    monkeypatch.setattr(
        "commander_lab.engine.rules.full_game.XmageFullGameRunner",
        _FakeRunner,
    )

    payload = launch.build_appcds_archive(jar=jar, decisions=8)
    expected_sha = hashlib.sha256(b"fake-bridge-jar-v1").hexdigest()
    archive = launch.appcds_archive_path(jar)
    sidecar = launch.appcds_jar_sha256_path(archive)
    assert payload["jar_sha256"] == expected_sha
    assert sidecar.is_file()
    assert sidecar.read_text(encoding="utf-8").strip() == expected_sha
    assert doctor._check_appcds(jar)["status"] == "PASS"

    # Replacing JAR invalidates the archive for doctor
    jar.write_bytes(b"fake-bridge-jar-v2")
    after = doctor._check_appcds(jar)
    assert after["status"] == "WARN"
    assert after["archive_matches_jar"] is False
