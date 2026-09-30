"""C4: full-game failure diagnostics never leave the process unredacted.

A honeycard sentinel is planted in everything a failing bridge or engine can
emit: stderr, the engine's error message, a raw protocol line and an engine
failure object. The sentinel must not appear in the exception message, the
batch record or the persisted evidence file, while the failure stays
classified and correlatable (stable code, machine codes, diagnostics digest).
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from commander_lab.engine.rules.failure_privacy import (
    diagnostics_digest,
    machine_codes,
    redacted_exception_message,
    redacted_summary,
)
from commander_lab.engine.rules.full_game import (
    FullGameConformanceError,
    FullGameProtocolError,
    _RawFullGameClient,
)
from commander_lab.engine.rules.full_game_batch import (
    FullGameBatchCase,
    FullGameFailureClass,
    XmageFullGameBatchRunner,
)

SENTINEL = "Honeycard Sentinel of Hidden Hands 7f3a"
SECRET = "hunter2-token-9c1e"


def _fake_bridge(tmp_path: Path, mode: str) -> tuple[str, ...]:
    script = tmp_path / "fake_bridge.py"
    script.write_text(
        textwrap.dedent(
            f"""
            import json, sys
            sys.stderr.write("opponent hand: {SENTINEL}; MAVEN_OPTS=-Dtoken={SECRET}\\n")
            sys.stderr.flush()
            mode = {mode!r}
            for line in sys.stdin:
                request = json.loads(line)
                if mode == "error":
                    reply = {{"request_id": request["request_id"], "ok": False,
                              "error": {{"code": "XMAGE_FULL_GAME_FAILED",
                                        "message": "PLAYER_LEFT_GAME_UNSUPPORTED_DECISION: "
                                                   "revealed {SENTINEL} to the wrong seat"}}}}
                    print(json.dumps(reply), flush=True)
                elif mode == "garbage":
                    print("not-json {SENTINEL}", flush=True)
                else:
                    sys.exit(3)
            """
        ),
        encoding="utf-8",
    )
    return (sys.executable, str(script), "full-game")


def _assert_private(text: str) -> None:
    assert SENTINEL not in text
    assert "Honeycard" not in text
    assert SECRET not in text


@pytest.mark.parametrize(
    ("mode", "code"),
    [("error", "BRIDGE_ERROR"), ("garbage", "INVALID_RESPONSE"), ("exit", "BRIDGE_CLOSED")],
)
def test_transport_failures_carry_a_code_and_no_raw_text(
    tmp_path: Path, mode: str, code: str
) -> None:
    client = _RawFullGameClient(_fake_bridge(tmp_path, mode), request_timeout_seconds=20)
    try:
        with pytest.raises(FullGameProtocolError) as caught:
            client.request("get_provider_version")
    finally:
        client.close()
    exc = caught.value
    assert exc.code == code
    assert code in str(exc)
    _assert_private(str(exc))
    _assert_private(exc.public_message)
    _assert_private(redacted_exception_message(exc))
    # The raw material is still available in memory for local debugging.
    assert any(SENTINEL in part for part in exc.diagnostics) or mode == "exit"
    if mode == "error":
        assert "PLAYER_LEFT_GAME_UNSUPPORTED_DECISION" in str(exc)
        assert "XMAGE_FULL_GAME_FAILED" in str(exc)
    assert "diagnostics sha256:" in str(exc) or not exc.diagnostics


def test_engine_failure_object_is_reduced_to_codes() -> None:
    failure = {
        "type": "decision_controller",
        "message": f"XMAGE_FULL_GAME_FAILED: {SENTINEL} was in the library",
    }
    message = "XMage full-game engine failed: " + redacted_summary(
        "ENGINE_FAILURE", (json.dumps(failure, sort_keys=True),)
    )
    _assert_private(message)
    assert "ENGINE_FAILURE" in message
    assert "XMAGE_FULL_GAME_FAILED" in message


def test_unknown_exception_text_is_never_persisted_verbatim() -> None:
    exc = RuntimeError(f"java.lang.IllegalStateException: {SENTINEL} {SECRET}")
    message = redacted_exception_message(exc)
    _assert_private(message)
    assert message.startswith("RuntimeError")


def test_machine_codes_keep_codes_and_drop_names() -> None:
    codes = machine_codes(
        ["Lightning Bolt hit P2: PLAYER_LEFT_GAME and BRIDGE_TIMEOUT", "Sol Ring"]
    )
    assert codes == ("PLAYER_LEFT_GAME", "BRIDGE_TIMEOUT")
    assert diagnostics_digest(["a"]) != diagnostics_digest(["b"])
    assert len(diagnostics_digest(["a"])) == 16


class _LeakyRunner:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def run(self, **_kwargs: object) -> Any:
        raise self.exc


@pytest.mark.parametrize(
    ("exc", "failure_class"),
    [
        (
            FullGameProtocolError(
                "get_provider_version failed: BRIDGE_ERROR",
                code="BRIDGE_ERROR",
                diagnostics=(SENTINEL,),
            ),
            FullGameFailureClass.PROTOCOL,
        ),
        (
            FullGameConformanceError(
                "XMage full-game engine failed: "
                + redacted_summary("ENGINE_FAILURE", (json.dumps({"m": SENTINEL}),))
            ),
            FullGameFailureClass.CONFORMANCE,
        ),
        (ValueError(f"bad deck {SENTINEL} {SECRET}"), FullGameFailureClass.CONFIGURATION),
        (RuntimeError(f"engine crashed on {SENTINEL}"), FullGameFailureClass.ENGINE),
    ],
)
def test_batch_record_and_evidence_file_stay_private(
    tmp_path: Path, exc: Exception, failure_class: FullGameFailureClass
) -> None:
    from tests.unit.test_xmage_full_game import _binding, _decks, _scenario

    decks = _decks()
    case = FullGameBatchCase(
        case_id="honeycard",
        scenario=_scenario(decks),
        decks=decks,
        pilots=tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, 5)),  # type: ignore[arg-type]
    )
    report = XmageFullGameBatchRunner(_LeakyRunner(exc), tmp_path).run((case,))  # type: ignore[arg-type]
    record = report.records[0]
    assert record.status == "failed"
    assert record.failure_class is failure_class
    assert record.failure_message
    _assert_private(record.failure_message)
    _assert_private(json.dumps(report.model_dump(mode="json")))
    for evidence_file in tmp_path.glob("*.json"):
        _assert_private(evidence_file.read_text(encoding="utf-8"))
