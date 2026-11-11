"""A stale bridge build is named in the public error, without the commits or other text.

The full-game handshake refuses a bridge built from another engine commit. Before this
site was public, the Studio showed only "full-game diagnostics redacted", which hid the
one actionable cause (re-stage the bridge jar). Only the fixed prefix is published.
"""

from __future__ import annotations

from commander_lab.engine.rules.failure_privacy import public_full_game_message

STALE = "2ec507b721ac04834eaa4d553b494681c46d996f"
PINNED = "f4d12f6e8066203fba7aa38bd35ea3358117393d"


def test_commit_mismatch_publishes_the_fixed_site_only() -> None:
    raw = f"XMage commit mismatch: scenario={PINNED} provider={STALE} Honeycard Sentinel"
    message = public_full_game_message(raw)
    assert message.startswith("XMage commit mismatch: ENGINE_FAILURE")
    assert STALE not in message
    assert PINNED not in message
    assert "Honeycard" not in message


def test_the_site_must_lead_the_message() -> None:
    # Negative control: the phrase inside another message does not become the site.
    message = public_full_game_message("engine said: XMage commit mismatch somewhere")
    assert not message.startswith("XMage commit mismatch")
