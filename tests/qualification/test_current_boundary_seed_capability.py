"""The seed is sent only when the provider declares it accepts one.

The XMage generic B4-D lane reports `seed_supported=false` and rejects a
create-game request carrying a seed with `unsupported_game_option: B4-D does not
support seed`. Passing it anyway turned an honestly uncontrolled run into a hard
failure, which is the wrong way round: a provider that cannot take a seed should
produce an UNCONTROLLED_ENGINE_RNG binding and no RNG credit, not a broken run.

These tests pin the capability-driven behaviour and the fail-closed defaults.
"""

from __future__ import annotations

import ast
from pathlib import Path

from commander_lab.qualification.current_boundary.game_driver import (
    _create_request,
    _declares_seed_support,
    _failure_detail,
)

REPO = Path(__file__).resolve().parents[2]
DRIVER = REPO / "src/commander_lab/qualification/current_boundary/game_driver.py"


class _Proc:
    def __init__(self, capabilities: object) -> None:
        self.capabilities = capabilities

    def request(self, message: str, payload: dict, **kwargs: object) -> dict:
        return {"success": True, "payload": {"capabilities": self.capabilities}}


def test_seed_is_sent_when_the_provider_declares_support() -> None:
    request = _create_request("g1", ["h1", "h2"], 424242, True)["request"]
    assert request["game_id"] == "g1"
    assert request["seed"] == 424242
    assert request["rules_seed"] == 424242
    assert request["options"]["seed"] == 424242


def test_seed_is_omitted_when_the_provider_declares_no_support() -> None:
    """The exact B4-D failure, prevented."""
    request = _create_request("g1", ["h1", "h2"], 424242, False)["request"]
    assert "seed" not in request
    assert "rules_seed" not in request
    assert "options" not in request
    # Everything the provider does need is still present.
    assert request["game_id"] == "g1"
    assert request["deck_handles"] == ["h1", "h2"]
    assert request["external_control"] is True


def test_create_request_is_not_double_nested() -> None:
    """A regression: wrapping twice dropped request.game_id entirely."""
    payload = _create_request("g7", ["h"], 1, False)
    assert list(payload) == ["request"]
    assert "request" not in payload["request"]


def test_declared_support_is_read_from_capabilities() -> None:
    assert _declares_seed_support(_Proc({"seed_supported": True})) is True
    assert _declares_seed_support(_Proc({"seed_supported": False})) is False


def test_absent_or_malformed_capability_defaults_to_no_support() -> None:
    """Unknown must never mean 'send the seed'."""
    for capabilities in (None, {}, {"seed_supported": None}, {"seed_supported": "yes"}, []):
        assert _declares_seed_support(_Proc(capabilities)) is False, capabilities


def test_capability_probe_failure_defaults_to_no_support() -> None:
    class Broken:
        def request(self, *a: object, **k: object) -> dict:
            raise TimeoutError("bridge down")

    assert _declares_seed_support(Broken()) is False  # type: ignore[arg-type]


def test_provider_error_detail_is_preserved() -> None:
    """A refused step is not diagnosable without the provider's own reason."""
    detail = _failure_detail(
        {
            "status": "error",
            "errors": [
                {"code": "unsupported_game_option", "message": "B4-D does not support seed"}
            ],
        }
    )
    assert "unsupported_game_option" in detail
    assert "B4-D does not support seed" in detail


def test_multiple_errors_are_all_reported() -> None:
    detail = _failure_detail(
        {"status": "error", "errors": [{"code": "a", "message": "x"}, {"code": "b"}]}
    )
    assert "a: x" in detail
    assert "b" in detail


def test_missing_error_detail_is_stated_rather_than_silent() -> None:
    detail = _failure_detail({"status": "error"})
    assert "no error detail" in detail


def test_driver_reads_capability_before_creating_the_game() -> None:
    source = DRIVER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_declares_seed_support"
    ]
    creates = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "request"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "create_commander_game"
    ]
    assert calls and creates
    assert min(calls) < min(creates), "capability must be read before the game is created"


def test_require_ok_keeps_the_provider_reason() -> None:
    source = DRIVER.read_text(encoding="utf-8")
    assert "_failure_detail(response)" in source
