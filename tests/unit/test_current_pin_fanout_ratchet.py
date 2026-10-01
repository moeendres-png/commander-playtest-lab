"""G1: the live XMage pin may be restated only where nothing can read the manifest.

``config/rules_engines.json`` is the sole machine-readable pin authority. Python
scripts and tests resolve the pin with ``canonical_xmage_engine_pin()``; the
bootstrap scripts resolve it through ``scripts/docker_resolve_engine_pin.py``.
What remains literal is workflow YAML ``env``/``inputs`` (which cannot read a JSON
file at parse time), Java constants, and the deliberate pin-authority guard
tests. This ratchet fails when a new copy of the live pin appears anywhere else
in the active tree, and when a remaining literal consumer drifts from the
manifest. Historical evidence trees (``docs/``, ``qualification/``,
``research/``, ``artifacts/``) are out of scope: they record earlier epochs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from commander_lab.qualification.current_boundary.bridge_launcher import (
    canonical_xmage_engine_pin,
)

ACTIVE_ROOTS = (
    ".devcontainer",
    ".github",
    "config",
    "engine-bridge",
    "scripts",
    "src",
    "tests",
    "tools",
)

ALLOWED_LITERAL_CONSUMERS = frozenset(
    {
        "config/rules_engines.json",
        # YAML env/inputs cannot read the manifest at parse time.
        ".github/workflows/external-engine-integration.yml",
        ".github/workflows/meta-qualification.yml",
        ".github/workflows/xmage-full-game-conformance.yml",
        ".github/workflows/xmage-real-4p-smoke.yml",
        # Compile-time Java identity and its bridge tests.
        "engine-bridge/src/main/java/org/commanderlab/xmage/XmageProvider.java",
        "engine-bridge/src/test/java/org/commanderlab/xmage/JsonlBridgeTest.java",
        "engine-bridge/src/test/java/org/commanderlab/xmage/XmageCandidateEngineFingerprintTest.java",
        # Deliberate pin-authority guards: a repin must change them consciously.
        "tests/qualification/test_xmage_f43_f44_repin_v3_20261001.py",
        "tests/unit/test_ws_a1d_docker_pin_authority.py",
        "tests/unit/test_ws_a1r_pin_authority.py",
        "tests/unit/test_ws_arclose_d1_authority_drift.py",
    }
)


def _files_containing(repo_root: Path, needle: str) -> set[str]:
    proc = subprocess.run(
        ["git", "grep", "-l", "-F", needle, "--", *ACTIVE_ROOTS],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1), proc.stderr
    return {line for line in proc.stdout.splitlines() if line}


def test_no_new_literal_copy_of_the_live_pin(repo_root: Path) -> None:
    holders = _files_containing(repo_root, canonical_xmage_engine_pin())
    unexpected = sorted(holders - ALLOWED_LITERAL_CONSUMERS)
    assert not unexpected, (
        "restates the live XMage pin; resolve it from config/rules_engines.json "
        f"(canonical_xmage_engine_pin / docker_resolve_engine_pin.py): {unexpected}"
    )


def test_every_remaining_literal_consumer_matches_the_manifest(repo_root: Path) -> None:
    pin = canonical_xmage_engine_pin()
    for rel in sorted(ALLOWED_LITERAL_CONSUMERS):
        assert pin in (repo_root / rel).read_text(encoding="utf-8"), rel
