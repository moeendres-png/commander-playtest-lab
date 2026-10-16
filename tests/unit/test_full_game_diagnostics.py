"""Diagnostic hooks for the #816/#817/#818 coverage-sweep aborts.

- #818: _drive keeps a bounded trailing window of answered decisions and
  attaches a compact summary when max_decisions is exceeded, so a tight
  decision loop can be told apart from a calibration problem.
- #816: COMMANDER_LAB_XMAGE_JVM_FLAGS splices opt-in JVM flags (e.g.
  -XX:+HeapDumpOnOutOfMemoryError) into the bridge java command.
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.engine.rules.full_game import (
    XmageFullGameRunner,
    _summarize_recent_decisions,
    _with_jvm_flags,
)
from commander_lab.engine.rules.full_game_pilot.common import (
    XMAGE_JVM_FLAGS_ENV,
    FullGameProtocolError,
)


def _record(n: int, cls: str = "declare_attacker", turn: int = 7, seat: int = 2) -> dict[str, Any]:
    return {"n": n, "class": cls, "turn": turn, "seat": seat, "options": 3}


def test_summarize_recent_decisions_empty() -> None:
    assert _summarize_recent_decisions([]) == "recent=none"


def test_summarize_recent_decisions_counts_and_top() -> None:
    recent = [_record(n, "declare_blocker", turn=7, seat=2) for n in range(1, 6)]
    recent += [_record(n, "declare_attacker", turn=8, seat=3) for n in range(6, 8)]
    summary = _summarize_recent_decisions(recent)
    assert "recent=total:7" in summary
    assert "declare_blocker=5,declare_attacker=2" in summary
    assert "declare_blocker@turn=7/seat=2:5" in summary
    assert "tail=[1:declare_blocker@turn=7/seat=2/opts=3" in summary


def test_summarize_recent_decisions_ties_are_deterministic() -> None:
    # Only the sorted segments are order-independent; the tail is chronological.
    def head(summary: str) -> str:
        return summary.split(" tail=")[0]

    first = [_record(1, "b"), _record(2, "a")]
    second = [_record(2, "a"), _record(1, "b")]
    assert head(_summarize_recent_decisions(first)) == head(_summarize_recent_decisions(second))


def test_with_jvm_flags_unset_leaves_command_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(XMAGE_JVM_FLAGS_ENV, raising=False)
    command = ("java", "-jar", "bridge.jar", "full-game")
    assert _with_jvm_flags(command) == command


def test_with_jvm_flags_blank_leaves_command_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(XMAGE_JVM_FLAGS_ENV, "   ")
    command = ("java", "-jar", "bridge.jar", "full-game")
    assert _with_jvm_flags(command) == command


def test_with_jvm_flags_splices_after_java(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        XMAGE_JVM_FLAGS_ENV, "-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp/dump.hprof"
    )
    assert _with_jvm_flags(("java", "-jar", "bridge.jar", "full-game")) == (
        "java",
        "-XX:+HeapDumpOnOutOfMemoryError",
        "-XX:HeapDumpPath=/tmp/dump.hprof",
        "-jar",
        "bridge.jar",
        "full-game",
    )


def test_with_jvm_flags_ignores_non_java_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(XMAGE_JVM_FLAGS_ENV, "-XX:+HeapDumpOnOutOfMemoryError")
    command = ("python", "bridge.py", "full-game")
    assert _with_jvm_flags(command) == command


class _LoopClient:
    """Always offers another decision, so _drive runs into max_decisions."""

    def request(self, name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        assert name in ("start_full_game", "submit_full_game_decision")
        return {
            "decision": {
                "decision_class": "declare_attacker",
                "pilot_state": {"turn_number": 7, "phase": "combat"},
                "seat": 2,
                "legal_options": [{}, {}, {}],
            }
        }


class _NullPolicy:
    def decide(self, decision: dict[str, Any]) -> dict[str, Any]:
        return {}


def test_drive_exceeded_error_carries_recent_diagnostics() -> None:
    # The summary rides the in-memory diagnostics channel: the persisted
    # message stays redacted by design, diagnostics survive the boundary.
    runner = XmageFullGameRunner(
        command=("java", "-jar", "bridge.jar", "full-game"), max_decisions=5
    )
    with pytest.raises(FullGameProtocolError) as excinfo:
        runner._drive(_LoopClient(), _NullPolicy(), stop_after=None)  # type: ignore[arg-type]
    (summary,) = excinfo.value.diagnostics
    assert "recent=total:5" in summary
    assert "declare_attacker=5" in summary
