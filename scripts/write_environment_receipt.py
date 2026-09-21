#!/usr/bin/env python3
"""WS223 environment-receipt writer (offline, no network, no secrets).

Records the reproducible environment identity for a lane run: interpreter,
hashseed, dependency-lock digest, resolved dependency-set digest, Java
toolchain, tool versions and engine pins, sealed with an identity digest.
Writes JSON to --output. Never emits secrets (no ``sk-`` material).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = "ws223-environment-receipt-1.0.0"


def _java_version() -> str:
    try:
        proc = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=30)
        out = (proc.stderr or proc.stdout or "").strip().splitlines()
        return out[0] if out else "unavailable"
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def _tool_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in ("pip", "setuptools", "wheel", "pytest", "mypy", "ruff"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "unavailable"
    return versions


def _engine_pins() -> dict[str, str]:
    pins: dict[str, str] = {}
    try:
        cfg = json.loads((REPO_ROOT / "config/rules_engines.json").read_text())
        pins["primary_engine_commit"] = cfg["primary_engine"]["commit"]
        pins["protocol_version"] = cfg["protocol_version"]
    except (OSError, KeyError, ValueError):
        pins["primary_engine_commit"] = "unknown"
        pins["protocol_version"] = "unknown"
    return pins


def _lock_digests() -> tuple[str, str]:
    lock_path = REPO_ROOT / "requirements/lock.txt"
    text = lock_path.read_text(encoding="utf-8")
    lock_digest = hashlib.sha256(text.encode()).hexdigest()
    spec = importlib.util.spec_from_file_location(
        "ws223_verify_lock", REPO_ROOT / "scripts/verify_dependency_lock.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    compiler_entries, _ = module._parse_lock(text)
    resolved = sorted(f"{e['name']}=={e['version']}" for e in compiler_entries)
    resolved_digest = hashlib.sha256(
        json.dumps(resolved, separators=(",", ":")).encode()
    ).hexdigest()
    return lock_digest, resolved_digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="write a WS223 environment receipt")
    parser.add_argument("--lane", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    lock_digest, resolved_digest = _lock_digests()
    receipt: dict = {
        "schema_version": SCHEMA_VERSION,
        "lane": args.lane,
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "dependency_lock_digest": lock_digest,
        "resolved_dependency_set_digest": resolved_digest,
        "java": _java_version(),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED", "unset"),
        "tool_versions": _tool_versions(),
        "engine_pins": _engine_pins(),
    }
    canonical = {k: v for k, v in receipt.items() if k != "generated_at"}
    receipt["identity_sha256"] = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    assert "sk-" not in payload
    Path(args.output).write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
