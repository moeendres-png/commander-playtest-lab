"""B10 (#491): the broad secret scan is pinned, fail-closed and narrowly excluded.

The live scan and its red controls run in the required ``security`` job
(``scripts/run_broad_secret_scan.py``). These tests keep its definition honest:
the pin, the exclusion shape, the workflow wiring and the separate project
sentinel.
"""

from __future__ import annotations

import importlib.util
import json
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
    assert re.fullmatch(r"[0-9a-f]{64}", scanner.GITLEAKS_BINARY_SHA256)
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
            # Only literal path characters and escaped dots: exclusions() un-escapes
            # exactly these, so the value-scope control lands on the real file.
            assert re.fullmatch(r"\^(?:[A-Za-z0-9_/-]|\\\.)+\$", entry["paths"][0]), entry["paths"]
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


def test_every_gitleaks_suppression_channel_is_closed() -> None:
    flags = _scanner().SCAN_FLAGS
    assert "--ignore-gitleaks-allow" in flags
    assert not any(flag.startswith(("--baseline", "-b", "--gitleaks-ignore")) for flag in flags)
    controls = {case["control"] for case in _scanner().red_controls()}
    assert controls  # the run adds inline-allow and suppression-file controls on top


def test_no_suppression_file_or_unanchored_allowlist_path_is_tracked() -> None:
    tracked = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z"], capture_output=True, check=True
    ).stdout.decode("utf-8")
    paths = [path for path in tracked.split("\0") if path]
    assert not [path for path in paths if path.rsplit("/", 1)[-1] == ".gitleaksignore"]
    assert [path for path in paths if "gitleaks.toml" in path] == [".gitleaks.toml"]


def _fake(tmp_path: Path, body: str) -> Path:
    fake = tmp_path / "gitleaks"
    fake.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    fake.chmod(0o755)
    return fake


@pytest.mark.parametrize("report", ["{not json", '{"a": 1}', '[{"RuleID": "x"}]'])
def test_a_malformed_report_is_not_run(tmp_path, report) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    fake = _fake(
        tmp_path,
        'while [ "$1" != "--report-path" ]; do shift; done\n'
        f"printf '%s' '{report}' > \"$2\"\nexit 0\n",
    )
    with pytest.raises(_scanner().ScannerError, match="malformed"):
        _scanner().scan(fake, tree, CONFIG)


def test_a_tree_with_a_suppression_file_is_refused(tmp_path) -> None:
    (tmp_path / ".gitleaksignore").write_text("a.py:github-pat:1\n", encoding="utf-8")
    with pytest.raises(_scanner().ScannerError, match="refusing"):
        _scanner().scan(tmp_path / "gitleaks", tmp_path, CONFIG)


def test_a_supplied_binary_must_be_the_pinned_binary(tmp_path) -> None:
    fake = _fake(tmp_path, "echo 8.28.0\n")
    with pytest.raises(_scanner().ScannerError, match="binary digest"):
        _scanner().verify_scanner(fake)


def test_main_reports_not_run_with_source_identity(tmp_path, monkeypatch, capsys) -> None:
    fake = _fake(tmp_path, "echo 8.28.0\n")
    report = tmp_path / "report.json"
    monkeypatch.setattr(
        sys, "argv", ["run_broad_secret_scan.py", "--gitleaks", str(fake), "--report", str(report)]
    )
    assert _scanner().main() == 2
    summary = json.loads(report.read_text(encoding="utf-8"))
    assert summary["status"] == "NOT_RUN"
    assert summary["scanner_source"] == "supplied_binary"
    assert re.fullmatch(r"[0-9a-f]{40}", summary["source"]["head"])
    assert "binary digest" in summary["error"]


def test_materialization_reports_suppression_paths_and_binds_a_manifest(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    (repo / ".gitleaksignore").write_text("a.py:generic-api-key:1\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "notes.gitleaks.toml.md").write_text("n\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    out = tmp_path / "out"
    first = _scanner().materialize_tracked(repo, out)
    assert first["files"] == 1
    assert first["suppression_paths"] == [".gitleaksignore", "docs/notes.gitleaks.toml.md"]
    assert not (out / ".gitleaksignore").exists()
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
    second = _scanner().materialize_tracked(repo, tmp_path / "out2")
    assert second["manifest_sha256"] != first["manifest_sha256"]


def test_out_of_range_report_line_is_a_scanner_error() -> None:
    with pytest.raises(_scanner().ScannerError, match="malformed"):
        _scanner()._parse_report('[{"RuleID":"x","File":"x","StartLine":1e400,"Fingerprint":"x"}]')


def test_tracked_symlink_cannot_receive_pass_by_being_skipped(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "regular.txt").write_text("clean\n")
    (repo / "link.txt").symlink_to("unresolved-target")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    with pytest.raises(_scanner().ScannerError, match="symlink"):
        _scanner().materialize_tracked(repo, tmp_path / "scan")


@pytest.mark.parametrize(
    "content",
    [
        "[invalid",
        'rules = ["wrong"]',
        '[[rules]]\nid = "x"\n[[rules.allowlists]]\npaths = []\nregexes = []\n',
    ],
)
def test_invalid_configuration_is_a_scanner_error(tmp_path, content) -> None:
    config = tmp_path / "config.toml"
    config.write_text(content)
    with pytest.raises(_scanner().ScannerError, match="configuration"):
        _scanner().exclusions(config)


def test_main_writes_not_run_for_invalid_configuration(tmp_path, monkeypatch) -> None:
    scanner = _scanner()
    config = tmp_path / "config.toml"
    config.write_text("[invalid")
    report = tmp_path / "evidence.json"
    report.write_text('{"status":"PASS"}')
    monkeypatch.setattr(scanner, "CONFIG", config)
    monkeypatch.setattr(scanner, "verify_scanner", lambda _binary: "0" * 64)
    monkeypatch.setattr(
        sys, "argv", ["scan", "--gitleaks", str(tmp_path / "scanner"), "--report", str(report)]
    )
    assert scanner.main() == 2
    document = json.loads(report.read_text())
    assert document["status"] == "NOT_RUN"
    assert "configuration" in document["error"]


@pytest.mark.parametrize("kind", ["missing", "directory", "unreadable"])
def test_unavailable_config_overwrites_stale_pass(tmp_path, monkeypatch, kind) -> None:
    scanner = _scanner()
    config = tmp_path / "unavailable.toml"
    if kind == "directory":
        config.mkdir()
    elif kind == "unreadable":
        config.write_text("[extend]\nuseDefault = true\n")
        original = scanner._sha256_file

        def unreadable(path):
            if path == config:
                raise PermissionError("configuration is unreadable")
            return original(path)

        monkeypatch.setattr(scanner, "_sha256_file", unreadable)
    report = tmp_path / "evidence.json"
    report.write_text('{"status":"PASS"}')
    monkeypatch.setattr(scanner, "CONFIG", config)
    monkeypatch.setattr(
        sys, "argv", ["scan", "--gitleaks", str(tmp_path / "scanner"), "--report", str(report)]
    )
    assert scanner.main() == 2
    document = json.loads(report.read_text())
    assert document["status"] == "NOT_RUN"
    assert "error" in document
    assert "config_sha256" not in document
