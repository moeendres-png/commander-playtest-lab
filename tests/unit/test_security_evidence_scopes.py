"""B11 scope controls: artifact presence alone never earns security PASS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from scripts import security_evidence as evidence


def fixture(tmp_path: Path) -> dict:
    record = {"scopes": {}, "dependency_audit_exclusion": {"name": "project"}}
    for scope, packages in (
        ("ci-tooling", {"project": "1", "audit-tool": "2", "runtime": "3"}),
        ("runtime-product", {"project": "1", "runtime": "3"}),
    ):
        record["scopes"][scope] = {"packages": packages}
        directory = tmp_path / scope
        directory.mkdir()
        (directory / "inventory.json").write_text(json.dumps({"packages": packages}))
        (directory / "requirements.txt").write_text("runtime==3\n")
        (directory / "sbom.cdx.json").write_text(
            json.dumps({"components": [{"name": n, "version": v} for n, v in packages.items()]})
        )
        (directory / "licenses.json").write_text(
            json.dumps([{"Name": n, "Version": v} for n, v in packages.items()])
        )
        (directory / "dependency-audit.json").write_text(
            json.dumps(
                {
                    "dependencies": [
                        {"name": n, "version": v, "vulns": []}
                        for n, v in packages.items()
                        if n != "project"
                    ]
                }
            )
        )
    return record


def test_separate_complete_scopes_pass(tmp_path):
    record = fixture(tmp_path)
    artifacts = evidence.validate_artifacts(tmp_path, record)
    assert len(artifacts) == 10
    assert {a["scope"] for a in artifacts} == set(evidence.SCOPES)
    assert all(len(a["sha256"]) == 64 for a in artifacts)


@pytest.mark.parametrize(
    "name",
    [
        "sbom.cdx.json",
        "licenses.json",
        "dependency-audit.json",
        "inventory.json",
        "requirements.txt",
    ],
)
def test_missing_product_artifact_refused(tmp_path, name):
    record = fixture(tmp_path)
    (tmp_path / "runtime-product" / name).unlink()
    with pytest.raises(ValueError, match="regular file"):
        evidence.validate_artifacts(tmp_path, record)


def test_tooling_leak_into_product_sbom_refused(tmp_path):
    record = fixture(tmp_path)
    target = tmp_path / "runtime-product/sbom.cdx.json"
    data = json.loads(target.read_text())
    data["components"].append({"name": "audit-tool", "version": "2"})
    target.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="extra"):
        evidence.validate_artifacts(tmp_path, record)


def test_runtime_dependency_is_not_blacklisted_by_name():
    evidence.assert_inventory({"pip-audit": "2.10.1"}, {"pip-audit": "2.10.1"})


def test_missing_license_component_refused(tmp_path):
    record = fixture(tmp_path)
    (tmp_path / "runtime-product/licenses.json").write_text(
        json.dumps([{"Name": "project", "Version": "1"}])
    )
    with pytest.raises(ValueError, match="missing"):
        evidence.validate_artifacts(tmp_path, record)


@pytest.mark.parametrize(
    "changes", [{"version": "4"}, {"vulns": [{"id": "VULN"}]}, {"skip_reason": "no collection"}]
)
def test_bad_audit_refused(tmp_path, changes):
    record = fixture(tmp_path)
    target = tmp_path / "runtime-product/dependency-audit.json"
    data = json.loads(target.read_text())
    data["dependencies"][0].update(changes)
    target.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        evidence.validate_artifacts(tmp_path, record)


def test_normalized_duplicate_component_refused():
    with pytest.raises(ValueError, match="duplicate"):
        evidence.canonical_inventory(
            [{"name": "Some_Name", "version": "1"}, {"name": "some-name", "version": "1"}]
        )


def test_symlink_artifact_refused(tmp_path):
    record = fixture(tmp_path)
    target = tmp_path / "runtime-product/sbom.cdx.json"
    target.unlink()
    target.symlink_to(tmp_path / "ci-tooling/sbom.cdx.json")
    with pytest.raises(ValueError, match="regular file"):
        evidence.validate_artifacts(tmp_path, record)


def test_early_failure_is_persisted(tmp_path):
    args = argparse.Namespace(
        repo=tmp_path / "absent",
        out=tmp_path / "evidence",
        runtime=tmp_path / "runtime",
        wheel_dir=tmp_path / "wheel",
    )
    assert evidence.prepare(args) == 1
    record = json.loads((args.out / "SCOPES.json").read_text())
    assert record["status"] == "FAIL"
    assert record["scopes"] == {}
    assert "error" in record


def test_missing_step_is_not_run_and_not_pass(tmp_path, monkeypatch):
    record = fixture(tmp_path)
    record.update(schema=evidence.SCHEMA, status="PASS")
    evidence.write(tmp_path / "SCOPES.json", record)
    monkeypatch.setenv("B11_STEP_RESULTS", "{}")
    args = argparse.Namespace(
        out=tmp_path, repo=tmp_path, runtime=tmp_path / "runtime", wheel_dir=tmp_path / "wheel"
    )
    assert evidence.seal(args) == 1
    index = json.loads((tmp_path / "SECURITY_EVIDENCE_INDEX.json").read_text())
    assert index["status"] == "FAIL"
    assert set(index["steps"].values()) == {"NOT_RUN"}
    assert index["artifacts"] == []
