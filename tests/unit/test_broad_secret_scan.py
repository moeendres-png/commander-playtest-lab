"""B10 (#491): the broad secret scan is pinned, fail-closed and narrowly excluded.

The live scan and its red controls run in the required ``security`` job
(``scripts/run_broad_secret_scan.py``). These tests keep its definition honest:
the pin, the exclusion shape, the workflow wiring and the separate project
sentinel.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import tarfile
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


def _fake_gitleaks(tmp_path: Path, report_body: str) -> Path:
    """A stand-in that reports the pinned version and writes ``report_body`` verbatim."""
    body = tmp_path / "report-body.json"
    body.write_text(report_body, encoding="utf-8")
    fake = tmp_path / "bin" / "gitleaks"
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = version ]; then echo {_scanner().GITLEAKS_VERSION}; exit 0; fi\n'
        'while [ "$#" -gt 0 ]; do\n'
        f'  if [ "$1" = --report-path ]; then cp "{body}" "$2"; fi\n'
        "  shift\n"
        "done\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def _summary(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


_ENTRY = {"RuleID": "generic-api-key", "File": "a.py", "StartLine": 1, "Fingerprint": "a.py:1"}


@pytest.mark.parametrize(
    "report_body",
    [
        '[{"RuleID": "generic-api-key", "File": ',  # truncated
        "not json at all",
        '{"RuleID": "generic-api-key"}',  # not a list
        "[42]",  # entry is not an object
        json.dumps([{k: v for k, v in _ENTRY.items() if k != "File"}]),  # missing field
        json.dumps([{**_ENTRY, "StartLine": "1"}]),  # wrong type
        json.dumps([{**_ENTRY, "StartLine": True}]),  # bool is not a line number
    ],
    ids=["truncated", "invalid", "not_a_list", "entry_not_object", "missing", "type", "bool"],
)
def test_a_malformed_report_is_a_scanner_failure(tmp_path, report_body) -> None:
    """Red control malformed_report_is_not_run: parsing never escapes as a traceback."""
    scanner = _scanner()
    fake = _fake_gitleaks(tmp_path, report_body)
    with pytest.raises(scanner.ScannerError, match="gitleaks report is malformed"):
        scanner.scan(fake, tmp_path, CONFIG)


def test_a_well_formed_report_parses() -> None:
    scanner = _scanner()
    assert scanner.parse_finding(0, _ENTRY) == {
        "rule": "generic-api-key",
        "file": "a.py",
        "line": 1,
        "fingerprint": "a.py:1",
    }


def test_a_malformed_report_writes_not_run_over_a_stale_pass(tmp_path) -> None:
    """End to end: exit 2 and a NOT_RUN summary replace an earlier PASS summary."""
    scanner = _scanner()
    fake = _fake_gitleaks(tmp_path, '[{"RuleID": ')
    report = tmp_path / "out" / "summary.json"
    report.parent.mkdir()
    report.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    assert scanner.main(["--gitleaks", str(fake), "--report", str(report)]) == 2
    summary = _summary(report)
    assert summary["status"] == "NOT_RUN"
    assert "gitleaks report is malformed" in summary["error"]


def test_a_stale_summary_is_removed_before_the_scanner_runs(tmp_path, monkeypatch) -> None:
    """Red control stale_summary_removed: an interrupted run leaves no earlier PASS behind."""
    scanner = _scanner()
    report = tmp_path / "summary.json"
    report.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")

    def interrupted(*_args):  # type: ignore[no-untyped-def]
        raise KeyboardInterrupt

    monkeypatch.setattr(scanner, "resolve_scanner", interrupted)
    with pytest.raises(KeyboardInterrupt):
        scanner.main(["--gitleaks", str(tmp_path / "gitleaks"), "--report", str(report)])
    assert not report.exists()


def _clean_run(scanner, monkeypatch, *, dirty: bool = False) -> None:  # type: ignore[no-untyped-def]
    """Controls and scan pass; only the scanner source and the candidate state vary."""
    monkeypatch.setattr(
        scanner,
        "run_controls",
        lambda *_: [{"control": "clean_tree", "observed_rules": [], "status": "PASS"}],
    )
    monkeypatch.setattr(scanner, "scan", lambda *_: [])
    monkeypatch.setattr(
        scanner,
        "candidate_identity",
        lambda _root: {
            "commit": "c" * 40,
            "tree": "t" * 40,
            "dirty": dirty,
            "dirty_paths": ["src/x.py"] if dirty else [],
        },
    )
    monkeypatch.setattr(
        scanner,
        "materialize_tracked",
        lambda _root, _dest: [("b.py", "2" * 64), ("a.py", "1" * 64)],
    )


def test_an_external_binary_is_recorded_by_its_own_digest_and_never_passes(
    tmp_path, monkeypatch
) -> None:
    """Red control external_scanner_unverified: no archive verification is claimed."""
    scanner = _scanner()
    _clean_run(scanner, monkeypatch)
    fake = _fake_gitleaks(tmp_path, "[]")
    report = tmp_path / "summary.json"
    assert scanner.main(["--gitleaks", str(fake), "--report", str(report)]) == 1
    summary = _summary(report)
    assert summary["source_mode"] == "external_unverified"
    assert summary["scanner_archive_sha256"] is None
    assert summary["scanner_binary_sha256"] == hashlib.sha256(fake.read_bytes()).hexdigest()
    assert summary["scanner_binary_sha256"] != scanner.GITLEAKS_BINARY_SHA256
    assert summary["blockers"] == ["unverified_scanner"]
    assert summary["status"] == "FAIL"


def test_a_supplied_binary_with_the_pinned_digest_is_verified(tmp_path, monkeypatch) -> None:
    scanner = _scanner()
    _clean_run(scanner, monkeypatch)
    fake = _fake_gitleaks(tmp_path, "[]")
    digest = hashlib.sha256(fake.read_bytes()).hexdigest()
    monkeypatch.setattr(scanner, "GITLEAKS_BINARY_SHA256", digest)
    report = tmp_path / "summary.json"
    assert scanner.main(["--gitleaks", str(fake), "--report", str(report)]) == 0
    summary = _summary(report)
    assert summary["source_mode"] == "pinned_binary_verified"
    assert summary["scanner_archive_sha256"] is None
    assert summary["status"] == "PASS"


def test_the_installed_archive_is_recorded_as_verified(tmp_path, monkeypatch) -> None:
    scanner = _scanner()
    _clean_run(scanner, monkeypatch)
    fake = _fake_gitleaks(tmp_path, "[]")
    monkeypatch.setattr(scanner, "install", lambda _dest: fake)
    report = tmp_path / "summary.json"
    assert scanner.main(["--install-dir", str(tmp_path / "i"), "--report", str(report)]) == 0
    summary = _summary(report)
    assert summary["source_mode"] == "pinned_archive_verified"
    assert summary["scanner_archive_sha256"] == scanner.GITLEAKS_SHA256
    assert summary["scanner_binary_sha256"] == hashlib.sha256(fake.read_bytes()).hexdigest()


def _archive(payload: bytes) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        info = tarfile.TarInfo("gitleaks")
        info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def test_install_rejects_a_binary_that_is_not_the_pinned_member(tmp_path, monkeypatch) -> None:
    """The archive digest alone is not enough: the extracted binary is pinned too."""
    scanner = _scanner()
    archive = _archive(b"#!/bin/sh\necho tampered\n")

    class _Response(io.BytesIO):
        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *_exc):  # type: ignore[no-untyped-def]
            return False

    monkeypatch.setattr(scanner.urllib.request, "urlopen", lambda *_a, **_k: _Response(archive))
    monkeypatch.setattr(scanner, "GITLEAKS_SHA256", hashlib.sha256(archive).hexdigest())
    with pytest.raises(scanner.ScannerError, match="gitleaks binary digest"):
        scanner.install(tmp_path / "install")
    assert not (tmp_path / "install" / "gitleaks").exists()


def test_the_summary_binds_to_commit_tree_and_scanned_manifest(tmp_path, monkeypatch) -> None:
    scanner = _scanner()
    _clean_run(scanner, monkeypatch)
    fake = _fake_gitleaks(tmp_path, "[]")
    monkeypatch.setattr(scanner, "install", lambda _dest: fake)
    report = tmp_path / "summary.json"
    assert scanner.main(["--install-dir", str(tmp_path / "i"), "--report", str(report)]) == 0
    candidate = _summary(report)["candidate"]
    expected = hashlib.sha256(f"{'1' * 64}  a.py\n{'2' * 64}  b.py\n".encode()).hexdigest()
    assert candidate == {
        "commit": "c" * 40,
        "tree": "t" * 40,
        "dirty": False,
        "dirty_paths": [],
        "scanned_files": 2,
        "manifest_sha256": expected,
    }


def test_a_dirty_tree_never_passes(tmp_path, monkeypatch) -> None:
    """Red control dirty_tree_blocks_pass: scanned bytes that are not HEAD bind to nothing."""
    scanner = _scanner()
    _clean_run(scanner, monkeypatch, dirty=True)
    fake = _fake_gitleaks(tmp_path, "[]")
    monkeypatch.setattr(scanner, "install", lambda _dest: fake)
    report = tmp_path / "summary.json"
    assert scanner.main(["--install-dir", str(tmp_path / "i"), "--report", str(report)]) == 1
    summary = _summary(report)
    assert summary["candidate"]["dirty"] is True
    assert summary["blockers"] == ["dirty_tree"]
    assert summary["status"] == "FAIL"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=True, text=True
    ).stdout.strip()


def test_candidate_identity_and_manifest_follow_the_real_checkout(tmp_path) -> None:
    scanner = _scanner()
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.py").write_text("A = 1\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("not scanned\n", encoding="utf-8")
    _git(repo, "add", "a.py")
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "commit",
        "-q",
        "-m",
        "init",
    )
    clean = scanner.candidate_identity(repo)
    assert clean["commit"] == _git(repo, "rev-parse", "HEAD")
    assert clean["tree"] == _git(repo, "rev-parse", "HEAD^{tree}")
    assert clean["dirty"] is False  # untracked files are never scanned
    manifest = scanner.materialize_tracked(repo, tmp_path / "copy")
    assert manifest == [("a.py", hashlib.sha256(b"A = 1\n").hexdigest())]
    (repo / "a.py").write_text("A = 2\n", encoding="utf-8")
    dirty = scanner.candidate_identity(repo)
    assert dirty["dirty"] is True and dirty["dirty_paths"] == ["a.py"]
    assert scanner.manifest_sha256(scanner.materialize_tracked(repo, tmp_path / "c2")) != (
        scanner.manifest_sha256(manifest)
    )
