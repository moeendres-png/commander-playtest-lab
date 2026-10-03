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
3. Scan exactly the git-tracked files of the checkout with ``.gitleaks.toml``,
   bound to the checkout's commit, tree and a manifest digest of the scanned
   bytes. Inline ``gitleaks:allow`` comments are ignored, a tracked
   ``.gitleaksignore`` fails the run, and encoded or archived content is decoded.

Exit 0 only when every control behaves and the repository has no finding.
Exit 1 on a finding or a failed control, 2 when the scanner cannot run. The
summary carries rule, file, line and fingerprint only, never a secret value.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import random
import string
import subprocess
import sys
import tarfile
import tempfile
import time
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
# The binary inside that archive. A supplied --gitleaks must be this exact binary.
GITLEAKS_BINARY_SHA256 = "5fd1b3b0073269484d40078662e921d07427340ab9e6ed526ccd215a565b3298"

# Every suppression channel gitleaks honours besides .gitleaks.toml is closed:
# inline `gitleaks:allow` comments are ignored, a .gitleaksignore (which gitleaks
# always loads from the scan root) is never scanned with and fails the run when
# tracked, no baseline is passed, and encoded or archived content is decoded.
SCAN_FLAGS = (
    "--ignore-gitleaks-allow",
    "--max-decode-depth",
    "3",
    "--max-archive-depth",
    "3",
)
SUPPRESSION_FILE = ".gitleaksignore"
INSTALL_ATTEMPTS = 3


