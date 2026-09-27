#!/usr/bin/env python3
"""Container provenance gate for WS-A1D Docker pin authority (fail closed).

Compares the build-time provenance record (``/opt/engine-provenance.json``,
written by ``docker/*/Dockerfile`` from required build args) against the sole
pin authority (``config/rules_engines.json``) for the configured provider.

Forge carries dual identity: besides the Rules-Core provider/repository/commit,
the gate also compares the bridge/materialization repository, commit and
Rules-Core base commit against ``secondary_engine.bridge_source``. A Forge
image without a conforming bridge_source claim fails closed.

The supported container path must prove image identity before the engine may
start. Every case where identity CANNOT be proven stops startup non-zero:

  * unknown or missing ``ENGINE_PROVIDER``;
  * missing or unreadable provenance record;
  * missing or unreadable pin manifest;
  * provider, repository, commit or protocol_version contradiction;
  * (forge) bridge/materialization repository, commit or base contradiction,
    or bridge_source absent from authority.

Exit codes:
  0 -- provenance matches authority on every compared field.
  2 -- usage error (bad arguments).
  3 -- fail closed: identity unproven or contradicted. Diagnostics go to
       stderr. There is no grandfathered/foreign-image exception: legacy
       containers require a separately authorized compatibility path.

Only the standard library is used.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_FAIL_CLOSED = 3

_KNOWN_PROVIDERS = ("xmage", "forge")
_SECTION = {"xmage": "primary_engine", "forge": "secondary_engine"}


def _fail(message: str) -> int:
    print(f"verify_container_provenance: FAIL CLOSED: {message}", file=sys.stderr)
    return EXIT_FAIL_CLOSED


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
        return _fail(f"ENGINE_PROVIDER {provider!r} is not a supported provider; refusing to start")
    if not provenance_path.is_file():
        return _fail(f"no provenance record at {provenance_path}; image identity cannot be proven")
    if not manifest_path.is_file():
        return _fail(f"no pin authority at {manifest_path}; image identity cannot be adjudicated")
    try:
        provenance = _read_json(provenance_path)
        manifest = _read_json(manifest_path)
    except ValueError as exc:
        return _fail(str(exc))
    section = manifest.get(_SECTION[provider])
    if not isinstance(section, dict):
        return _fail("pin authority manifest is missing the provider section")
    expected = {
        "provider": provider,
        "repository": section.get("repository"),
        "commit": section.get("commit"),
        "protocol_version": manifest.get("protocol_version"),
    }
    mismatches = [key for key in expected if provenance.get(key) != expected[key]]
    if mismatches:
        return _fail(
            "image provenance contradicts pin authority "
            f"(provider={provider} fields={','.join(sorted(mismatches))})"
        )
    if provider == "forge":
        # Dual identity: the materialization/bridge source must independently
        # match secondary_engine.bridge_source, whose Rules-Core base must equal
        # the Rules pin (cross-wiring either level fails closed here too).
        bridge = section.get("bridge_source")
        if not isinstance(bridge, dict):
            return _fail(
                "pin authority manifest is missing secondary_engine.bridge_source; "
                "Forge dual identity cannot be proven"
            )
        if bridge.get("rules_core_base_commit") != section.get("commit"):
            return _fail(
                "pin authority bridge_source.rules_core_base_commit does not equal "
                "the Rules-Core pin; materialization source and Rules pin are cross-wired"
            )
        bridge_expected = {
            "bridge_repository": bridge.get("repository"),
            "bridge_commit": bridge.get("commit"),
            "rules_core_base_commit": bridge.get("rules_core_base_commit"),
        }
        bridge_mismatches = [
            key for key in bridge_expected if provenance.get(key) != bridge_expected[key]
        ]
        if bridge_mismatches:
            return _fail(
                "image bridge provenance contradicts pin authority "
                f"(provider={provider} fields={','.join(sorted(bridge_mismatches))})"
            )
    return EXIT_OK


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed container provenance gate.")
    parser.add_argument("--provider", default=os.environ.get("ENGINE_PROVIDER", ""))
    parser.add_argument(
        "--provenance",
        default=os.environ.get("CONTAINER_PROVENANCE_PATH", "/opt/engine-provenance.json"),
    )
    parser.add_argument(
        "--manifest",
        default=os.environ.get("PIN_MANIFEST_PATH", "/workspace/config/rules_engines.json"),
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
