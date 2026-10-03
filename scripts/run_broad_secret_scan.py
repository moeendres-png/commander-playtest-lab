#!/usr/bin/env python3
"""B10 (#491): deterministic broad secret scan with the pinned gitleaks.

The project sentinel (the ``Secret-pattern scan`` step of the required
``quality`` job) stays a separate signal. This scan adds the full upstream
gitleaks rule set:

1. Install the pinned gitleaks release and verify the archive digest, the
   extracted binary digest and the reported version before it runs
   (``--install-dir``), or use ``--gitleaks``. A supplied binary is recorded
   by its own digest; one that is not the pinned binary is
   ``external_unverified`` and never yields PASS.
2. Red controls: representative secrets generated at run time (never stored in
   the repository) must each be found by their expected rule, an allowlisted
   value must still be found outside its own file, a different value must still
   be found inside an allowlisted file, and a clean tree must produce nothing.
   A scanner that finds nothing would otherwise pass every repository scan.
3. Scan exactly the git-tracked files of the checkout with ``.gitleaks.toml``.
   The summary binds the evidence to the candidate: HEAD commit and tree, the
   dirty state of the tracked files, and the digest of the scanned manifest
   (every scanned path with the digest of the bytes that were scanned).

Exit 0 only when every control behaves, the repository has no finding, the
tracked files are clean and the scanner is verified. Exit 1 otherwise, 2 when
the scanner cannot run or its report is malformed (NOT_RUN). The summary
carries rule, file, line and fingerprint only, never a secret value. A stale
summary is removed before anything runs.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import string
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".gitleaks.toml"
DEFAULT_REPORT = Path("artifacts/security/broad-secret-scan.json")
SCHEMA_VERSION = "b10.broad-secret-scan.v2"

GITLEAKS_VERSION = "8.28.0"
GITLEAKS_ARCHIVE = f"gitleaks_{GITLEAKS_VERSION}_linux_x64.tar.gz"
GITLEAKS_URL = (
    f"https://github.com/gitleaks/gitleaks/releases/download/v{GITLEAKS_VERSION}/{GITLEAKS_ARCHIVE}"
)
# From the release's gitleaks_8.28.0_checksums.txt.
GITLEAKS_SHA256 = "a65b5253807a68ac0cafa4414031fd740aeb55f54fb7e55f386acb52e6a840eb"
# The ``gitleaks`` member of that verified archive.
GITLEAKS_BINARY_SHA256 = "5fd1b3b0073269484d40078662e921d07427340ab9e6ed526ccd215a565b3298"

PINNED_ARCHIVE_VERIFIED = "pinned_archive_verified"
PINNED_BINARY_VERIFIED = "pinned_binary_verified"
EXTERNAL_UNVERIFIED = "external_unverified"
VERIFIED_SOURCES = frozenset({PINNED_ARCHIVE_VERIFIED, PINNED_BINARY_VERIFIED})
REPORT_FIELDS = {"RuleID": str, "File": str, "StartLine": int, "Fingerprint": str}


class ScannerError(RuntimeError):
    """The scanner could not run; the scan is NOT_RUN, never PASS."""


def install(dest: Path) -> Path:
    with urllib.request.urlopen(GITLEAKS_URL, timeout=120) as response:
        archive = response.read()
    digest = hashlib.sha256(archive).hexdigest()
    if digest != GITLEAKS_SHA256:
        raise ScannerError(f"gitleaks archive digest {digest} != pinned {GITLEAKS_SHA256}")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        member = bundle.extractfile("gitleaks")
        if member is None:
            raise ScannerError("gitleaks archive has no gitleaks binary")
        payload = member.read()
    binary_digest = hashlib.sha256(payload).hexdigest()
    if binary_digest != GITLEAKS_BINARY_SHA256:
        raise ScannerError(
            f"gitleaks binary digest {binary_digest} != pinned {GITLEAKS_BINARY_SHA256}"
        )
    dest.mkdir(parents=True, exist_ok=True)
    binary = dest / "gitleaks"
    binary.write_bytes(payload)
    binary.chmod(0o755)
    return binary


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_scanner(install_dir: Path | None, supplied: Path | None) -> dict[str, Any]:
    """The binary to run and its provenance; only a pinned binary counts as verified."""
    if install_dir is not None:
        binary = install(install_dir).resolve()
        source_mode = PINNED_ARCHIVE_VERIFIED
        archive_sha256: str | None = GITLEAKS_SHA256
    elif supplied is not None:
        binary = supplied.resolve()
        archive_sha256 = None
        source_mode = EXTERNAL_UNVERIFIED
    else:
        raise ScannerError("no gitleaks source given")
    binary_sha256 = file_sha256(binary)
    if source_mode == EXTERNAL_UNVERIFIED and binary_sha256 == GITLEAKS_BINARY_SHA256:
        source_mode = PINNED_BINARY_VERIFIED
    return {
        "binary": binary,
        "source_mode": source_mode,
        "scanner_archive_sha256": archive_sha256,
        "scanner_binary_sha256": binary_sha256,
    }


def verify_version(binary: Path) -> str:
    completed = subprocess.run(
        [str(binary), "version"], capture_output=True, text=True, check=False
    )
    observed = completed.stdout.strip()
    if completed.returncode != 0 or observed != GITLEAKS_VERSION:
        raise ScannerError(f"gitleaks version {observed!r} != pinned {GITLEAKS_VERSION}")
    return observed


def scan(binary: Path, tree: Path, config: Path) -> list[dict[str, Any]]:
    """Every finding in ``tree``, sorted, without secret values."""
    with tempfile.TemporaryDirectory() as scratch:
        report = Path(scratch) / "report.json"
        completed = subprocess.run(
            [
                str(binary),
                "dir",
                ".",
                "--config",
                str(config),
                "--no-banner",
                "--no-color",
                "--redact",
                "--report-format",
                "json",
                "--report-path",
                str(report),
                "--exit-code",
                "0",
            ],
            cwd=tree,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not report.is_file():
            raise ScannerError(f"gitleaks failed with exit {completed.returncode}")
        try:
            raw = json.loads(report.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ScannerError(f"gitleaks report is malformed: {type(exc).__name__}") from exc
    return sorted(
        (parse_finding(index, item) for index, item in enumerate(_report_items(raw))),
        key=lambda row: (row["file"], row["line"], row["rule"]),
    )


def _report_items(raw: Any) -> list[Any]:
    if not isinstance(raw, list):
        raise ScannerError(f"gitleaks report is malformed: top level is {type(raw).__name__}")
    return raw


def parse_finding(index: int, item: Any) -> dict[str, Any]:
    """One report entry, validated field by field; a malformed entry is NOT_RUN."""
    if not isinstance(item, dict):
        raise ScannerError(f"gitleaks report is malformed: entry {index} is not an object")
    for field, kind in REPORT_FIELDS.items():
        value = item.get(field)
        # bool is an int subclass; a boolean line number is malformed too.
        if not isinstance(value, kind) or isinstance(value, bool):
            raise ScannerError(f"gitleaks report is malformed: entry {index} field {field}")
    return {
        "rule": item["RuleID"],
        "file": item["File"],
        "line": item["StartLine"],
        "fingerprint": item["Fingerprint"],
    }


def _chars(rng: random.Random, alphabet: str, count: int) -> str:
    return "".join(rng.choice(alphabet) for _ in range(count))


def red_controls(seed: int = 491) -> list[dict[str, str]]:
    """Representative secrets, generated so no secret literal is ever committed."""
    rng = random.Random(seed)
    alnum = string.ascii_letters + string.digits
    upper32 = string.ascii_uppercase + "234567"
    body = "\n".join(_chars(rng, string.ascii_letters + string.digits + "+/", 64) for _ in range(6))
    key_kind = "RSA " + "PRIVATE KEY"
    return [
        {
            "control": "github_personal_access_token",
            "rule": "github-pat",
            "path": "src/settings.py",
            "content": f'GITHUB_TOKEN = "ghp_{_chars(rng, alnum, 36)}"\n',
        },
        {
            "control": "aws_access_key_id",
            "rule": "aws-access-token",
            "path": "config/cloud.ini",
            "content": f"aws_access_key_id = {'AKIA' + _chars(rng, upper32, 16)}\n",
        },
        {
            "control": "private_key",
            "rule": "private-key",
            "path": "deploy/id_rsa",
            "content": f"-----BEGIN {key_kind}-----\n{body}\n-----END {key_kind}-----\n",
        },
        {
            "control": "slack_bot_token",
            "rule": "slack-bot-token",
            "path": "ops/notify.py",
            "content": (
                "SLACK = "
                f'"xoxb-{_chars(rng, string.digits, 12)}-{_chars(rng, string.digits, 13)}'
                f'-{_chars(rng, alnum, 24)}"\n'
            ),
        },
        {
            "control": "stripe_live_secret_key",
            "rule": "stripe-access-token",
            "path": "billing/keys.py",
            "content": f'STRIPE = "sk_live_{_chars(rng, alnum, 32)}"\n',
        },
        {
            "control": "generic_api_key_assignment",
            "rule": "generic-api-key",
            "path": "app/client.py",
            "content": f'api_key = "{_chars(rng, alnum, 40)}"\n',
        },
    ]


def exclusions(config: Path) -> list[dict[str, str]]:
    """Every exclusion of the scan configuration: its rule, file and exact value."""
    document = tomllib.loads(config.read_text(encoding="utf-8"))
    return [
        {
            "rule": rule["id"],
            "path": entry["paths"][0].removeprefix("^").removesuffix("$").replace("\\.", "."),
            "value": entry["regexes"][0].removeprefix("^").removesuffix("$"),
        }
        for rule in document.get("rules", [])
        for entry in rule.get("allowlists", [])
    ]


def run_controls(binary: Path, config: Path) -> list[dict[str, Any]]:
    """Each control in its own tree: it passes only with exactly the expected outcome."""
    cases: list[dict[str, Any]] = [{**control, "expect": "FOUND"} for control in red_controls()]
    rng = random.Random(4910)
    for exclusion in exclusions(config):
        cases.append(
            {
                "control": f"exclusion_is_path_scoped:{exclusion['path']}",
                "rule": exclusion["rule"],
                "path": "src/elsewhere.py",
                "content": f'secret_token = "{exclusion["value"]}"\n',
                "expect": "FOUND",
            }
        )
        cases.append(
            {
                "control": f"exclusion_is_value_scoped:{exclusion['path']}",
                "rule": exclusion["rule"],
                "path": exclusion["path"],
                "content": f'api_key = "{_chars(rng, string.ascii_letters + string.digits, 40)}"\n',
                "expect": "FOUND",
            }
        )
    cases.append(
        {
            "control": "clean_tree",
            "rule": None,
            "path": "src/clean.py",
            "content": 'GREETING = "hello"\n',
            "expect": "NONE",
        }
    )
    results = []
    for case in cases:
        with tempfile.TemporaryDirectory() as scratch:
            target = Path(scratch) / case["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(case["content"], encoding="utf-8")
            findings = scan(binary, Path(scratch), config)
        rules = sorted({row["rule"] for row in findings})
        # FOUND: the expected rule fired. NONE: nothing fired at all.
        passed = case["rule"] in rules if case["expect"] == "FOUND" else not findings
        results.append(
            {
                "control": case["control"],
                "expected_rule": case["rule"],
                "expect": case["expect"],
                "observed_rules": rules,
                "status": "PASS" if passed else "FAIL",
            }
        )
    return results


def materialize_tracked(root: Path, dest: Path) -> list[tuple[str, str]]:
    """Copy exactly the git-tracked regular files of ``root`` into ``dest``.

    Returns the scanned manifest: each copied path with the sha256 of the bytes
    that were copied, sorted by path.
    """
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    manifest = []
    for relative in sorted(set(filter(None, listed.split("\0")))):
        source = root / relative
        if source.is_symlink() or not source.is_file():
            continue
        data = source.read_bytes()
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest.append((relative, hashlib.sha256(data).hexdigest()))
    return manifest


def manifest_sha256(manifest: list[tuple[str, str]]) -> str:
    """Digest of the sorted ``<sha256>  <path>`` lines of the scanned manifest."""
    lines = "".join(f"{digest}  {relative}\n" for relative, digest in sorted(manifest))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def _git_text(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=True, text=True
    ).stdout


def candidate_identity(root: Path) -> dict[str, Any]:
    """HEAD commit and tree, and the tracked paths that differ from HEAD."""
    dirty = sorted(
        line[3:]
        for line in _git_text(root, "status", "--porcelain=v1", "--untracked-files=no").splitlines()
        if line.strip()
    )
    return {
        "commit": _git_text(root, "rev-parse", "HEAD").strip(),
        "tree": _git_text(root, "rev-parse", "HEAD^{tree}").strip(),
        "dirty": bool(dirty),
        "dirty_paths": dirty,
    }


def blockers(
    findings: list[dict[str, Any]],
    failed_controls: list[str],
    candidate: dict[str, Any],
    source_mode: str,
) -> list[str]:
    """Every reason the scan is not PASS; empty means PASS."""
    reasons = []
    if findings:
        reasons.append("findings")
    if failed_controls:
        reasons.append("failed_controls")
    if candidate["dirty"]:
        # The scanned bytes are not the HEAD tree; the evidence binds to no commit.
        reasons.append("dirty_tree")
    if source_mode not in VERIFIED_SOURCES:
        reasons.append("unverified_scanner")
    return reasons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--install-dir", type=Path, help="install the pinned gitleaks here")
    source.add_argument("--gitleaks", type=Path, help="an existing gitleaks binary")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    # A summary from an earlier run must never stand in for this one.
    report_path.unlink(missing_ok=True)

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scanner": "gitleaks",
        "scanner_version": GITLEAKS_VERSION,
        "pinned_archive_sha256": GITLEAKS_SHA256,
        "pinned_binary_sha256": GITLEAKS_BINARY_SHA256,
        "source_mode": None,
        "scanner_archive_sha256": None,
        "scanner_binary_sha256": None,
        "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "status": "NOT_RUN",
    }
    try:
        scanner = resolve_scanner(args.install_dir, args.gitleaks)
        binary = scanner.pop("binary")
        summary.update(scanner)
        verify_version(binary)
        controls = run_controls(binary, CONFIG)
        candidate = candidate_identity(ROOT)
        with tempfile.TemporaryDirectory() as scratch:
            manifest = materialize_tracked(ROOT, Path(scratch))
            findings = scan(binary, Path(scratch), CONFIG)
    except Exception as exc:  # every failure is NOT_RUN, never PASS
        summary["error"] = f"{type(exc).__name__}: {exc}"
        _write(report_path, summary)
        print(f"broad secret scan NOT_RUN: {summary['error']}", file=sys.stderr)
        return 2

    failed_controls = [row["control"] for row in controls if row["status"] != "PASS"]
    candidate["scanned_files"] = len(manifest)
    candidate["manifest_sha256"] = manifest_sha256(manifest)
    reasons = blockers(findings, failed_controls, candidate, summary["source_mode"])
    summary.update(
        {
            "candidate": candidate,
            "controls": controls,
            "failed_controls": failed_controls,
            "tracked_files_scanned": len(manifest),
            "findings": findings,
            "blockers": reasons,
            "status": "FAIL" if reasons else "PASS",
        }
    )
    _write(report_path, summary)
    for row in controls:
        print(f"control {row['control']}: {row['status']} ({row['observed_rules']})")
    print(f"scanner source: {summary['source_mode']} sha256={summary['scanner_binary_sha256']}")
    print(
        f"candidate: commit={candidate['commit']} tree={candidate['tree']} "
        f"dirty={candidate['dirty']} manifest_sha256={candidate['manifest_sha256']}"
    )
    print(f"tracked files scanned: {len(manifest)}")
    for row in findings:
        print(f"FINDING {row['rule']} {row['file']}:{row['line']} (value redacted)")
    for reason in reasons:
        print(f"BLOCKER {reason}")
    print(f"broad secret scan: {summary['status']}")
    return 0 if summary["status"] == "PASS" else 1


def _write(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
