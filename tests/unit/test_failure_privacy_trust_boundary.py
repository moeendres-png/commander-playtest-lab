"""Untrusted diagnostics are not a public error-code or exception-message authority."""

from __future__ import annotations

import json
import traceback
from pathlib import Path

import pytest

from commander_lab.engine.rules.failure_privacy import (
    machine_codes,
    redacted_exception_message,
    redacted_summary,
)
from commander_lab.engine.rules.full_game import (
    FullGameConformanceError,
    FullGameProtocolError,
    _RawFullGameClient,
    audit_actor_scoped_frame,
    public_full_game_errors,
)
from commander_lab.engine.rules.full_game_batch import XmageFullGameBatchRunner
from tests.unit.test_full_game_batch_resume_identity import _case
from tests.unit.test_full_game_failure_privacy import _fake_bridge, _LeakyRunner


@pytest.mark.parametrize("error_type", [FullGameProtocolError, FullGameConformanceError])
def test_exact_public_error_notes_cannot_cross_the_runner_boundary(
    error_type: type[Exception],
) -> None:
    private = "PRIVATE_HAND_CANARY_7E4B"
    original = error_type("outside authoritative domain")
    original.add_note(private)
    if isinstance(original, FullGameProtocolError):
        original.code = "ILLEGAL_ACTION"
        original.diagnostics = (private,)

    @public_full_game_errors
    def operation() -> None:
        raise original

    with pytest.raises(error_type) as caught:
        operation()
    assert caught.value is not original
    assert "outside authoritative domain" in str(caught.value)
    assert private not in "".join(traceback.format_exception(caught.value))
    assert not getattr(caught.value, "__notes__", ())
    if isinstance(caught.value, FullGameProtocolError):
        assert caught.value.code == "ILLEGAL_ACTION"
        assert caught.value.diagnostics == (private,)  # process-local diagnostic channel


@pytest.mark.parametrize(
    "private",
    [
        "PRIVATE_HAND_CANARY_7E4B",
        "prefix_PRIVATE_HAND_CANARY_7E4B_suffix",
        "PRIVATE_HAND_CANARY_7E4B: PLAYER_LEFT_GAME_UNSUPPORTED_DECISION",
        '{"hidden": "PRIVATE_HAND_CANARY_7E4B"}',
        "PRIVATE_HAND_CANARY_7E4B\nBRIDGE_TIMEOUT",
    ],
)
def test_raw_tokens_are_not_an_authority_for_public_machine_codes(private: str) -> None:
    message = redacted_summary("BRIDGE_ERROR", (private,))
    assert "PRIVATE_HAND" not in message
    assert message.startswith("BRIDGE_ERROR")
    assert "diagnostics sha256:" in message
    assert all("PRIVATE_HAND" not in code for code in machine_codes((private,)))


def test_untrusted_summary_prefix_is_redacted_too() -> None:
    assert "PRIVATE_HAND" not in redacted_summary("PRIVATE_HAND_CANARY_7E4B", ())


@pytest.mark.parametrize("error_type", [FullGameProtocolError, FullGameConformanceError])
@pytest.mark.parametrize("private", ["PRIVATE_HAND_CANARY_7E4B", "Private hidden card 7f3a"])
def test_direct_public_full_game_error_is_redacted(
    error_type: type[Exception], private: str
) -> None:
    exc = error_type(private)
    assert private not in str(exc)
    assert "diagnostics sha256:" in str(exc)


def test_actor_scope_audit_does_not_interpolate_unvalidated_seats() -> None:
    private = "Private hidden card 7f3a"
    frame = {
        "actor_id": "P1",
        "pilot_state": {
            "players": [
                {"is_actor": True, "player_id": "P1"},
                {"seat": private, "hand": [private]},
            ]
        },
    }
    rows, visible, violations = audit_actor_scoped_frame(frame)
    assert (rows, visible) == (1, 0)
    assert violations == ["seat invalid exposes hand to another principal"]


def test_validation_traceback_cannot_publish_raw_protocol_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private = "Private hidden card 7f3a"
    client = _RawFullGameClient(("unused", "full-game"), request_timeout_seconds=1)

    class Process:
        class Input:
            def write(self, _text: str) -> None:
                pass

            def flush(self) -> None:
                pass

        stdin = Input()

        def poll(self) -> None:
            return None

    monkeypatch.setattr(client, "start", lambda: None)
    monkeypatch.setattr(client, "_process", Process())
    client._stdout_queue.put(json.dumps({"success": True, "status": private}))
    with pytest.raises(FullGameProtocolError) as caught:
        client.request("get_provider_version")
    assert caught.value.code == "INVALID_RESPONSE"
    assert private not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("kind", ["attribute", "property", "type_name", "protocol"])
def test_exception_metadata_cannot_assert_that_it_is_public(kind: str) -> None:
    private = "PRIVATE_HAND_CANARY_7E4B"
    if kind == "attribute":
        exc = RuntimeError(private)
        exc.public_message = private  # type: ignore[attr-defined]
    elif kind == "property":

        class Error(RuntimeError):
            @property
            def public_message(self) -> str:
                raise AssertionError("untrusted properties must not execute")

        exc = Error(private)
    elif kind == "type_name":
        exc = type(private, (RuntimeError,), {})(private)
    else:
        exc = FullGameProtocolError(private, code=private, diagnostics=(private,))
    message = redacted_exception_message(exc)
    assert "PRIVATE_HAND" not in message
    assert "diagnostics sha256:" in message


