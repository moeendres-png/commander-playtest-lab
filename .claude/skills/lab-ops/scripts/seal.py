#!/usr/bin/env python3
"""Prepare a current-boundary epoch seal in a Lab worktree, with the CI gates a seal PR meets.

    seal.py RUN_ID [--lab .] [--replace EPOCH_ID] [--scratch DIR]

Run on a fresh branch from main. It downloads and verifies the PB-03 packet
(pb03_packet.py --into), removes a superseded unsealed epoch (--replace, via
``git rm``), regenerates the hash manifests, and runs the repository's broad
secret scan with the pinned gitleaks before anything is pushed: the required
``security`` check scans every tracked file, so a packet that trips it would
turn main red. It commits nothing; read the output, run ``tests/qualification``,
then commit and push.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("run_id")
    p.add_argument("--lab", type=Path, default=Path("."))
    p.add_argument("--replace", help="unsealed epoch id to remove from this branch")
    p.add_argument(
        "--scratch",
        type=Path,
        default=Path(os.environ.get("TMPDIR", tempfile.gettempdir())) / "lab-ops-seal",
    )
    a = p.parse_args()
    lab = a.lab.resolve()
    a.scratch.mkdir(parents=True, exist_ok=True)

    if a.replace:
        old = f"qualification/current-boundary-epochs/{a.replace}"
        done = run(["git", "rm", "-q", "-r", old], lab)
        if done.returncode != 0:
            raise SystemExit(f"git rm {old}: {done.stderr.strip()}")
        print(f"removed {old}")

    packet = run(
        [
            sys.executable,
            str(HERE / "pb03_packet.py"),
            a.run_id,
            str(a.scratch / f"packet-{a.run_id}"),
            "--into",
            str(lab),
        ],
        lab,
    )
    print(packet.stdout.rstrip())
    if packet.returncode != 0 or "verified" not in packet.stdout:
        print(packet.stderr.rstrip(), file=sys.stderr)
        return 1
    verified = next(line for line in packet.stdout.splitlines() if "verified" in line)
    have, total = verified.split()[1].split("/")
    if have != total:
        print("packet digests do not verify; nothing to seal", file=sys.stderr)
        return 1

    manifests = run([sys.executable, "scripts/regenerate_hash_manifests.py"], lab)
    print(manifests.stdout.rstrip())
    if manifests.returncode != 0:
        print(manifests.stderr.rstrip(), file=sys.stderr)
        return 1

    # The scan reads tracked files: stage the epoch so the scan sees it.
    run(["git", "add", "-A", "qualification", "WS17_SHA256SUMS"], lab)
    scan = run(
        [
            sys.executable,
            "scripts/run_broad_secret_scan.py",
            "--install-dir",
            str(a.scratch / "gitleaks"),
            "--report",
            str(a.scratch / "broad-secret-scan.json"),
        ],
        lab,
    )
    lines = (scan.stdout + scan.stderr).splitlines()
    findings = [line for line in lines if line.startswith("FINDING")]
    for line in findings[:10]:
        print(line)
    if len(findings) > 10:
        print(f"... {len(findings) - 10} more findings")
    verdict = next((line for line in lines if line.startswith("broad secret scan")), None)
    print(verdict or "broad secret scan: no verdict line")
    if scan.returncode != 0 or not verdict or not verdict.endswith("PASS"):
        print(
            "the packet trips the required security check: fix the producer at its source "
            "(never add exclusions for evidence values), re-run PB-03, and seal that run",
            file=sys.stderr,
        )
        return 1
    print("ready: run tests/qualification, then commit 'Evidence: seal current-boundary epoch …'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
