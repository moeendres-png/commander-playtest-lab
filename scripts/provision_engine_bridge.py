"""Provision and verify the XMage rules engine bridge for Commander Studio.

Part of Issue #1172:
Ensures reproducible engine deployment into the Studio data folder
(%LOCALAPPDATA%\\CommanderStudio or ~/.local/share/commander-studio).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from commander_lab.qualification.current_boundary.bridge_launcher import (
    canonical_xmage_engine_pin,
)
from commander_lab.studio.launch import (
    ENGINE_JAR,
    _java_executable,
    engine_state,
)
from commander_lab.studio.store import studio_data_dir


def _compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def provision_bridge(
    source_path: Path,
    target_data_dir: Path | None = None,
) -> dict[str, object]:
    """Copy and verify an engine bridge JAR into the Studio data folder."""
    if not source_path.is_file():
        raise FileNotFoundError(f"Source engine bridge JAR not found: {source_path}")

    data_dir = (target_data_dir or studio_data_dir()).resolve()
    engine_dir = data_dir / "engine"
    engine_dir.mkdir(parents=True, exist_ok=True)

    dest_jar = data_dir / ENGINE_JAR
    source_sha256 = _compute_sha256(source_path)

    # Copy JAR
    shutil.copy2(source_path, dest_jar)
    dest_sha256 = _compute_sha256(dest_jar)
    if dest_sha256 != source_sha256:
        raise RuntimeError("Checksum mismatch after copying engine bridge JAR")

    # Record digest and canonical pin
    pin = canonical_xmage_engine_pin()
    (engine_dir / "xmage-engine-bridge.jar.sha256").write_text(
        f"{dest_sha256}  xmage-engine-bridge.jar\n", encoding="utf-8"
    )
    (engine_dir / "ENGINE_PIN.txt").write_text(f"{pin}\n", encoding="utf-8")

    return {
        "status": "provisioned",
        "jar_path": str(dest_jar),
        "sha256": dest_sha256,
        "engine_pin": pin,
        "java_executable": _java_executable(),
    }


def verify_installed_engine(target_data_dir: Path | None = None) -> dict[str, object]:
    """Inspect and report the status of the installed engine bridge."""
    data_dir = (target_data_dir or studio_data_dir()).resolve()
    state = engine_state(data_dir)
    java = _java_executable()

    result: dict[str, object] = {
        "data_dir": str(data_dir),
        "engine_state": state,
        "java_path": java,
    }

    jar = data_dir / ENGINE_JAR
    if jar.is_file() and java:
        # Check basic invocation
        try:
            proc = subprocess.run(
                [java, "-version"],
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False,
            )
            result["java_version_output"] = (proc.stdout or proc.stderr).strip().splitlines()[:2]
        except (subprocess.SubprocessError, OSError) as exc:
            result["java_version_error"] = str(exc)

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Provision and verify XMage engine bridge for Commander Studio"
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Path to built or downloaded xmage-engine-bridge.jar",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Custom Studio data directory (default: COMMANDER_LAB_STUDIO_DATA or standard system path)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Report status and verification of current engine installation",
    )
    args = parser.parse_args(argv)

    if args.source:
        res = provision_bridge(args.source, args.data_dir)
        print(json.dumps(res, indent=2))
        return 0

    status = verify_installed_engine(args.data_dir)
    print(json.dumps(status, indent=2))
    state = status.get("engine_state")
    if isinstance(state, dict) and state.get("ready"):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
