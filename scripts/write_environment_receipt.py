"""Write a machine-readable environment receipt for qualification runs.

Captures exact tooling identity (interpreter, lock digest, resolved-set
digest, Java runtime, image ref, hashseed, tool versions, engine pins) so
evidence can be attributed to the environment that produced it. Collects no
secrets and dumps no ambient environment: only explicitly named values.
Wall-clock time is recorded as informational only and excluded from the
identity digest.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

RECEIPT_SCHEMA = "ws223-environment-receipt-1.0.0"
TOOL_PACKAGES = ("pip", "setuptools", "wheel", "pytest", "pydantic", "PyYAML")


def _lock_digest(root: Path) -> str | None:
    lock = root / "requirements" / "lock.txt"
    if not lock.is_file():
        return None
    return hashlib.sha256(lock.read_bytes()).hexdigest()


def _resolved_set_digest() -> tuple[str | None, int]:
    try:
        output = subprocess.run(
            [sys.executable, "-m", "pip", "freeze", "--exclude-editable"],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, OSError):
        return None, 0
    lines = sorted(line.strip() for line in output.stdout.splitlines() if line.strip())
    if not lines:
        return None, 0
    return hashlib.sha256("\n".join(lines).encode()).hexdigest(), len(lines)


def _java_identity() -> dict[str, str | None]:
    identity: dict[str, str | None] = {"runtime": None, "java_home": os.environ.get("JAVA_HOME")}
    try:
        completed = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return identity
    detail = (completed.stderr or completed.stdout or "").strip().splitlines()
    identity["runtime"] = " | ".join(line.strip() for line in detail[:3]) or None
    return identity


def _tool_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for package in TOOL_PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def _engine_pins(root: Path) -> dict[str, str | None]:
    pins: dict[str, str | None] = {
        "xmage_commit_env": os.environ.get("XMAGE_COMMIT"),
        "rules_engines_primary_commit": None,
    }
    manifest = root / "config" / "rules_engines.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        pins["rules_engines_primary_commit"] = (data.get("primary_engine") or {}).get("commit")
    except (OSError, ValueError):
        pass
    return pins


def _repo_head(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = completed.stdout.strip()
    return head or None


def build_receipt(root: Path, lane: str, image_ref: str | None) -> dict:
    lock_digest = _lock_digest(root)
    resolved_digest, resolved_count = _resolved_set_digest()
    canonical = {
        "schema_version": RECEIPT_SCHEMA,
        "lane": lane,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "dependency_lock_digest": lock_digest,
        "resolved_dependency_set_digest": resolved_digest,
        "resolved_dependency_count": resolved_count,
        "java": _java_identity(),
        "container_image_ref": image_ref or os.environ.get("WS223_IMAGE_REF"),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED", "unset"),
        "tool_versions": _tool_versions(),
        "engine_pins": _engine_pins(root),
        "repo_head": _repo_head(root),
        "note": "generated_at is informational and excluded from identity_sha256",
    }
    identity = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        **canonical,
        "identity_sha256": identity,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a WS223 environment receipt")
    parser.add_argument("--output", required=True)
    parser.add_argument("--lane", default="unspecified")
    parser.add_argument("--image-ref", default=None)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    receipt = build_receipt(root, args.lane, args.image_ref)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
