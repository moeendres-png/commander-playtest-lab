"""B1: current-boundary evidence writes to a source-bound successor epoch.

``qualification/final-current-boundary-20260927`` is the historical WSR22
current-boundary evidence epoch. The runner and assembler wrote into it in place,
so every execution replaced the historical bytes and the same path meant both
"the frozen historical evidence" and "the latest run". These tests pin the
successor-epoch contract:

* the default runtime epoch is derived from the producing source (commit + tree)
  and lives under ``qualification/current-boundary-epochs/``;
* the historical epoch is never a legal write target, explicit or default;
* an explicit override must stay inside this repository's ``qualification/`` tree;
* the epoch identity is machine-readable and a foreign producing source refuses
  to overwrite it, and the assembler refuses to credit a foreign-produced epoch;
* runner and assembler resolve the same epoch through one function;
* run outputs under the new epoch are excluded from the runner's dirty accounting.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import evidence_epoch as E
from commander_lab.qualification.current_boundary import receipts as receipt_mod

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "run_current_boundary_qualification.py"
ASSEMBLER = REPO / "scripts" / "assemble_current_boundary_evidence.py"
WORKFLOW = REPO / ".github" / "workflows" / "pb03-runtime-qualification.yml"


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(REPO), capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def _script_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_default_epoch_is_bound_to_the_producing_source() -> None:
    root = E.epoch_root(REPO)
    commit = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    assert root.parent == REPO / "qualification" / E.EPOCH_PARENT
    assert root.name == f"{commit[:12]}-{tree[:12]}"
    assert root != REPO / "qualification" / E.HISTORICAL_EPOCH_ID


def test_historical_epoch_is_never_a_legal_target() -> None:
    with pytest.raises(E.EvidenceEpochError):
        E.epoch_root(REPO, environ={E.EPOCH_ENV: f"qualification/{E.HISTORICAL_EPOCH_ID}"})
    with pytest.raises(E.EvidenceEpochError):
        E.epoch_root(
            REPO,
            environ={E.EPOCH_ENV: f"qualification/{E.HISTORICAL_EPOCH_ID}/receipts"},
        )


def test_override_must_stay_inside_qualification() -> None:
    for outside in ("/etc", "src", "../outside", "docs"):
        with pytest.raises(E.EvidenceEpochError):
            E.epoch_root(REPO, environ={E.EPOCH_ENV: outside})


def test_override_inside_qualification_is_honoured() -> None:
    relative = f"qualification/{E.EPOCH_PARENT}/explicit-test-epoch"
    assert E.epoch_root(REPO, environ={E.EPOCH_ENV: relative}) == REPO / relative


def test_epoch_identity_is_machine_readable_and_source_bound(tmp_path: Path) -> None:
    epoch = tmp_path / "epoch"
    document = E.ensure_epoch_identity(epoch, repo_root=REPO)
    assert document["schema_version"] == E.EPOCH_IDENTITY_SCHEMA
    assert document["producing_source"]["commit"] == _git("rev-parse", "HEAD")
    assert document["producing_source"]["tree"] == _git("rev-parse", "HEAD^{tree}")
    assert document["predecessor_epoch"] == f"qualification/{E.HISTORICAL_EPOCH_ID}"
    reloaded = E.load_epoch_identity(epoch)
    assert reloaded == document
    # Idempotent for the same source: the identity is written once.
    assert E.ensure_epoch_identity(epoch, repo_root=REPO) == document


def test_epoch_identity_refuses_a_foreign_producing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    epoch = tmp_path / "epoch"
    E.ensure_epoch_identity(epoch, repo_root=REPO)
    foreign = {
        "repository": "UNCONFIGURED",
        "commit": "1" * 40,
        "tree": "2" * 40,
        "branch": "foreign",
    }
    monkeypatch.setattr(E, "source_identity", lambda repo_root: dict(foreign))
    with pytest.raises(E.EvidenceEpochError, match="Refusing to overwrite"):
        E.ensure_epoch_identity(epoch, repo_root=REPO)
    with pytest.raises(E.EvidenceEpochError, match="different source"):
        E.require_epoch_identity(epoch, repo_root=REPO)


def test_require_epoch_identity_rejects_an_unattributed_epoch(tmp_path: Path) -> None:
    with pytest.raises(E.EvidenceEpochError, match="no epoch identity"):
        E.require_epoch_identity(tmp_path / "absent", repo_root=REPO)
    epoch = tmp_path / "epoch"
    E.ensure_epoch_identity(epoch, repo_root=REPO)
    assert E.require_epoch_identity(epoch, repo_root=REPO)["producing_source"]["commit"] == (
        _git("rev-parse", "HEAD")
    )


def test_malformed_epoch_identity_fails_closed(tmp_path: Path) -> None:
    epoch = tmp_path / "epoch"
    epoch.mkdir()
    path = epoch / E.EPOCH_IDENTITY_FILENAME
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(E.EvidenceEpochError):
        E.load_epoch_identity(epoch)
    path.write_text(json.dumps({"schema_version": "other/9.9.9"}), encoding="utf-8")
    with pytest.raises(E.EvidenceEpochError):
        E.load_epoch_identity(epoch)


def test_runner_and_assembler_resolve_the_same_epoch() -> None:
    runner = _script_module(RUNNER, "cb_runner_epoch_test")
    assembler = _script_module(ASSEMBLER, "cb_assembler_epoch_test")
    expected = E.epoch_root(REPO)
    assert expected == runner.OUT_DIR
    assert expected == assembler.OUT
    assert expected / "receipts" == runner.RECEIPT_DIR


def test_runner_records_the_epoch_in_its_runtime_identity() -> None:
    runner = _script_module(RUNNER, "cb_runner_epoch_identity_test")
    identity = runner.runtime_identity("xmage")
    epoch = identity["evidence_epoch"]
    assert epoch["epoch_id"] == E.epoch_root(REPO).name
    assert epoch["predecessor_epoch"] == f"qualification/{E.HISTORICAL_EPOCH_ID}"
    assert epoch["writes_historical_epoch"] is False


def test_receipts_exclude_the_runtime_epoch_from_dirty_accounting() -> None:
    assert receipt_mod._is_run_output(
        "qualification/current-boundary-epochs/abc-123/receipts/native-xmage-direct.json"
    )
    assert receipt_mod._is_run_output("qualification/current-boundary-epochs/")
    assert receipt_mod._is_run_output(
        f"qualification/{E.HISTORICAL_EPOCH_ID}/FULL107_XMAGE_RESULTS.json"
    )
    assert not receipt_mod._is_run_output("scripts/run_current_boundary_qualification.py")


def test_scripts_do_not_hard_code_the_historical_epoch() -> None:
    for script in (RUNNER, ASSEMBLER):
        source = script.read_text(encoding="utf-8")
        assert E.HISTORICAL_EPOCH_ID not in source, (
            f"{script.name} hard-codes the historical epoch path again; resolution must go "
            "through evidence_epoch"
        )


def test_pb03_workflow_consumes_the_resolved_epoch() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert E.HISTORICAL_EPOCH_ID not in text, (
        "the PB-03 workflow still points at the historical epoch; it must resolve the runtime "
        "epoch so CI uploads what the run produced"
    )
    assert E.EPOCH_ENV in text, (
        "the PB-03 workflow must resolve the epoch through the shared function and export it "
        "under the environment variable the runner and assembler read"
    )
    assert "evidence_epoch" in text


def test_runner_writes_only_the_successor_epoch_and_never_the_historical_tree() -> None:
    """A real runner process writes its output into the resolved successor epoch.

    The write target is exercised through the runner's own ``write()`` on an
    explicitly selected epoch, and the historical tree is checked with
    ``git status`` before and after: a run must not touch it.
    """
    import os
    import shutil

    epoch_rel = f"qualification/{E.EPOCH_PARENT}/pytest-epoch-probe"
    epoch_dir = REPO / epoch_rel
    historical_rel = f"qualification/{E.HISTORICAL_EPOCH_ID}"

    def historical_status() -> str:
        completed = subprocess.run(
            ["git", "status", "--porcelain", "--", historical_rel],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout

    before = historical_status()
    code = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('epoch_probe_runner', r'{RUNNER}')\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules['epoch_probe_runner'] = module\n"
        "spec.loader.exec_module(module)\n"
        "module.bootstrap_evidence_epoch()\n"
        "module.write('EPOCH_PROBE.json', {'probe': True})\n"
        "print(module.OUT_DIR)\n"
    )
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"))
    env[E.EPOCH_ENV] = epoch_rel
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        assert completed.returncode == 0, completed.stderr[-2000:]
        assert completed.stdout.strip().splitlines()[-1] == str(epoch_dir)
        assert (epoch_dir / "EPOCH_PROBE.json").is_file()
        identity = json.loads((epoch_dir / E.EPOCH_IDENTITY_FILENAME).read_text(encoding="utf-8"))
        assert identity["producing_source"]["commit"] == _git("rev-parse", "HEAD")
        assert identity["epoch_id"] == "pytest-epoch-probe"
        assert historical_status() == before == ""
        assert not (REPO / historical_rel / "EPOCH_PROBE.json").exists()
    finally:
        shutil.rmtree(epoch_dir, ignore_errors=True)
