"""Every game of scripts/pilot_decision_report.py gets a private card database slot (#878).

Several report processes started side by side with one worker each used to share
XMage's ``./db/cards.h2``; H2 then refuses about one start in ten with ``Lock file
recently modified`` (XMAGE_CARD_REPOSITORY_INIT_FAILED). No JVM is started here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pilot_decision_report.py"
spec = importlib.util.spec_from_file_location("pilot_decision_report_private_under_test", SCRIPT)
assert spec and spec.loader
pdr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdr)


class _RecordingRunner:
    """Stands in for XmageFullGameRunner: records how it was built, never plays."""

    built: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, command: tuple[str, ...], **kwargs: Any) -> None:
        self.built.append(kwargs)

    def run(self, **_: Any) -> Any:
        raise RuntimeError("no game is played in this test")


def test_a_single_game_uses_a_private_card_repository(monkeypatch: Any) -> None:
    _RecordingRunner.built.clear()
    monkeypatch.setattr(pdr, "XmageFullGameRunner", _RecordingRunner)
    scenario = SimpleNamespace(model_copy=lambda update: SimpleNamespace(**update))
    row = pdr._play(
        ("java", "-jar", "x.jar", "full-game"), "real", (scenario, ("a", "b", "c", "d"), ()), 7
    )
    assert row["status"] == "failed"  # the stand-in refused to play
    assert _RecordingRunner.built == [{"private_card_repository": True}]
