"""B10 (#491): the broad secret scan is pinned, fail-closed and narrowly excluded.

The live scan and its red controls run in the required ``security`` job
(``scripts/run_broad_secret_scan.py``). These tests keep its definition honest:
the pin, the exclusion shape, the workflow wiring and the separate project
sentinel.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tomllib
from functools import cache
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "run_broad_secret_scan.py"
CONFIG = REPO / ".gitleaks.toml"


@cache
def _scanner():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("b10_broad_secret_scan", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@cache
def _config() -> dict:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))


def _security_steps() -> list[dict]:
    workflow = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    return workflow["jobs"]["security"]["steps"]


def test_the_scanner_is_pinned_by_version_and_digest() -> None:
    scanner = _scanner()
    assert re.fullmatch(r"\d+\.\d+\.\d+", scanner.GITLEAKS_VERSION)
    assert re.fullmatch(r"[0-9a-f]{64}", scanner.GITLEAKS_SHA256)
    assert scanner.GITLEAKS_VERSION in scanner.GITLEAKS_URL
    assert scanner.GITLEAKS_URL.startswith("https://github.com/gitleaks/gitleaks/releases/")


def test_the_upstream_rule_set_applies() -> None:
    assert _config()["extend"] == {"useDefault": True}
    # A top-level allowlist exempts whole files whatever its condition.
    assert "allowlists" not in _config()
    assert "allowlist" not in _config()


def test_every_exclusion_names_one_rule_one_file_one_value_and_a_reason() -> None:
    rules = _config().get("rules", [])
    assert rules, "the configuration is expected to carry its two redaction fixtures"
    for rule in rules:
        # A rule entry only attaches exclusions; it never redefines the upstream rule.
        assert set(rule) == {"id", "allowlists"}, rule
        for entry in rule["allowlists"]:
            assert set(entry) == {"description", "condition", "paths", "regexes"}, entry
            assert entry["condition"] == "AND"
            assert len(entry["description"].split()) >= 8
            assert len(entry["paths"]) == 1 and len(entry["regexes"]) == 1
            assert re.fullmatch(r"\^[\w/.\\-]+\$", entry["paths"][0]), entry["paths"][0]
            assert re.fullmatch(r"\^[\w-]+\$", entry["regexes"][0]), entry["regexes"][0]


def test_no_exclusion_is_stale() -> None:
    """Each excluded value still occurs in its file; otherwise the entry must go."""
    for exclusion in _scanner().exclusions(CONFIG):
        text = (REPO / exclusion["path"]).read_text(encoding="utf-8")
        assert exclusion["value"] in text, exclusion


def test_red_controls_are_deterministic_and_never_committed() -> None:
    scanner = _scanner()
    controls = scanner.red_controls()
    assert controls == scanner.red_controls()
    assert len({control["rule"] for control in controls}) >= 6
    tracked = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z"], capture_output=True, check=True
    ).stdout.decode("utf-8")
    secrets = [re.search(r'"([^"]+)"|= (\S+)', control["content"]) for control in controls]
    values = [match.group(1) or match.group(2) for match in secrets if match]
    for relative in filter(None, tracked.split("\0")):
        path = REPO / relative
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        data = path.read_bytes()
        for value in values:
            assert value.encode() not in data, f"a generated red control is committed in {relative}"


def test_the_required_security_job_runs_the_scan_fail_closed() -> None:
    steps = _security_steps()
    scan = [step for step in steps if "run_broad_secret_scan.py" in (step.get("run") or "")]
    assert len(scan) == 1
    step = scan[0]
    assert "--install-dir" in step["run"]
    assert "|| true" not in step["run"]
    assert "continue-on-error" not in step
    assert step.get("if") == "${{ success() || failure() }}"
    upload = steps[-1]
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["with"]["path"] == "artifacts/security/"


def test_the_project_sentinel_is_retained_as_a_separate_signal() -> None:
    workflow = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    sentinel = [
        step
        for step in workflow["jobs"]["quality"]["steps"]
        if step.get("name") == "Secret-pattern scan"
    ]
    assert len(sentinel) == 1
    assert "[s]k-[A-Za-z0-9_-]{20,}" in sentinel[0]["run"]
    assert "[O]PENAI_API_KEY=" in sentinel[0]["run"]


@pytest.mark.parametrize("exit_code", [1, 2])
def test_a_scanner_failure_is_not_run_never_pass(tmp_path, exit_code) -> None:
    scanner = _scanner()
    fake = tmp_path / "gitleaks"
    fake.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
    fake.chmod(0o755)
    with pytest.raises(scanner.ScannerError):
        scanner.scan(fake, tmp_path, CONFIG)
