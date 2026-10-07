"""#479 Priority E item 2: the opt-in Forge/XMage native-suite overlap.

The overlap is a shadow experiment only. These tests pin the three properties
that make it safe to compare against the credited serial path:

- with the variable unset, ``run_all_native_suites`` still executes the same
  candidates and groups in the same order with the same receipts;
- with the variable set, the returned receipt list order is identical and the
  Forge groups really do start while the main thread is still in the XMage
  phases;
- a Forge-thread failure is re-raised, never swallowed at pool shutdown;
- when the calling thread and the Forge thread both fail, the calling thread's
  failure stays authoritative and the Forge failure is chained as its cause;
- a real, identity-valid Forge checkout resolves to a suite root whose surefire
  report directories are disjoint from the XMage bridge's.
"""

from __future__ import annotations

import importlib.util
import subprocess
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


def test_both_failures_stay_visible_and_the_calling_thread_failure_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _runner_module(monkeypatch)
    monkeypatch.setenv(module.PB03_SHADOW_PARALLEL_FORGE_NATIVE_ENV, "1")

    def fake_run_native_suite(candidate: str, group: str, *, runner: Any) -> dict[str, Any]:
        if candidate == "forge":
            raise RuntimeError("forge native suite exploded")
        return {"candidate": candidate, "group": group}

    monkeypatch.setattr(module, "run_native_suite", fake_run_native_suite)

    def broken_phases() -> None:
        raise ValueError("xmage phases exploded")

    with pytest.raises(ValueError, match="xmage phases exploded") as caught:
        module.run_native_suites_with_shadow_overlap(
            object(), ("xmage", "forge"), xmage_phases=broken_phases
        )
    cause = caught.value.__cause__
    assert isinstance(cause, RuntimeError), (
        "the Forge-thread failure must stay visible as the primary failure's cause, "
        f"got cause={cause!r}"
    )
    assert "forge native suite exploded" in str(cause)


def test_shadow_overlap_without_xmage_phases_joins_and_keeps_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _runner_module(monkeypatch)
    monkeypatch.setenv(module.PB03_SHADOW_PARALLEL_FORGE_NATIVE_ENV, "1")
    main_thread = threading.main_thread()
    calls: list[tuple[str, str, bool]] = []

    def fake_run_native_suite(candidate: str, group: str, *, runner: Any) -> dict[str, Any]:
        calls.append((candidate, group, threading.current_thread() is main_thread))
        return {"candidate": candidate, "group": group}

    monkeypatch.setattr(module, "run_native_suite", fake_run_native_suite)
    receipts = module.run_native_suites_with_shadow_overlap(
        object(), ("xmage", "forge"), xmage_phases=None
    )
    expected = _expected_order(module)
    assert [(receipt["candidate"], receipt["group"]) for receipt in receipts] == expected
    assert {(candidate, group) for candidate, group, _ in calls} == set(expected)
    assert all(on_main_thread for candidate, _, on_main_thread in calls if candidate == "xmage")
    assert not any(
        on_main_thread for candidate, _, on_main_thread in calls if candidate == "forge"
    ), "the Forge groups must still execute on the pool thread without XMage phases"


def _git(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def _make_forge_workspace(tmp_path: Path) -> Path:
    """A minimal, clean, identity-valid Forge checkout with the bridge module."""
    forge = tmp_path / "forge"
    bridge = forge / "forge-protocol2-bridge" / "src"
    bridge.mkdir(parents=True)
    (bridge / "Main.java").write_text("// bridge fixture\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main", str(forge)], check=True)
    subprocess.run(["git", "config", "user.email", "shadow@example.invalid"], cwd=forge, check=True)
    subprocess.run(["git", "config", "user.name", "Shadow Test"], cwd=forge, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=forge, check=True)
    subprocess.run(["git", "add", "-A"], cwd=forge, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "forge workspace fixture"], cwd=forge, check=True)
    return forge


def test_a_real_forge_workspace_resolves_outside_the_xmage_bridge_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The no-shared-files property, exercised through real suite-root resolution.

    Every other test here monkeypatches ``run_native_suite``, so no Forge suite
    root is ever resolved. This resolves one from a real, identity-valid Forge
    checkout and asserts the surefire report directories the overlapped threads
    read (and the one the runner clears) cannot overlap the XMage bridge's.
    """
    module = _runner_module(monkeypatch)
    forge = _make_forge_workspace(tmp_path)
    head = _git(["rev-parse", "HEAD"], forge)
    tree = _git(["rev-parse", "HEAD^{tree}"], forge)
    monkeypatch.setattr(module, "FORGE_WORKSPACE", forge)
    monkeypatch.setattr(
        module,
        "canonical_forge_authority",
        lambda: {"rules_core_commit": head, "bridge_commit": head, "bridge_tree": tree},
    )
    forge_root = Path(module.resolve_suite_root("forge")["root"]).resolve()
    xmage_root = Path(module.resolve_suite_root("xmage")["root"]).resolve()
    assert forge_root == forge.resolve()
    assert forge_root != xmage_root, "the two candidates resolved to one checkout"
    # The suite-root report expressions are `<root>/*/target/surefire-reports`;
    # if either root contained the other, those globs could read reports the
    # other overlapped thread is still writing.
    assert xmage_root not in forge_root.parents, (
        "the Forge suite root contains the XMage bridge tree, so its report globs "
        "could read reports the XMage phases are writing"
    )
    assert forge_root not in xmage_root.parents, (
        "the XMage bridge tree contains the Forge suite root, so the XMage report "
        "globs could read reports the Forge suite is writing"
    )
    forge_reports = {
        forge_root / "target" / "surefire-reports",
        *forge_root.glob("*/target/surefire-reports"),
    }
    xmage_reports = {
        xmage_root / "target" / "surefire-reports",
        *xmage_root.glob("*/target/surefire-reports"),
    }
    assert forge_reports.isdisjoint(xmage_reports)
    # The runner clears the XMage report tree before the overlap starts; no
    # Forge report directory may live under the directory being cleared.
    cleared = xmage_root / "target" / "surefire-reports"
    assert all(cleared != path and cleared not in path.parents for path in forge_reports)
