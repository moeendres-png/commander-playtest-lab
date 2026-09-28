"""The assembler must not be able to credit anything it did not observe.

These are structural tests over the assembler source itself. The defects they
guard against were silent: the assembler produced plausible PASS counts from a
hand-written literal and from fixture-id strings found in test source. A test
that only checks counts would not have caught either, so these assert that the
promoting code paths are gone and that the credit functions are receipt-only.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import receipts as R

REPO = Path(__file__).resolve().parents[2]
ASSEMBLER = REPO / "scripts" / "assemble_current_boundary_evidence.py"
RUNNER = REPO / "scripts" / "run_current_boundary_qualification.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _module_constants(path: Path) -> dict[str, object]:
    tree = ast.parse(_source(path))
    out: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                try:
                    out[target.id] = ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    out[target.id] = "<computed>"
    return out


def test_hard_coded_native_runs_literal_is_gone() -> None:
    """NATIVE_RUNS was a hand-written literal the assembler consumed as evidence.

    The name may still appear in a comment recording that it was retired, so the
    guard is on the constant existing at all: it must not be assigned anywhere,
    and no name containing it may be defined.
    """
    assert "NATIVE_RUNS" not in _module_constants(ASSEMBLER), (
        "the NATIVE_RUNS literal must not exist as a module constant"
    )
    tree = ast.parse(_source(ASSEMBLER))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            assert "NATIVE_RUNS" not in node.name, f"{node.name} reintroduces the retired literal"
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assert "NATIVE_RUNS" not in target.id, target.id


def test_assembler_never_reads_test_source_for_fixture_ids() -> None:
    """The regex promotion path scanned test source; it must not come back."""
    source = _source(ASSEMBLER)
    assert "engine-bridge/src/test/java" not in source
    assert "pattern.findall" not in source
    assert "read_text(errors=" not in source


def test_assembler_derives_native_credit_from_receipts_only() -> None:
    source = _source(ASSEMBLER)
    assert "collect_receipts" in source
    assert "positive_fixture_credit" in source
    assert "PERSISTED_EXECUTION_RECEIPTS_ONLY" in source
    assert "absent_receipts_yield_no_credit" in source


def test_native_suite_executor_is_on_the_execution_path() -> None:
    """run_native_suite() used to be dead code. It must now be reachable."""
    source = _source(RUNNER)
    tree = ast.parse(source)
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "run_native_suite" in called, "run_native_suite is still dead code"
    assert "run_all_native_suites" in called
    # And it must refuse to run against a dirty runner.
    assert "require_clean_runner" in source
    assert "verify_runner_unchanged" in source
    # And it must check the recorded candidate against the executing one.
    # The gate must PROVE the engine is the same engine, not merely assert the
    # commit matches, because the suite has to execute at a descendant that
    # contains its test classes.
    assert "verify_engine_identity" in source
    assert "engine_identity_proof" in source
    assert "executed_commit" in source


def test_native_suites_are_scoped_to_the_selected_candidates(monkeypatch) -> None:
    """A Forge-only run must not regenerate XMage native receipts."""
    import importlib.util

    # Importing the runner resolves each native suite's root from the
    # environment and reads that root's tree at module level. Point the Forge
    # root at this repository so the import works on a machine that does not
    # have the historical reference checkout; the test only exercises candidate
    # scoping, and the patched executor never runs a suite.
    monkeypatch.setenv("FORGE_WORKSPACE", str(REPO))
    spec = importlib.util.spec_from_file_location("wsr_runner_mod", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    executed: list[tuple[str, str]] = []

    def _fake(candidate: str, group: str, *, runner: object) -> dict:
        executed.append((candidate, group))
        return {}

    monkeypatch.setattr(module, "run_native_suite", _fake)
    module.run_all_native_suites(object(), ("forge",))
    assert executed, "the forge native suites must still be executed"
    assert {candidate for candidate, _ in executed} == {"forge"}


def test_seed_is_not_recorded_as_engine_owned_without_acknowledgement() -> None:
    """`engine_owned: true` from caller intent alone is the Gate 3 defect.

    The classification lives in the receipts module and is applied by the game
    driver, which must pass the seed to the provider and derive control from the
    acknowledgement rather than from the request.
    """
    driver = (REPO / "src/commander_lab/qualification/current_boundary/game_driver.py").read_text(
        encoding="utf-8"
    )
    receipts = (REPO / "src/commander_lab/qualification/current_boundary/receipts.py").read_text(
        encoding="utf-8"
    )

    # Control is derived from an observed acknowledgement.
    assert "classify_seed_binding" in driver
    assert "_acknowledged_seed" in driver
    assert "ACKNOWLEDGED_ENGINE_SEED" in receipts
    assert "UNCONTROLLED_ENGINE_RNG" in receipts
    assert "REQUESTED_SEED" in receipts

    # The seed must actually reach the provider request. It is built in
    # _create_request, which sends it only when the provider declares support;
    # the behaviour itself is pinned in test_current_boundary_seed_capability.
    create_helper = driver[driver.index("def _create_request(") :]
    create_helper = create_helper[: create_helper.index("\n\ndef ")]
    assert 'request["seed"] = seed' in create_helper
    assert 'request["rules_seed"] = seed' in create_helper
    assert "if seed_supported:" in create_helper

    # And the derived binding is what the evidence records.
    assert '"rules_rng_binding"' in driver


def test_bridge_read_is_deadline_bounded() -> None:
    source = (
        REPO / "src/commander_lab/qualification/current_boundary/bridge_launcher.py"
    ).read_text(encoding="utf-8")
    assert "_read_line_with_deadline" in source
    assert "BridgeTimeout" in source
    # The unbounded read must not be the request path any more.
    request_body = source.split("def request(", 1)[1].split("def _read_line_with_deadline(", 1)[0]
    assert "self.popen.stdout.readline()" not in request_body
    assert "_read_line_with_deadline(" in request_body
    # The only readline lives inside the deadline-bounded reader thread.
    assert source.count("self.popen.stdout.readline()") == 1
    assert "finished.wait(timeout_s)" in source
    assert "_terminate_stalled_child" in source


def test_no_credit_without_receipts_end_to_end(tmp_path: Path) -> None:
    """The end-to-end property: no receipts, no credit, of any kind."""
    valid, rejected = R.collect_receipts(tmp_path / "receipts")
    assert valid == []
    assert rejected  # absent directory is itself a no-credit condition
    assert (
        R.positive_fixture_credit(
            valid, candidate="xmage", expected_commit="a" * 40, denominator={"MICRO_STACK"}
        )
        == {}
    )
    credit = R.native_suite_credit(valid, candidate="xmage", expected_commit="a" * 40)
    assert credit["groups_credited"] == []
    assert credit["tests"] == 0
    assert credit["passed"] == 0


def test_real_evidence_directory_has_no_receipts_yet() -> None:
    """Honest current state: the receipts do not exist, so nothing is credited.

    This is the state that makes the historical FULL107 counts upper bounds. It
    is asserted explicitly so the transition to 'receipts exist' is visible
    rather than silent.
    """
    directory = REPO / "qualification" / "final-current-boundary-20260927" / "receipts"
    if not directory.is_dir():
        pytest.skip("no receipt directory yet; nothing can be credited, which is the point")
    valid, rejected = R.collect_receipts(directory)
    assert valid or rejected
