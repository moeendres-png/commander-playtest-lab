"""The launch plan of the XMage bridge carries the serial collector (E1, 2026-10-22)."""

from __future__ import annotations

from pathlib import Path

from commander_lab.qualification.current_boundary.bridge_launcher import build_launch_plan


def _workspace(tmp_path: Path) -> Path:
    target = tmp_path / "target"
    (target / "classes").mkdir(parents=True, exist_ok=True)
    (target / "cp-wsr22.txt").write_text("a.jar:b.jar\n", encoding="utf-8")
    return tmp_path


def test_every_xmage_lane_starts_the_serial_collector_before_the_classpath(tmp_path: Path) -> None:
    for lane in (None, "full-game", "midgame", "compat"):
        plan = build_launch_plan("xmage", lane=lane, xmage_workspace=_workspace(tmp_path))
        argv = list(plan.argv)
        assert argv[0] == "java"
        assert "-XX:+UseSerialGC" in argv, lane
        assert argv.index("-XX:+UseSerialGC") < argv.index("-cp"), lane
        assert "-Djava.awt.headless=true" in argv, lane
        assert argv[argv.index("-cp") + 2] == "org.commanderlab.xmage.Main", lane


def test_the_collector_is_the_only_jvm_flag_added(tmp_path: Path) -> None:
    plan = build_launch_plan("xmage", lane="full-game", xmage_workspace=_workspace(tmp_path))
    flags = [part for part in plan.argv[1 : plan.argv.index("-cp")] if part.startswith("-")]
    assert flags[0] == "-XX:+UseSerialGC"
    assert [flag for flag in flags if flag.startswith("-XX")] == ["-XX:+UseSerialGC"]