class ScannerError(RuntimeError):
    """The scanner could not run; the scan is NOT_RUN, never PASS."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(dest: Path) -> Path:
    archive = b""
    for attempt in range(1, INSTALL_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(GITLEAKS_URL, timeout=120) as response:
                archive = response.read()
            break
        except OSError as exc:
            if attempt == INSTALL_ATTEMPTS:
                raise ScannerError(f"gitleaks download failed: {exc}") from exc
            time.sleep(5 * attempt)
    digest = hashlib.sha256(archive).hexdigest()
    if digest != GITLEAKS_SHA256:
        raise ScannerError(f"gitleaks archive digest {digest} != pinned {GITLEAKS_SHA256}")
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            member = bundle.extractfile("gitleaks")
            if member is None:
                raise ScannerError("gitleaks archive member is not a file")
            data = member.read()
    except (KeyError, tarfile.TarError) as exc:
        raise ScannerError(f"gitleaks archive is unreadable: {exc}") from exc
    dest.mkdir(parents=True, exist_ok=True)
    binary = dest / "gitleaks"
    binary.write_bytes(data)
    binary.chmod(0o755)
    return binary


def verify_scanner(binary: Path) -> str:
    """The binary must be the pinned one, by digest and by reported version."""
    digest = _sha256_file(binary)
    if digest != GITLEAKS_BINARY_SHA256:
        raise ScannerError(f"gitleaks binary digest {digest} != pinned {GITLEAKS_BINARY_SHA256}")
    completed = subprocess.run(
        [str(binary), "version"], capture_output=True, text=True, check=False
    )
    observed = completed.stdout.strip()
    if completed.returncode != 0 or observed != GITLEAKS_VERSION:
        raise ScannerError(f"gitleaks version {observed!r} != pinned {GITLEAKS_VERSION}")
    return digest


def _parse_report(text: str) -> list[dict[str, Any]]:
    try:
        raw = json.loads(text)
        if not isinstance(raw, list):
            raise TypeError("report is not a list")
        return [
            {
                "rule": str(item["RuleID"]),
                "file": str(item["File"]),
                "line": int(item["StartLine"]),
                "fingerprint": str(item["Fingerprint"]),
            }
            for item in raw
        ]
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ScannerError(f"gitleaks report is malformed: {exc}") from exc


def _scan_once(binary: Path, tree: Path, config: Path) -> list[dict[str, Any]]:
    """Every finding in ``tree``, sorted, without secret values."""
    if any(tree.rglob(SUPPRESSION_FILE)):
        raise ScannerError(f"refusing to scan a tree that holds a {SUPPRESSION_FILE}")
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
                *SCAN_FLAGS,
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
            # --redact keeps secret values out of gitleaks' own output.
            raise ScannerError(
                f"gitleaks failed with exit {completed.returncode}: {completed.stderr[-500:]}"
            )
        findings = _parse_report(report.read_text(encoding="utf-8"))
    return sorted(findings, key=lambda row: (row["file"], row["line"], row["rule"]))


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
    """Validate narrow exclusions before deriving their adversarial controls."""
    try:
        document = tomllib.loads(config.read_text(encoding="utf-8"))
        if (
            document.get("extend", {}).get("useDefault") is not True
            or "allowlists" in document
            or "allowlist" in document
        ):
            raise ValueError("upstream defaults and rule-bound exclusions required")
        rules = document.get("rules", [])
        if not isinstance(rules, list):
            raise TypeError("rules must be a list")
        result = []
        for rule in rules:
            if not isinstance(rule, dict) or not isinstance(rule.get("id"), str):
                raise TypeError("rule id missing")
            entries = rule.get("allowlists", [])
            if not isinstance(entries, list):
                raise TypeError("allowlists must be a list")
            for entry in entries:
                if (
                    not isinstance(entry, dict)
                    or entry.get("condition") != "AND"
                    or not str(entry.get("description", "")).strip()
                ):
                    raise ValueError("rule exclusion needs AND and a justification")
                for key in ("paths", "regexes"):
                    values = entry.get(key)
                    if (
                        not isinstance(values, list)
                        or len(values) != 1
                        or not isinstance(values[0], str)
                        or not values[0].startswith("^")
                        or not values[0].endswith("$")
                    ):
                        raise ValueError("rule exclusion needs one anchored path and value")
                result.append(
                    {
                        "rule": rule["id"],
                        "path": entry["paths"][0]
                        .removeprefix("^")
                        .removesuffix("$")
                        .replace("\\.", "."),
                        "value": entry["regexes"][0].removeprefix("^").removesuffix("$"),
                    }
                )
        return result
    except (OSError, ValueError, TypeError, AttributeError, KeyError, IndexError) as error:
        raise ScannerError("gitleaks configuration malformed: " + type(error).__name__) from error


def scan(binary: Path, tree: Path, config: Path) -> list[dict[str, Any]]:
    """Scan the root configuration too, outside the upstream filename allowlist."""
    root_config = tree / ".gitleaks.toml"
    if root_config.is_symlink():
        raise ScannerError("root configuration symlink cannot be scanned")
    findings = _scan_once(binary, tree, config)
    if root_config.is_file():
        # Upstream defaults globally allowlist gitleaks.toml filenames. Scan
        # the same bytes under a neutral name, then retain the original path
        # identity in the redacted evidence; rule/value exclusions stay intact.
        with tempfile.TemporaryDirectory() as scratch:
            alias = "root-security-configuration.txt"
            (Path(scratch) / alias).write_bytes(root_config.read_bytes())
            for row in _scan_once(binary, Path(scratch), config):
                row["file"] = ".gitleaks.toml"
                row["fingerprint"] = row["fingerprint"].replace(alias, ".gitleaks.toml")
                findings.append(row)
    return sorted(
        findings, key=lambda row: (row["file"], row["line"], row["rule"], row["fingerprint"])
    )


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
    configuration_secret = next(case for case in red_controls() if case["rule"] == "github-pat")
    cases.append(
        {
            **configuration_secret,
            "control": "root_configuration_is_scanned",
            "path": ".gitleaks.toml",
            "content": "# " + configuration_secret["content"],
            "expect": "FOUND",
        }
    )
    allowed = red_controls()[0]
    cases.append(
        {
            **allowed,
            "control": "inline_allow_comment_is_ignored",
            "content": allowed["content"].rstrip("\n") + "  # gitleaks:allow\n",
            "expect": "FOUND",
        }
    )
    cases.append(
        {
            **allowed,
            "control": "suppression_file_is_refused",
            "extra": {SUPPRESSION_FILE: f"{allowed['path']}:{allowed['rule']}:1\n"},
            "expect": "REFUSED",
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
        refused = False
        with tempfile.TemporaryDirectory() as scratch:
            files = {case["path"]: case["content"], **case.get("extra", {})}
            for relative, content in files.items():
                target = Path(scratch) / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            try:
                findings = scan(binary, Path(scratch), config)
            except ScannerError:
                if case["expect"] != "REFUSED":
                    raise
                refused, findings = True, []
        rules = sorted({row["rule"] for row in findings})
        # FOUND: the expected rule fired. NONE: nothing fired at all. REFUSED:
        # the scan refused the tree instead of honouring its suppression file.
        if case["expect"] == "FOUND":
            passed = case["rule"] in rules
        elif case["expect"] == "REFUSED":
            passed = refused
        else:
            passed = not findings
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


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def source_identity(root: Path) -> dict[str, Any]:
    """The commit and tree the scanned bytes belong to, and whether they differ."""
    return {
        "head": _git(root, "rev-parse", "HEAD"),
        "tree": _git(root, "rev-parse", "HEAD^{tree}"),
        "tracked_changes": bool(_git(root, "status", "--porcelain", "--untracked-files=no")),
    }


def materialize_tracked(root: Path, dest: Path) -> dict[str, Any]:
    """Copy exactly the git-tracked regular files of ``root`` into ``dest``.

    Symlinks (mode 120000) fail closed: their target text is committed content.
    Submodules (160000) are counted separately and are not file blobs. A tracked suppression file is never copied and is
    reported, and so is a path holding ``gitleaks.toml`` other than the config:
    the upstream default allowlist exempts such paths unanchored. Any other
    entry that cannot be copied fails the run instead of shrinking the scan.
    """
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--stage"], capture_output=True, check=True
    ).stdout
    manifest = hashlib.sha256()
    copied = symlinks = gitlinks = 0
    suppression: list[str] = []
    for entry in filter(None, listed.split(b"\0")):
        meta, _, raw_path = entry.partition(b"\t")
        mode = meta.split(b" ", 1)[0].decode("ascii")
        relative = os.fsdecode(raw_path)
        name = relative.rsplit("/", 1)[-1]
        if mode == "120000":
            # Target text is committed blob content. A skipped link cannot earn PASS.
            raise ScannerError(f"tracked symlink {relative!r} cannot be scanned")
        if mode == "160000":
            gitlinks += 1
            continue
        if name == SUPPRESSION_FILE or (
            "gitleaks.toml" in relative and relative != ".gitleaks.toml"
        ):
            suppression.append(relative)
            continue
        source = root / relative
        if mode not in {"100644", "100755"} or source.is_symlink() or not source.is_file():
            raise ScannerError(f"tracked entry {relative!r} (mode {mode}) cannot be scanned")
        data = source.read_bytes()
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest.update(f"{mode} {hashlib.sha256(data).hexdigest()} ".encode() + raw_path + b"\n")
        copied += 1
    if copied == 0:
        raise ScannerError("no tracked file was materialized")
    return {
        "files": copied,
        "skipped_symlinks": symlinks,
        "skipped_submodules": gitlinks,
        "suppression_paths": sorted(suppression),
        "manifest_sha256": manifest.hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--install-dir", type=Path, help="install the pinned gitleaks here")
    source.add_argument(
        "--gitleaks", type=Path, help="an existing gitleaks binary (must be the pinned binary)"
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report_path = args.report if args.report.is_absolute() else ROOT / args.report

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scanner": "gitleaks",
        "scanner_version": GITLEAKS_VERSION,
        "scanner_archive_sha256": GITLEAKS_SHA256,
        "scanner_source": "installed_pinned_archive" if args.install_dir else "supplied_binary",
        "scan_flags": list(SCAN_FLAGS),
        "status": "NOT_RUN",
    }
    try:
        summary["config_sha256"] = _sha256_file(CONFIG)
        summary["source"] = source_identity(ROOT)
        binary = (install(args.install_dir) if args.install_dir else args.gitleaks).resolve()
        summary["scanner_binary_sha256"] = verify_scanner(binary)
        summary["controls"] = controls = run_controls(binary, CONFIG)
        with tempfile.TemporaryDirectory() as scratch:
            summary["scanned"] = scanned = materialize_tracked(ROOT, Path(scratch))
            findings = scan(binary, Path(scratch), CONFIG)
    except (ScannerError, OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        summary["error"] = str(exc)
        _write(report_path, summary)
        print(f"broad secret scan NOT_RUN: {exc}", file=sys.stderr)
        return 2

    failed_controls = [row["control"] for row in controls if row["status"] != "PASS"]
    suppression = scanned["suppression_paths"]
    summary.update(
        {
            "failed_controls": failed_controls,
            "findings": findings,
            "status": "PASS" if not (findings or failed_controls or suppression) else "FAIL",
        }
    )
    _write(report_path, summary)
    for row in controls:
        print(f"control {row['control']}: {row['status']} ({row['observed_rules']})")
    print(
        f"tracked files scanned: {scanned['files']} at {summary['source']['tree']} "
        f"(manifest {scanned['manifest_sha256']})"
    )
    for path in suppression:
        print(f"SUPPRESSION FILE tracked: {path}")
    for row in findings:
        print(f"FINDING {row['rule']} {row['file']}:{row['line']} (value redacted)")
    print(f"broad secret scan: {summary['status']}")
    return 0 if summary["status"] == "PASS" else 1


def _write(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
