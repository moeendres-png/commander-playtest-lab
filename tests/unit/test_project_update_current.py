import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_current_project_update_did_not_change_deck_or_opponent_truth() -> None:
    payload = json.loads(
        (ROOT / "data/collections/current/PROJECT_UPDATE_CURRENT.json").read_text(encoding="utf-8")
    )
    assert payload["active_own_decks"] == ["rogshai/current"]
    assert payload["rogshai_decklist_changed"] is False
    assert payload["korvold_historical_list_preserved"] is True
    assert payload["opponent_truth_changed"] is False
    assert payload["kaervek_status_changed"] is False
