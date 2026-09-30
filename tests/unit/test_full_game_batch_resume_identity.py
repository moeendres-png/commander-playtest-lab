"""D2: batch resume is bound to the bytes that execute, not only to the inputs.

A completed full-game record may be reused only when the same bridge artifact,
decision protocol and result schema would execute the case again. Rebuilding
the bridge jar must force re-execution; the identical jar reuses the record.
"""

from __future__ import annotations

import json
from pathlib import Path

from commander_lab.engine.rules.full_game_batch import FullGameBatchCase, XmageFullGameBatchRunner
from tests.unit.test_xmage_full_game import _binding, _decks, _result, _scenario


class _CountingRunner:
    def __init__(self, jar: Path) -> None:
        self.command = ("java", "-jar", str(jar), "full-game")
        self.calls = 0
        self._decks = _decks()

    def run(self, **_kwargs: object) -> object:
        self.calls += 1
        return _result(_scenario(self._decks))


def _case() -> FullGameBatchCase:
    decks = _decks()
    return FullGameBatchCase(
        case_id="resume",
        scenario=_scenario(decks),
        decks=decks,
        pilots=tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, 5)),  # type: ignore[arg-type]
    )


def test_the_identical_bridge_reuses_the_completed_record(tmp_path: Path) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"build-1")
    runner = _CountingRunner(jar)
    XmageFullGameBatchRunner(runner, tmp_path / "out").run((_case(),))  # type: ignore[arg-type]
    report = XmageFullGameBatchRunner(runner, tmp_path / "out").run((_case(),))  # type: ignore[arg-type]
    assert runner.calls == 1
    assert report.records[0].resumed_from_completed_record is True


def test_a_rebuilt_bridge_forces_re_execution(tmp_path: Path) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"build-1")
    runner = _CountingRunner(jar)
    XmageFullGameBatchRunner(runner, tmp_path / "out").run((_case(),))  # type: ignore[arg-type]
    jar.write_bytes(b"build-2")
    report = XmageFullGameBatchRunner(runner, tmp_path / "out").run((_case(),))  # type: ignore[arg-type]
    assert runner.calls == 2
    assert report.records[0].resumed_from_completed_record is False


def test_the_identity_names_protocol_schema_and_artifact_digest(tmp_path: Path) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"build-1")
    identity = XmageFullGameBatchRunner(_CountingRunner(jar), tmp_path).execution_identity()  # type: ignore[arg-type]
    assert identity["decision_protocol_version"].startswith("xmage-external-decision-protocol-")
    assert identity["result_schema_version"].startswith("xmage-full-game-conformance-result-")
    assert list(identity["bridge_artifacts"]) == ["bridge.jar"]
    assert len(identity["bridge_artifacts"]["bridge.jar"]) == 64


def test_a_record_whose_stored_key_differs_is_not_reused(tmp_path: Path) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"build-1")
    runner = _CountingRunner(jar)
    batch = XmageFullGameBatchRunner(runner, tmp_path / "out")  # type: ignore[arg-type]
    batch.run((_case(),))
    record_path = next((tmp_path / "out").glob("*.json"))
    tampered = json.loads(record_path.read_text(encoding="utf-8"))
    tampered["run_key"] = "0" * 64
    record_path.write_text(json.dumps(tampered), encoding="utf-8")
    XmageFullGameBatchRunner(runner, tmp_path / "out").run((_case(),))  # type: ignore[arg-type]
    assert runner.calls == 2
