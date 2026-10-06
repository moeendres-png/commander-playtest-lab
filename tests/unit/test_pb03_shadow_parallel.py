"""#479 Priority E item 2: the opt-in Forge/XMage native-suite overlap.

The overlap is a shadow experiment only. These tests pin the three properties
that make it safe to compare against the credited serial path:

- with the variable unset, ``run_all_native_suites`` still executes the same
  candidates and groups in the same order with the same receipts;
- with the variable set, the returned receipt list order is identical and the
  Forge groups really do start while the main thread is still in the XMage
  phases;
- a Forge-thread failure is re-raised, never swallowed at pool shutdown.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "run_current_boundary_qualification.py"


def _runner_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("FORGE_WORKSPACE", str(REPO))
    monkeypatch.delenv("CURRENT_BOUNDARY_EVIDENCE_EPOCH", raising=False)
    spec = importlib.util.spec_from_file_location("pb03_shadow_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _expected_order(module: Any) -> list[tuple[str, str]]:
    return [
        (candidate, group)
        for candidate in ("xmage", "forge")
        for group in module.NATIVE_SUITE_BINDING[candidate]["classes"]
    ]


def test_only_the_exact_value_one_enables_the_overlap(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _runner_module(monkeypatch)
    for value in ("0", "true", "yes", "TRUE", ""):
        monkeypatch.setenv(module.PB03_SHADOW_PARALLEL_FORGE_NATIVE_ENV, value)
        assert module.shadow_parallel_forge_native_enabled() is False, value
    monkeypatch.setenv(module.PB03_SHADOW_PARALLEL_FORGE_NATIVE_ENV, "1")
    assert module.shadow_parallel_forge_native_enabled() is True


def test_serial_native_suite_order_and_receipts_are_unchanged(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _runner_module(monkeypatch)
    monkeypatch.delenv(module.PB03_SHADOW_PARALLEL_FORGE_NATIVE_ENV, raising=False)
    calls: list[tuple[str, str]] = []

    def fake_run_native_suite(candidate: str, group: str, *, runner: Any) -> dict[str, Any]:
        calls.append((candidate, group))
        return {"candidate": candidate, "group": group, "tests": len(calls)}

    monkeypatch.setattr(module, "run_native_suite", fake_run_native_suite)
    receipts = module.run_all_native_suites(object(), ("xmage", "forge"))
    expected = _expected_order(module)
    assert calls == expected
    assert [(receipt["candidate"], receipt["group"]) for receipt in receipts] == expected
    assert [receipt["tests"] for receipt in receipts] == list(range(1, len(expected) + 1))
    output = capsys.readouterr().out
    assert "[pb03 shadow] overlap enabled" not in output
    assert output.count("[pb03 native]") == len(expected)


def test_serial_wrapper_runs_the_phases_after_the_suites(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _runner_module(monkeypatch)
    monkeypatch.delenv(module.PB03_SHADOW_PARALLEL_FORGE_NATIVE_ENV, raising=False)
    events: list[str] = []

    def fake_run_native_suite(candidate: str, group: str, *, runner: Any) -> dict[str, Any]:
        events.append(f"suite:{candidate}:{group}")
        return {"candidate": candidate, "group": group}

    monkeypatch.setattr(module, "run_native_suite", fake_run_native_suite)
    receipts = module.run_native_suites_with_shadow_overlap(
        object(), ("xmage", "forge"), xmage_phases=lambda: events.append("phases")
    )
    assert events[-1] == "phases"
    assert [event for event in events if event != "phases"] == [
        f"suite:{candidate}:{group}" for candidate, group in _expected_order(module)
    ]
    assert [(receipt["candidate"], receipt["group"]) for receipt in receipts] == _expected_order(
        module
    )


def test_shadow_overlap_starts_forge_before_the_phases_and_keeps_serial_order(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _runner_module(monkeypatch)
    monkeypatch.setenv(module.PB03_SHADOW_PARALLEL_FORGE_NATIVE_ENV, "1")
    forge_started = threading.Event()
    release_forge = threading.Event()

    def fake_run_native_suite(candidate: str, group: str, *, runner: Any) -> dict[str, Any]:
        if candidate == "forge":
            forge_started.set()
            release_forge.wait(timeout=30)
        return {"candidate": candidate, "group": group}

    monkeypatch.setattr(module, "run_native_suite", fake_run_native_suite)
    phases: list[str] = []

    def xmage_phases() -> None:
        # The overlap is real only if the Forge worker started while the main
        # thread is still here, before the Forge future is joined.
        assert forge_started.wait(timeout=30), "Forge native groups never started"
        phases.append("ran")
        release_forge.set()

    receipts = module.run_native_suites_with_shadow_overlap(
        object(), ("xmage", "forge"), xmage_phases=xmage_phases
    )
    assert phases == ["ran"]
    assert [(receipt["candidate"], receipt["group"]) for receipt in receipts] == _expected_order(
        module
    )
    output = capsys.readouterr().out
    assert output.count("[pb03 shadow] overlap enabled") == 1
    assert output.count("[pb03 native]") == len(_expected_order(module))


def test_a_forge_thread_failure_propagates_and_is_never_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _runner_module(monkeypatch)
    monkeypatch.setenv(module.PB03_SHADOW_PARALLEL_FORGE_NATIVE_ENV, "1")

    def fake_run_native_suite(candidate: str, group: str, *, runner: Any) -> dict[str, Any]:
        if candidate == "forge":
            raise RuntimeError("forge native suite exploded")
        return {"candidate": candidate, "group": group}

    monkeypatch.setattr(module, "run_native_suite", fake_run_native_suite)
    with pytest.raises(RuntimeError, match="forge native suite exploded"):
        module.run_native_suites_with_shadow_overlap(object(), ("xmage", "forge"))
