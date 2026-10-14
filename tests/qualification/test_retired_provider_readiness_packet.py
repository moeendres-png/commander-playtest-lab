"""The retired two-candidate provider readiness packet stays byte-identical.

Its generator read the Forge pins from ``config/rules_engines.json``, which no
longer carries a secondary engine since Forge was removed (Owner decision
2026-10-13), so the packet is no longer regenerated or re-derived. It remains
the historical record of the pre-Freeze comparison, and these digests make any
edit to it visible.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

PACKET = Path(__file__).resolve().parents[2] / "docs/provider_readiness_packet_20261007"
DIGESTS = {
    "PROVIDER_READINESS.json": "8d84f5d3d37a850b5d652798873a5271db9c8fadc2d9a015a0d0f2c4c7cc9e61",
    "PROVIDER_READINESS.md": "553d5115d074373259468d9767c486132a1a4524caa7d1f6c8f9c5922ae9992e",
    "COORDINATOR_ADJUDICATION.md": (
        "2e4aeb2b6eaa4d153c6cfa7dac776987d3036530e6a48708cbc3b7142620fffc"
    ),
}


@pytest.mark.parametrize(("name", "digest"), sorted(DIGESTS.items()))
def test_the_historical_packet_is_unchanged(name: str, digest: str) -> None:
    assert hashlib.sha256((PACKET / name).read_bytes()).hexdigest() == digest


def test_the_packet_is_marked_retired() -> None:
    note = (PACKET / "RETIRED.md").read_text(encoding="utf-8")
    assert "not regenerated" in note
    assert not (PACKET.parents[1] / "scripts/build_provider_readiness_packet.py").exists()