def test_stable_known_codes_and_digest_remain_correlatable() -> None:
    raw = "XMAGE_FULL_GAME_FAILED: PLAYER_LEFT_GAME_UNSUPPORTED_DECISION"
    first = redacted_summary("BRIDGE_ERROR", (raw,))
    assert machine_codes((raw, raw)) == (
        "XMAGE_FULL_GAME_FAILED",
        "PLAYER_LEFT_GAME_UNSUPPORTED_DECISION",
    )
    assert first == redacted_summary("BRIDGE_ERROR", (raw,))
    assert first != redacted_summary("BRIDGE_ERROR", (raw + " private detail",))
    assert redacted_exception_message(ValueError("private detail")).startswith("ValueError")


def test_unknown_tokens_cannot_exhaust_the_public_code_budget() -> None:
    private = " ".join(f"PRIVATE_HAND_CANARY_{index}" for index in range(20))
    assert machine_codes((private + " BRIDGE_TIMEOUT",)) == ("BRIDGE_TIMEOUT",)


@pytest.mark.parametrize("error_type", [FullGameProtocolError, FullGameConformanceError])
def test_implicit_exception_context_is_not_public(error_type: type[Exception]) -> None:
    private = "Private hidden card 7f3a"
    try:
        try:
            raise ValueError(private)
        except ValueError:
            raise error_type("Lab check failed")  # noqa: B904 — exercise implicit context deliberately
    except error_type as exc:
        assert private not in "".join(traceback.format_exception(exc))


@pytest.mark.parametrize("kind", ["attribute", "type_name", "protocol", "formatting"])
def test_real_smoke_failure_record_and_rethrow_stay_private(
    repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    from tests.unit.test_real_4p_full_game_smoke import _load_smoke_module

    private = "PRIVATE_HAND_CANARY_7E4B"
    if kind == "attribute":
        exc = RuntimeError(private)
        exc.public_message = private  # type: ignore[attr-defined]
    elif kind == "type_name":
        exc = type(private, (RuntimeError,), {})(private)
    elif kind == "protocol":
        exc = FullGameProtocolError(private, code=private)
        assert exc.code == "ENGINE_FAILURE"
    else:

        class Error(RuntimeError):
            def __str__(self) -> str:
                raise ValueError(private)

        exc = Error()

    class Runner:
        def run_smoke(self, **_kwargs: object) -> None:
            raise exc

    module = _load_smoke_module(repo_root)
    monkeypatch.setattr(module, "XmageFullGameRunner", lambda **_kwargs: Runner())
    artifact = tmp_path / "smoke.json"
    monkeypatch.setattr(module, "_artifact_path", lambda *_args: artifact)
    with pytest.raises(FullGameConformanceError) as caught:
        module.run_live_smoke(repo_root)
    assert private not in "".join(traceback.format_exception(caught.value))
    report = json.loads(artifact.read_text())
    assert report["status"] == "FAIL"
    assert report["failure_class"] == "RuntimeError"
    assert private not in artifact.read_text()


@pytest.mark.parametrize("kind", ["attribute", "type_name", "protocol", "formatting"])
def test_batch_failure_json_never_persists_untrusted_metadata(tmp_path: Path, kind: str) -> None:
    private = "PRIVATE_HAND_CANARY_7E4B"
    if kind == "attribute":
        exc = RuntimeError(private)
        exc.public_message = private  # type: ignore[attr-defined]
    elif kind == "type_name":
        exc = type(private, (RuntimeError,), {})(private)
    elif kind == "protocol":
        exc = FullGameProtocolError(private, code=private)
    else:

        class Error(RuntimeError):
            def __str__(self) -> str:
                raise ValueError(private)

        exc = Error()
    runner = XmageFullGameBatchRunner(_LeakyRunner(exc), tmp_path)  # type: ignore[arg-type]
    report = runner.run((_case(),))
    assert report.records[0].status == "failed"
    assert "PRIVATE_HAND" not in json.dumps(report.model_dump(mode="json"))
    paths = list(tmp_path.glob("*.json"))
    assert paths
    for path in paths:
        assert "PRIVATE_HAND" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("field", ["seat", "minimum_selections", "decision_offset"])
def test_runner_redacts_raw_engine_numeric_conversion_failures(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    from tests.unit.test_full_game_hidden_audit import _frame, _run

    private = "PRIVATE_HAND_CANARY_7E4B"
    frame = _frame()
    if field == "seat":
        frame["pilot_state"][field] = private
    else:
        frame[field] = private
    with pytest.raises(ValueError) as caught:
        _run(monkeypatch, [frame])
    assert private not in str(caught.value)
    assert private not in "".join(traceback.format_exception(caught.value))


def test_runner_redacts_malformed_winner_seat(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit import test_full_game_hidden_audit as fixture

    private = "PRIVATE_HAND_CANARY_7E4B"
    original = fixture._result_payload

    def result(count: int, seed: int) -> dict[str, object]:
        payload = original(count, seed)
        payload["outcomes"][0]["seat"] = private
        return payload

    monkeypatch.setattr(fixture, "_result_payload", result)
    with pytest.raises(ValueError) as caught:
        fixture._run(monkeypatch, [fixture._frame()])
    assert private not in str(caught.value)
    assert private not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("mode", ["error", "garbage", "exit"])
def test_transport_redacts_uppercase_private_bridge_output(tmp_path: Path, mode: str) -> None:
    command = _fake_bridge(tmp_path, mode)
    script = Path(command[1])
    script.write_text(
        script.read_text().replace(
            "Honeycard Sentinel of Hidden Hands 7f3a", "PRIVATE_HAND_CANARY_7E4B"
        )
    )
    client = _RawFullGameClient(command, request_timeout_seconds=20)
    try:
        with pytest.raises(FullGameProtocolError) as caught:
            client.request("get_provider_version")
    finally:
        client.close()
    assert "PRIVATE_HAND" not in str(caught.value)
    assert caught.value.code in {"BRIDGE_ERROR", "INVALID_RESPONSE", "BRIDGE_CLOSED"}
