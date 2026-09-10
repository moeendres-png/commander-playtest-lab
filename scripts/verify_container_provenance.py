#!/usr/bin/env python3
"""Container provenance gate for WS-A1D Docker pin authority.

Compares the build-time provenance record (``/opt/engine-provenance.json``,
written by ``docker/*/Dockerfile`` from required build args) against the sole
pin authority (``config/rules_engines.json``) for the configured provider.

Exit codes:
  0 -- provenance matches authority, or no adjudication was possible
       (missing provenance file means a grandfathered/foreign image;
       missing manifest means no authority is mounted; an unconfigured
       provider is owned by downstream fail-closed checks). Warnings go to
       stderr in these cases.
  2 -- usage error (bad arguments).
  3 -- provenance contradicts authority (wrong provider, repository, commit
       or protocol): fail closed so a stale image can never serve as healthy.

Paths and provider default to the container layout but are overridable for
tests. Only the standard library is used.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_MISMATCH = 3

_KNOWN_PROVIDERS = ("xmage", "forge")
_SECTION = {"xmage": "primary_engine", "forge": "secondary_engine"}


def _warn(message: str) -> None:
    print(f"verify_container_provenance: {message}", file=sys.stderr)


def _read_json(path: Path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable JSON: {path} ({exc})") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return payload


def check(provider: str, provenance_path: Path, manifest_path: Path) -> int:
    if provider not in _KNOWN_PROVIDERS:
        _warn(f"ENGINE_PROVIDER {provider!r} is not adjudicated here; leaving to downstream checks")
        return EXIT_OK
    if not provenance_path.is_file():
        _warn(f"no provenance record at {provenance_path}; cannot prove image identity")
        return EXIT_OK
    if not manifest_path.is_file():
        _warn(f"no pin authority mounted at {manifest_path}; cannot adjudicate image identity")
        return EXIT_OK
    try:
        provenance = _read_json(provenance_path)
        manifest = _read_json(manifest_path)
    except ValueError as exc:
        _warn(str(exc))
        return EXIT_MISMATCH
    section = manifest.get(_SECTION[provider])
    if not isinstance(section, dict):
        _warn("pin authority manifest is missing the provider section")
        return EXIT_MISMATCH
    expected = {
        "provider": provider,
        "repository": section.get("repository"),
        "commit": section.get("commit"),
        "protocol_version": manifest.get("protocol_version"),
    }
    mismatches = [
        key for key in expected if provenance.get(key) != expected[key]
    ]
    if mismatches:
        _warn(
            "image provenance contradicts pin authority "
            f"(provider={provider} fields={','.join(sorted(mismatches))}); refusing to start"
        )
        return EXIT_MISMATCH
    return EXIT_OK


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed container provenance gate.")
    parser.add_argument(
        "--provider", default=os.environ.get("ENGINE_PROVIDER", "xmage")
    )
    parser.add_argument(
        "--provenance",
        default=os.environ.get(
            "CONTAINER_PROVENANCE_PATH", "/opt/engine-provenance.json"
        ),
    )
    parser.add_argument(
        "--manifest",
        default=os.environ.get(
            "PIN_MANIFEST_PATH", "/workspace/config/rules_engines.json"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or EXIT_USAGE)
    return check(args.provider, Path(args.provenance), Path(args.manifest))


if __name__ == "__main__":
    raise SystemExit(main())
