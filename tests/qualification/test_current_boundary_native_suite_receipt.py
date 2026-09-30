"""The native-suite receipt path must produce a receipt from a real execution.

The pb03-runtime CI job caught a defect this file now covers: the suite binding
carries ``build_identity`` as a JSON string (declared by ``_native_identity``),
and the receipt construction treated it as a mapping, so every native suite
crashed with ``ValueError: dictionary update sequence element #0 has length 1``
after the whole XMage column had already executed.

The test runs ``run_native_suite`` end to end with a faked Maven process and
asserts that a digest-bound receipt is produced and persisted under the receipt
directory, so the receipt path itself is covered without building an engine.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import receipts as receipt_mod

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "run_current_boundary_qualification.py"


class _Completed:
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def _runner_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_WORKSPACE", str(REPO))
    spec = importlib.util.spec_from_file_location("cb_native_receipt_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _clean_identity() -> receipt_mod.RunnerIdentity:
    captured = receipt_mod.capture_runner_identity(REPO)
    return receipt_mod.RunnerIdentity(
        repository=captured.repository,
        commit=captured.commit,
        tree=captured.tree,
        branch=captured.branch,
        dirty=False,
        dirty_paths=(),
        input_digests=captured.input_digests,
    )


def test_run_native_suite_produces_a_receipt_from_the_executed_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner_module(monkeypatch)
    receipt_dir = tmp_path / "receipts"
    monkeypatch.setattr(module, "RECEIPT_DIR", receipt_dir)
    executed: list[list[str]] = []

    real_run = subprocess.run

    def fake_run(argv, **kwargs):  # type: ignore[no-untyped-def]
        if list(argv)[:1] == ["mvn"]:
            executed.append(list(argv))
            return _Completed("Tests run: 3, Failures: 0, Errors: 0, Skipped: 0\n")
        return real_run(argv, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        module.receipt_mod,
        "observed_class_executions",
        lambda report_dirs, classes, *, not_before: (
            {
                name: {
                    "tests": 1,
                    "failures": 0,
                    "errors": 0,
                    "skipped": 0,
                    "report": f"{name}.xml",
                }
                for name in classes
            },
            (),
        ),
    )

    document = module.run_native_suite("xmage", "direct", runner=_clean_identity())

    assert executed, "the suite command must actually be invoked"
    command = executed[0]
    assert command[:2] == ["mvn", "-o"]
    assert (
        "-Dtest=" + ",".join(module.NATIVE_SUITE_BINDING["xmage"]["classes"]["direct"]) in command
    )
    assert document["returncode"] == 0
    assert document["tests"] == 3
    assert document["passed"] == 3
    assert document["classes"] == module.NATIVE_SUITE_BINDING["xmage"]["classes"]["direct"]
    runner_identity = _clean_identity()
    assert document["executed_commit"] == runner_identity.commit
    assert document["candidate_commit"] == module.canonical_xmage_engine_pin()
    # build_identity is a JSON document on the receipt, whatever shape the
    # binding declared, and it must name the lane that executed.
    declared = json.loads(document["build_identity"])
    assert declared["lane"] == "maven-surefire"
    persisted = receipt_dir / "native-xmage-direct.json"
    assert persisted.is_file()
    on_disk = json.loads(persisted.read_text(encoding="utf-8"))
    assert on_disk["receipt_digest"] == document["receipt_digest"]
    # The receipt must load under the fail-closed loader.
    assert receipt_mod.load_native_receipt(persisted)["group"] == "direct"


def test_run_native_suite_receipt_records_the_failure_tail_without_credit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner_module(monkeypatch)
    monkeypatch.setattr(module, "RECEIPT_DIR", tmp_path / "receipts")
    real_run = subprocess.run

    def fake_run(argv, **kwargs):  # type: ignore[no-untyped-def]
        if list(argv)[:1] == ["mvn"]:
            return _Completed("Tests run: 2, Failures: 1, Errors: 0, Skipped: 0\n", returncode=1)
        return real_run(argv, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        module.receipt_mod,
        "observed_class_executions",
        lambda report_dirs, classes, *, not_before: (
            {name: {"tests": 1, "failures": 1, "errors": 0, "skipped": 0} for name in classes},
            tuple(classes),
        ),
    )
    document = module.run_native_suite("xmage", "direct", runner=_clean_identity())
    assert document["returncode"] == 1
    persisted = tmp_path / "receipts" / "native-xmage-direct.json"
    with pytest.raises(receipt_mod.ReceiptError):
        receipt_mod.load_native_receipt(persisted)


def test_binding_declares_build_identity_that_the_runner_can_consume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _runner_module(monkeypatch)
    for candidate in ("xmage", "forge"):
        declared = module.NATIVE_SUITE_BINDING[candidate].get("build_identity")
        assert isinstance(declared, str)
        json.loads(declared)  # a JSON object, as the receipt contract requires


def test_native_suite_argv_is_a_list_not_a_shell_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No shell/string behaviour may silently change which tests run."""
    module = _runner_module(monkeypatch)
    for candidate in ("xmage", "forge"):
        argv = module.NATIVE_SUITE_BINDING[candidate]["argv"]
        assert isinstance(argv, list)
        assert all(isinstance(part, str) for part in argv)
        assert any("{tests}" in part for part in argv)
    assert "shell=True" not in RUNNER.read_text(encoding="utf-8")
