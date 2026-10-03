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


def test_override_must_stay_inside_the_epochs_parent() -> None:
    """An epoch may only be selected under the runtime epochs parent.

    Anything else inside qualification/ would write evidence into a tracked
    research tree where it is neither attributable as a runtime epoch nor
    excluded from source dirtiness.
    """
    for outside in (
        "/etc",
        "src",
        "../outside",
        "docs",
        "qualification/manifests",
        "qualification/other-tree",
        f"qualification/{E.HISTORICAL_EPOCH_ID}",
    ):
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


def test_receipts_exclude_only_the_runtime_epoch_from_dirty_accounting() -> None:
    assert receipt_mod._is_run_output(
        "qualification/current-boundary-epochs/abc-123/receipts/native-xmage-direct.json"
    )
    assert receipt_mod._is_run_output("qualification/current-boundary-epochs/")
    # The historical epoch is a read-only predecessor now: a modification under
    # it must count as dirty source, not be hidden as run output.
    assert not receipt_mod._is_run_output(
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


def _assert_workflow_runtime_epoch(document: dict) -> None:
    import yaml

    # Trigger paths may name read-only historical test inputs. Execution and
    # upload paths must still resolve the current source-bound output epoch.
    text = yaml.safe_dump(document["jobs"])
    assert E.HISTORICAL_EPOCH_ID not in text, "historical epoch used as a runtime/upload target"
    assert E.EPOCH_ENV in text
    assert "evidence_epoch" in text


def test_pb03_workflow_consumes_the_resolved_epoch() -> None:
    import yaml

    _assert_workflow_runtime_epoch(yaml.safe_load(WORKFLOW.read_text()))


def test_historical_trigger_does_not_grant_historical_upload_credit() -> None:
    import yaml

    document = yaml.safe_load(WORKFLOW.read_text())
    triggers = document.get("on") or document.get(True)
    assert f"qualification/{E.HISTORICAL_EPOCH_ID}/**" in triggers["pull_request"]["paths"]
    _assert_workflow_runtime_epoch(document)
    upload = next(
        step
        for step in document["jobs"]["pb03-runtime"]["steps"]
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    )
    upload["with"]["path"] = f"qualification/{E.HISTORICAL_EPOCH_ID}/"
    with pytest.raises(AssertionError, match="runtime/upload"):
        _assert_workflow_runtime_epoch(document)


def _runner_script_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CURRENT_BOUNDARY_EVIDENCE_EPOCH", raising=False)
    spec = importlib.util.spec_from_file_location("cb_epoch_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fake_candidate_artifacts(directory: Path, candidate: str) -> dict[Path, bytes]:
    written: dict[Path, bytes] = {}
    for template in (
        "FULL107_{candidate}_RESULTS.json",
        "AF01_{candidate}.json",
        "AF03_{candidate}.json",
        "PLAYER_CARDINALITY_{candidate}.json",
        "RNG_REPLAY_{candidate}.json",
    ):
        path = directory / template.format(candidate=candidate)
        payload = json.dumps(
            {
                "schema_version": "test/1.0.0",
                "evidence_class": "FRESH_CURRENT_BOUNDARY_EXECUTION",
                "boundary": "FRESH_CURRENT_BOUNDARY_EXECUTION",
                "runtime_identity": {"engine_candidate_commit": "a" * 40},
                "rows": [
                    {
                        "fixture_id": "WS05-CMD-START-2",
                        "evidence_class": "FRESH_CURRENT_BOUNDARY_RUNTIME",
                    }
                ],
            },
            indent=1,
            sort_keys=True,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
        written[path] = path.read_bytes()
    return written


def test_unselected_candidate_column_is_carried_forward_with_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _runner_script_module(monkeypatch)
    source = tmp_path / "historical"
    target = tmp_path / "runtime"
    before = _fake_candidate_artifacts(source, "FORGE")
    (source / "FULL107_XMAGE_RESULTS.json").write_text("{}", encoding="utf-8")

    carried = runner.carry_forward_unselected_candidates(
        ["xmage"], source_epoch=source, target_epoch=target
    )
    assert carried == ["forge"]
    for path, original in before.items():
        copied = target / path.name
        assert copied.is_file(), path.name
        document = json.loads(copied.read_text(encoding="utf-8"))
        assert document["evidence_class"] == "CARRIED_FORWARD_NOT_REEXECUTED"
        assert document["boundary"] == "CARRIED_FORWARD_NOT_REEXECUTED"
        assert document["rows"][0]["evidence_class"] == "CARRIED_FORWARD_NOT_REEXECUTED"
        assert document["carried_forward"]["source_epoch"] == str(source)
        assert document["carried_forward"]["source_epoch_id"] == source.name
        # The historical source is read, never rewritten.
        assert path.read_bytes() == original
    # The selected candidate is never carried forward, and historical receipts
    # are never copied into the runtime epoch (that would credit old executions).
    assert not (target / "FULL107_XMAGE_RESULTS.json").exists()
    assert not (target / "receipts").exists()


def test_existing_target_column_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _runner_script_module(monkeypatch)
    source = tmp_path / "historical"
    target = tmp_path / "runtime"
    _fake_candidate_artifacts(source, "FORGE")
    target.mkdir()
    fresh = target / "FULL107_FORGE_RESULTS.json"
    fresh.write_text('{"evidence_class": "FRESH_CURRENT_BOUNDARY_EXECUTION"}\n', encoding="utf-8")
    runner.carry_forward_unselected_candidates(["xmage"], source_epoch=source, target_epoch=target)
    assert json.loads(fresh.read_text(encoding="utf-8"))["evidence_class"] == (
        "FRESH_CURRENT_BOUNDARY_EXECUTION"
    )


def test_assembler_derives_the_boundary_from_column_provenance() -> None:
    source = ASSEMBLER.read_text(encoding="utf-8")
    assert 'data["column_provenance"]["class"]' in source
    assert '"column_provenance": data["column_provenance"]' in source


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
