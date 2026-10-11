from __future__ import annotations

from commander_lab.models import EngineCapabilityHandshake


def test_handshake_accepts_the_full_game_lane_player_range() -> None:
    """D5: the full-game lane declares min_players; the strict model must accept it."""
    caps = EngineCapabilityHandshake.model_validate(
        {"min_players": 2, "max_players": 6, "runtime_kind": "external_rules_engine"}
    )
    assert (caps.min_players, caps.max_players) == (2, 6)


def test_handshake_still_rejects_unknown_capability_keys() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EngineCapabilityHandshake.model_validate({"invented_capability": True})


def test_handshake_rejects_an_inverted_or_solo_player_range() -> None:
    import pytest
    from pydantic import ValidationError

    for payload in ({"min_players": 6, "max_players": 2}, {"min_players": 1}):
        with pytest.raises(ValidationError):
            EngineCapabilityHandshake.model_validate(payload)
