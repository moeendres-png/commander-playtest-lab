"""D2: batch resume is bound to the bytes that execute, not only to the inputs.

A completed full-game record may be reused only when the same bridge artifact,
decision protocol and result schema would execute the case again. Rebuilding
the bridge jar must force re-execution; the identical jar reuses the record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    assert list(identity["bridge_artifacts"]) == ["2"]
    assert len(identity["bridge_artifacts"]["2"]) == 64


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


def test_same_batch_object_refreshes_after_rebuild(tmp_path: Path) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"build-1")
    runner = _CountingRunner(jar)
    batch = XmageFullGameBatchRunner(runner, tmp_path / "out")  # type: ignore[arg-type]
    batch.run((_case(),))
    jar.write_bytes(b"build-2")
    assert batch.run((_case(),)).resumed_cases == 0
    assert runner.calls == 2
    assert batch.run((_case(),)).resumed_cases == 1
    assert runner.calls == 2


@pytest.mark.parametrize("explicit", [True, False])
def test_relative_artifact_uses_actual_engine_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, explicit: bool
) -> None:
    engine = tmp_path / "engine"
    engine.mkdir()
    jar = engine / "bridge.jar"
    jar.write_bytes(b"real-1")
    (tmp_path / "bridge.jar").write_bytes(b"decoy")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENGINE_RUNTIME_DIRECTORY", str(engine))
    runner = _CountingRunner(Path("bridge.jar"))
    if explicit:
        runner.cwd = engine
    batch = XmageFullGameBatchRunner(runner, tmp_path / "out")  # type: ignore[arg-type]
    batch.run((_case(),))
    (tmp_path / "bridge.jar").write_bytes(b"decoy-change")
    assert batch.run((_case(),)).resumed_cases == 1
    jar.write_bytes(b"real-2")
    assert batch.run((_case(),)).resumed_cases == 0
    assert runner.calls == 2


def test_artifact_basename_collision_cannot_hide_a_rebuild(tmp_path: Path) -> None:
    first, second = tmp_path / "a" / "bridge.jar", tmp_path / "b" / "bridge.jar"
    for jar in (first, second):
        jar.parent.mkdir()
        jar.write_bytes(b"build")
    runner = _CountingRunner(first)
    runner.command += (str(second),)
    batch = XmageFullGameBatchRunner(runner, tmp_path / "out")  # type: ignore[arg-type]
    batch.run((_case(),))
    first.write_bytes(b"new-first")
    assert batch.run((_case(),)).resumed_cases == 0
    assert len(batch.execution_identity()["bridge_artifacts"]) == 2


def test_missing_artifact_fails_before_stale_reuse(tmp_path: Path) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"build")
    runner = _CountingRunner(jar)
    batch = XmageFullGameBatchRunner(runner, tmp_path / "out")  # type: ignore[arg-type]
    batch.run((_case(),))
    jar.unlink()
    with pytest.raises(ValueError, match="execution identity unavailable"):
        batch.run((_case(),))
    assert runner.calls == 1


@pytest.mark.parametrize("field", ["command", "max_decisions", "request_timeout_seconds", "cwd"])
def test_material_runner_configuration_changes_invalidate_resume(
    tmp_path: Path, field: str
) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"build")
    runner = _CountingRunner(jar)
    batch = XmageFullGameBatchRunner(runner, tmp_path / "out")  # type: ignore[arg-type]
    batch.run((_case(),))
    setattr(
        runner,
        field,
        (*runner.command, "--different")
        if field == "command"
        else (str(tmp_path) if field == "cwd" else 9),
    )
    assert batch.run((_case(),)).resumed_cases == 0


def test_artifact_drift_during_execution_cannot_complete(tmp_path: Path) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"build")

    class MutatingRunner(_CountingRunner):
        def run(self, **kwargs: object) -> object:
            result = super().run(**kwargs)
            jar.write_bytes(b"changed")
            return result

    batch = XmageFullGameBatchRunner(MutatingRunner(jar), tmp_path / "out")  # type: ignore[arg-type]
    report = batch.run((_case(),))
    assert report.completed_cases == 0
    assert report.failed_cases == 1
    assert report.records[0].result is None


def test_unreadable_identity_is_safe_and_cannot_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"build")
    runner = _CountingRunner(jar)
    batch = XmageFullGameBatchRunner(runner, tmp_path / "out")  # type: ignore[arg-type]
    batch.run((_case(),))
    original = Path.open

    def denied(path, *a, **kw):
        if path == jar:
            raise PermissionError("private-credential-in-path")
        return original(path, *a, **kw)

    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(ValueError) as exc:
        batch.run((_case(),))
    assert str(exc.value) == "full-game batch execution identity unavailable"
    assert exc.value.__context__ is None
    assert exc.value.__cause__ is None
    assert not getattr(exc.value, "__notes__", ())
    assert runner.calls == 1


def test_identity_does_not_expose_command_arguments_or_paths(tmp_path: Path) -> None:
    jar = tmp_path / "private-artifact.jar"
    jar.write_bytes(b"build")
    runner = _CountingRunner(jar)
    runner.command += ("private-command-credential",)
    identity = XmageFullGameBatchRunner(runner, tmp_path).execution_identity()  # type: ignore[arg-type]
    public = json.dumps(identity)
    assert "private" not in public
    assert str(tmp_path) not in public


@pytest.mark.parametrize("field", ["scenario", "seed", "terminal"])
def test_completed_record_must_bind_the_requested_scenario(tmp_path: Path, field: str) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"build")
    runner = _CountingRunner(jar)
    batch = XmageFullGameBatchRunner(runner, tmp_path / "out")  # type: ignore[arg-type]
    batch.run((_case(),))
    path = next((tmp_path / "out").glob("*.json"))
    payload = json.loads(path.read_text())
    if field == "scenario":
        payload["result"]["scenario"]["seed"] += 1
    elif field == "seed":
        payload["result"]["result_payload"]["seed"] += 1
    else:
        payload["result"]["result_payload"]["terminal"] = False
    path.write_text(json.dumps(payload))
    assert batch.run((_case(),)).resumed_cases == 0
    assert runner.calls == 2
