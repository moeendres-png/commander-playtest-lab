"""Canonical qualified OpenCode CLI version source (single pin authority).

WS75: exactly one machine-readable source names the qualified OpenCode CLI:
``QUALIFIED_OPENCODE_VERSION = "1.18.30"``. The launcher (and bootstrap when
given a binary) resolves the installed CLI via ``<binary> --version`` and
fails closed on any drift, except an explicit bounded version-audit mode
used for migration/audit runs. Nothing here floats ``latest``.

Immutable release assets (verified 2026-09-12 by direct download +
``sha256sum`` against the release tag ``v1.18.30``, published 2026-09-09):

- linux x64 / arm64 tarballs below carry DIRECTLY_VERIFIED SHA256 digests.
- Other platforms resolve through :func:`asset_url` (same immutable tag
  path) but carry no recorded digest here until verified the same way;
  consumers must verify before trusting them.

Official CLI/version behaviour (opencode.ai docs, fetched 2026-09-12,
pages last updated 2026-09-10) is recorded in
``research/foundry/ws75-opencode-tooling-hardening/OPENCODE_DOCS_2026-09-12.md``.
"""

from __future__ import annotations

import re
import subprocess

QUALIFIED_OPENCODE_VERSION = "1.18.30"
QUALIFIED_RELEASE_TAG = "v1.18.30"
QUALIFIED_RELEASE_PUBLISHED_UTC = "2026-09-09T03:34:27Z"
QUALIFIED_RELEASE_REPO = "sst/opencode"

_ASSET_BASE = (
    f"https://github.com/{QUALIFIED_RELEASE_REPO}/releases/download/{QUALIFIED_RELEASE_TAG}"
)

# platform -> {asset, sha256|None, verified}. Only entries with
# verified=True were hashed locally from the immutable asset.
ASSETS: dict[str, dict[str, object]] = {
    "linux-x64": {
        "asset": "opencode-linux-x64.tar.gz",
        "sha256": "55007246858165496ff85ba1c2b648f7421e8e2013bf4189a680c9ff8e699d17",
        "verified": True,
    },
    "linux-arm64": {
        "asset": "opencode-linux-arm64.tar.gz",
        "sha256": "4111a55c2a02c0fac314bd51e9a2330280e6d29d2b85b9554fff6d62612566ed",
        "verified": True,
    },
}

_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")


class VersionCheckError(RuntimeError):
    """Installed CLI version cannot be established or does not match."""


def asset_url(platform: str, version: str = QUALIFIED_OPENCODE_VERSION) -> str:
    """Immutable per-tag asset URL (no ``latest`` indirection)."""
    base = f"https://github.com/{QUALIFIED_RELEASE_REPO}/releases/download/v{version}"
    if platform in ASSETS:
        return f"{base}/{ASSETS[platform]['asset']}"
    raise VersionCheckError(f"no recorded asset for platform {platform!r}")


def installed_version(binary: str) -> str:
    """Return the exact ``X.Y.Z`` reported by ``<binary> --version``.

    Raises VersionCheckError when the binary is missing, fails, or emits
    no parseable version. Never guesses.
    """
    try:
        proc = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, check=False, timeout=60
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VersionCheckError(f"cannot execute {binary!r} --version: {exc}") from exc
    if proc.returncode != 0:
        raise VersionCheckError(
            f"{binary!r} --version exited {proc.returncode}: {(proc.stderr or proc.stdout).strip()[:200]}"
        )
    match = _VERSION_RE.search(proc.stdout.strip())
    if not match:
        raise VersionCheckError(f"{binary!r} --version unparseable: {proc.stdout.strip()[:200]!r}")
    return match.group(1)


def verify(binary: str, expected: str = QUALIFIED_OPENCODE_VERSION) -> dict:
    """Compare installed vs expected. ``ok`` True only on exact equality."""
    found = installed_version(binary)
    return {
        "binary": binary,
        "expected": expected,
        "installed": found,
        "ok": found == expected,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Verify the qualified OpenCode CLI version.")
    parser.add_argument("--binary", default="opencode")
    parser.add_argument("--expected", default=QUALIFIED_OPENCODE_VERSION)
    args = parser.parse_args(argv)
    try:
        result = verify(args.binary, args.expected)
    except VersionCheckError as exc:
        print(f"OPENCODE_VERSION_FAIL: {exc}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["ok"]:
        print(
            f"OPENCODE_VERSION_FAIL: installed {result['installed']!r} != "
            f"qualified {result['expected']!r}",
        )
        return 1
    print(f"OPENCODE_VERSION_OK: {result['installed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
