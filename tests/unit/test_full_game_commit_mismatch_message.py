"""A stale bridge build is named in the public error, without the commits or other text.

The full-game handshake refuses a bridge built from another engine commit. Before this
site was public, the Studio showed only "full-game diagnostics redacted", which hid the
one actionable cause (re-stage the bridge jar). Only the fixed prefix is published.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from commander_lab.engine.rules.failure_privacy import public_full_game_message
from commander_lab.engine.rules.full_game import FullGameConformanceError
from commander_lab.studio.play import play_recorded_game

STALE = "2" * 40
PINNED = "1" * 40
VALID_HASH = "a" * 64


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


def test_play_recorded_game_failure_captures_redacted_message(tmp_path: Path) -> None:
    mock_runner = MagicMock()
    mock_runner.run.side_effect = FullGameConformanceError(
        f"XMage commit mismatch: scenario={PINNED} provider={STALE} secret_deck_leak"
    )

    with (
        patch("commander_lab.studio.play._RecordingRunner", return_value=mock_runner),
        patch(
            "commander_lab.studio.play.load_decks",
            return_value=(
                MagicMock(deck_id="d1", deck_hash=VALID_HASH, commander_names=["C1"]),
                MagicMock(deck_id="d2", deck_hash=VALID_HASH, commander_names=["C2"]),
            ),
        ),
    ):
        result = play_recorded_game(
            data_folder=tmp_path,
            deck_paths=[Path("deck1.json"), Path("deck2.json")],
            seed=42,
            game_id="test-fail-game",
        )

    assert result["status"] == "failed"
    assert result["failure_class"] == "RuntimeError"
    failure_msg = str(result["failure_message"])
    assert failure_msg.startswith("XMage commit mismatch: ENGINE_FAILURE")
    assert "secret_deck_leak" not in failure_msg
