"""The current-boundary launch command carries the serial GC flag and keeps its shape.

Serial GC is a JVM flag (measured -10 to -16 % CPU per game, identical semantic transcripts);
the launch contract around it, the classpath manifest and the lane argument, stays as it was.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import bridge_launcher as B


@pytest.mark.parametrize("lane", [None, "full-game", "midgame"])
def test_the_launch_command_uses_serial_gc_and_keeps_the_launch_contract(
    tmp_path: Path, lane: str | None
) -> None:
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "cp-wsr22.txt").write_text("a.jar:b.jar\n", encoding="utf-8")
    plan = B.build_launch_plan("xmage", lane=lane, xmage_workspace=tmp_path)
    argv = plan.argv
    assert argv[0] == "java"
    assert "-XX:+UseSerialGC" in argv
    assert argv.index("-XX:+UseSerialGC") < argv.index("-cp")
    assert argv[argv.index("-cp") + 1].endswith(":a.jar:b.jar")
    assert argv[argv.index("-cp") + 2] == "org.commanderlab.xmage.Main"
    assert argv[argv.index("-cp") + 3 :] == (plan.lane,)
    assert plan.lane == ("midgame" if lane == "midgame" else "full-game")
