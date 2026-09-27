import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_live_active_deck_projection_is_rogshai_only() -> None:
    payload = json.loads(
        (ROOT / "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["active_own_deck_ids"] == ["rogshai/current"]
    assert payload["inactive_former_own_deck_ids"] == []
    assert payload["historical_own_decks"] == []
    assert payload["primary_active_own_deck_id"] == "rogshai/current"
