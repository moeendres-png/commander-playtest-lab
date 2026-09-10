#!/usr/bin/env python3
"""Resolve canonical Docker engine build identity from manifest authority.

WS-A1D pin-authority helper. The sole machine-readable authority for current
engine pins is ``config/rules_engines.json``. This helper stores no pins: it
reads the manifest at runtime and prints the canonical provider repository,
commit, release and bridge protocol version for one provider.

Every authority problem fails closed (non-zero exit, diagnostic on stderr):
unknown provider, missing manifest, malformed manifest, missing section or
field, manifest provider-identity mismatch, non-https repository,
repository/provider cross-wire, malformed commit, or missing protocol version.

Supported Docker builds must obtain their build args through this helper via
``scripts/docker_build_engine.sh``. ``docker/xmage/Dockerfile`` and
``docker/forge/Dockerfile`` declare their build args without defaults and
re-validate them at materialization time, so a stale default can never
silently win.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_REPO = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$")
_KNOWN_PROVIDERS = ("xmage", "forge")
# Provider token that must identify the canonical repository path, and the
# foreign token that must be absent, so an XMage/Forge cross-wire fails closed.
_REPO_TOKEN = {"xmage": "mage", "forge": "forge"}

EXIT_USAGE = 2
EXIT_AUTHORITY = 3


class PinResolutionError(Exception):
    """Raised when canonical authority cannot be resolved safely."""


@dataclass(frozen=True)
class EnginePin:
    provider: str
    repository: str
    commit: str
    release: str
    protocol_version: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_manifest(path: str | Path) -> dict:
    candidate = Path(path)
    if not candidate.is_file():
        raise PinResolutionError(f"pin authority manifest is missing: {candidate}")
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PinResolutionError(f"pin authority manifest is unreadable: {candidate}") from exc
    if not isinstance(payload, dict):
        raise PinResolutionError("pin authority manifest must be a JSON object")
    return payload


def resolve(provider: str, manifest: dict) -> EnginePin:
    """Return the canonical build identity for ``provider`` or fail closed."""
    if provider not in _KNOWN_PROVIDERS:
        raise PinResolutionError(
            f"unsupported provider {provider!r}; expected one of {', '.join(_KNOWN_PROVIDERS)}"
        )
    section_key = "primary_engine" if provider == "xmage" else "secondary_engine"
    section = manifest.get(section_key)
    if not isinstance(section, dict):
        raise PinResolutionError(f"manifest section {section_key!r} is missing or malformed")

    # Manifest provider identity is authoritative: the section itself must
    # declare the requested provider. Section position and repository-name
    # heuristics alone are not sufficient.
    identity = section.get("provider")
    if identity != provider:
        raise PinResolutionError(
            f"manifest {section_key}.provider {identity!r} does not identify "
            f"requested provider {provider!r}"
        )

    repository = section.get("repository")
    if not isinstance(repository, str) or _REPO.fullmatch(repository) is None:
        raise PinResolutionError(
            f"manifest {section_key}.repository is not a valid https engine repository"
        )
    lowered = repository.lower()
    own_token = _REPO_TOKEN[provider]
    foreign_token = _REPO_TOKEN["forge" if provider == "xmage" else "xmage"]
    if own_token not in lowered or foreign_token in lowered:
        raise PinResolutionError(
            f"manifest {section_key}.repository {repository!r} does not identify provider {provider!r}"
        )

    commit = section.get("commit")
    if not isinstance(commit, str) or _HEX40.fullmatch(commit) is None:
        raise PinResolutionError(f"manifest {section_key}.commit is not a full 40-hex commit SHA")

    release = section.get("release")
    if not isinstance(release, str) or not release:
        raise PinResolutionError(f"manifest {section_key}.release is missing")

    protocol = manifest.get("protocol_version")
    if not isinstance(protocol, str) or not protocol:
        raise PinResolutionError("manifest protocol_version is missing")

    return EnginePin(
        provider=provider,
        repository=repository,
        commit=commit,
        release=release,
        protocol_version=protocol,
    )


def format_shell(pin: EnginePin) -> str:
    prefix = pin.provider.upper()
    lines = [
        f"{prefix}_ENGINE_REPOSITORY={pin.repository}",
        f"{prefix}_ENGINE_COMMIT={pin.commit}",
        f"{prefix}_ENGINE_PROTOCOL_VERSION={pin.protocol_version}",
        f"{prefix}_ENGINE_RELEASE={pin.release}",
    ]
    return "\n".join(lines) + "\n"


def format_json(pin: EnginePin) -> str:
    return (
        json.dumps(
            {
                "provider": pin.provider,
                "repository": pin.repository,
                "commit": pin.commit,
                "release": pin.release,
                "protocol_version": pin.protocol_version,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve canonical Docker engine build identity from "
        "config/rules_engines.json (sole pin authority)."
    )
    parser.add_argument("--provider", required=True, help="xmage or forge")
    parser.add_argument(
        "--manifest",
        default=str(repo_root() / "config/rules_engines.json"),
        help="path to the pin authority manifest",
    )
    parser.add_argument(
        "--format",
        choices=("shell", "json"),
        default="shell",
        help="output format (shell KEY=VALUE lines or JSON)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or EXIT_USAGE)
    try:
        pin = resolve(args.provider, load_manifest(args.manifest))
    except PinResolutionError as exc:
        print(f"docker_resolve_engine_pin: {exc}", file=sys.stderr)
        return EXIT_AUTHORITY
    if args.format == "json":
        sys.stdout.write(format_json(pin))
    else:
        sys.stdout.write(format_shell(pin))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
