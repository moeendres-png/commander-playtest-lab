#!/usr/bin/env python3
"""B10 (#491): deterministic broad secret scan with the pinned gitleaks.

The project sentinel (the ``Secret-pattern scan`` step of the required
``quality`` job) stays a separate signal. This scan adds the full upstream
gitleaks rule set:

1. Install the pinned gitleaks release and verify the archive digest and the
   reported version before it runs (``--install-dir``), or use ``--gitleaks``.
2. Red controls: representative secrets generated at run time (never stored in
   the repository) must each be found by their expected rule, an allowlisted
   value must still be found outside its own file, a different value must still
   be found inside an allowlisted file, and a clean tree must produce nothing.
   A scanner that finds nothing would otherwise pass every repository scan.
3. Scan exactly the git-tracked files of the checkout with ``.gitleaks.toml``.

Exit 0 only when every control behaves and the repository has no finding.
Exit 1 on a finding or a failed control, 2 when the scanner cannot run. The
summary carries rule, file, line and fingerprint only, never a secret value.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import shutil
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
SCHEMA_VERSION = "b10.broad-secret-scan.v1"

GITLEAKS_VERSION = "8.28.0"
GITLEAKS_ARCHIVE = f"gitleaks_{GITLEAKS_VERSION}_linux_x64.tar.gz"
GITLEAKS_URL = (
    f"https://github.com/gitleaks/gitleaks/releases/download/v{GITLEAKS_VERSION}/{GITLEAKS_ARCHIVE}"
)
# From the release's gitleaks_8.28.0_checksums.txt.
GITLEAKS_SHA256 = "a65b5253807a68ac0cafa4414031fd740aeb55f54fb7e55f386acb52e6a840eb"


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
        dest.mkdir(parents=True, exist_ok=True)
        binary = dest / "gitleaks"
        binary.write_bytes(member.read())
    binary.chmod(0o755)
    return binary


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
        raw = json.loads(report.read_text(encoding="utf-8"))
    return sorted(
        (
            {
                "rule": item["RuleID"],
                "file": item["File"],
                "line": item["StartLine"],
                "fingerprint": item["Fingerprint"],
            }
            for item in raw
        ),
        key=lambda row: (row["file"], row["line"], row["rule"]),
    )


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


def materialize_tracked(root: Path, dest: Path) -> int:
    """Copy exactly the git-tracked regular files of ``root`` into ``dest``."""
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    count = 0
    for relative in filter(None, listed.split("\0")):
        source = root / relative
        if source.is_symlink() or not source.is_file():
            continue
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--install-dir", type=Path, help="install the pinned gitleaks here")
    source.add_argument("--gitleaks", type=Path, help="an existing gitleaks binary")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report_path = args.report if args.report.is_absolute() else ROOT / args.report

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scanner": "gitleaks",
        "scanner_version": GITLEAKS_VERSION,
        "scanner_archive_sha256": GITLEAKS_SHA256,
        "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "status": "NOT_RUN",
    }
    try:
        binary = (install(args.install_dir) if args.install_dir else args.gitleaks).resolve()
        verify_version(binary)
        controls = run_controls(binary, CONFIG)
        with tempfile.TemporaryDirectory() as scratch:
            tracked = materialize_tracked(ROOT, Path(scratch))
            findings = scan(binary, Path(scratch), CONFIG)
    except (ScannerError, OSError, subprocess.CalledProcessError) as exc:
        summary["error"] = str(exc)
        _write(report_path, summary)
        print(f"broad secret scan NOT_RUN: {exc}", file=sys.stderr)
        return 2

    failed_controls = [row["control"] for row in controls if row["status"] != "PASS"]
    summary.update(
        {
            "controls": controls,
            "failed_controls": failed_controls,
            "tracked_files_scanned": tracked,
            "findings": findings,
            "status": "PASS" if not findings and not failed_controls else "FAIL",
        }
    )
    _write(report_path, summary)
    for row in controls:
        print(f"control {row['control']}: {row['status']} ({row['observed_rules']})")
    print(f"tracked files scanned: {tracked}")
    for row in findings:
        print(f"FINDING {row['rule']} {row['file']}:{row['line']} (value redacted)")
    print(f"broad secret scan: {summary['status']}")
    return 0 if summary["status"] == "PASS" else 1


def _write(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
