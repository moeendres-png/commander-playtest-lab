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
