import hashlib
import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/production-qualification.yml"
HARNESS = ROOT / "qualification/harness.py"
MANIFEST = ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json"
SOURCE_LOCK = ROOT / "qualification/WS17_SOURCE_LOCK.json"


def test_exact_main_job_installs_declared_runtime_before_harness_import():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "jsonschema>=4.23,<5" in project["project"]["optional-dependencies"]["dev"]
    assert Draft202012Validator is not None

    spec = importlib.util.spec_from_file_location("ws17r_harness_import_probe", HARNESS)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    text = WORKFLOW.read_text(encoding="utf-8")
    exact_main = text.split("\n  exact-main-admission:\n", 1)[1]
    install = "python -m pip install -e '.[dev]'"
    first_harness_call = "python qualification/harness.py"

    assert install in exact_main
    assert exact_main.index(install) < exact_main.index(first_harness_call)
    assert "Verify qualification runtime imports" in exact_main
    assert "from jsonschema import Draft202012Validator" in exact_main
    assert 'runpy.run_path("qualification/harness.py"' in exact_main


def test_provider_absence_end_to_end_generates_fail_not_run_hashes_and_artifacts(tmp_path):
    evidence_dir = tmp_path / "qualification/evidence/runtime"
    aggregate_dir = tmp_path / "qualification/aggregate/runtime"
    evidence_dir.mkdir(parents=True)
    aggregate_dir.mkdir(parents=True)

    common_results = evidence_dir / "COMMON_RESULTS.json"
    production_json = aggregate_dir / "PRODUCTION_ADMISSION.json"
    production_md = aggregate_dir / "PRODUCTION_ADMISSION.md"
    sha = "a" * 40

    subprocess.run(
        [
            sys.executable,
            str(HARNESS),
            "run",
            "--candidate",
            "NO_PRODUCTION_PROVIDER_SELECTED",
            "--source-lock",
            str(SOURCE_LOCK),
            "--manifest",
            str(MANIFEST),
            "--output",
            str(common_results),
        ],
        check=True,
    )

    common = json.loads(common_results.read_text(encoding="utf-8"))
    assert common["fixture_results"]
    assert all(result["verdict"] == "NOT_RUN" for result in common["fixture_results"])

    subprocess.run(
        [
            sys.executable,
            str(HARNESS),
            "aggregate",
            "--manifest",
            str(MANIFEST),
            "--results",
            str(common_results),
            "--admitted-main-sha",
            sha,
            "--actual-sha",
            sha,
            "--output",
            str(production_json),
            "--md-output",
            str(production_md),
        ],
        check=True,
    )

    admission = json.loads(production_json.read_text(encoding="utf-8"))
    assert admission["production_admission"] == "FAIL"
    assert any(result["verdict"] == "NOT_RUN" for result in admission["blocking_results"])

    expected_artifacts = {common_results, production_json, production_md}
    assert all(path.is_file() and path.stat().st_size > 0 for path in expected_artifacts)

    checksum_file = aggregate_dir / "SHA256SUMS"
    lines = []
    for path in sorted(expected_artifacts):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = path.relative_to(tmp_path)
        lines.append(f"{digest}  {relative}")
    checksum_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    recorded = {}
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        recorded[relative] = digest

    assert "qualification/aggregate/runtime/SHA256SUMS" not in recorded
    assert set(recorded) == {
        "qualification/evidence/runtime/COMMON_RESULTS.json",
        "qualification/aggregate/runtime/PRODUCTION_ADMISSION.json",
        "qualification/aggregate/runtime/PRODUCTION_ADMISSION.md",
    }
    for relative, digest in recorded.items():
        assert hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest() == digest


def test_exact_main_hash_step_excludes_checksum_manifest_itself():
    text = WORKFLOW.read_text(encoding="utf-8")
    exact_main = text.split("\n  exact-main-admission:\n", 1)[1]
    hash_step = exact_main.split("- name: Hash runtime evidence", 1)[1]
    assert "! -path 'qualification/aggregate/runtime/SHA256SUMS'" in hash_step
    assert "xargs -0 sha256sum > qualification/aggregate/runtime/SHA256SUMS" in hash_step
