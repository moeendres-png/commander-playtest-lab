import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_live_scope_separates_global_active_runtime_and_unresolved_baseline() -> None:
    payload = json.loads(
        (ROOT / "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["global_active_own_decks"] == ["korvold/current", "rogshai/current"]
    assert payload["runtime_loaded_decks"] == ["rogshai/current"]
    assert payload["optimization_targets"] == ["rogshai/current"]
    assert payload["unresolved_operational_baselines"] == ["korvold/current"]
    # Backward-compatible active_own_deck_ids means runtime-loaded, not global ownership.
    assert payload["active_own_deck_ids"] == ["rogshai/current"]
    assert payload["inactive_former_own_deck_ids"] == []
    assert payload["korvold_optimization_target"] is False
    assert payload["korvold_simultaneous_build_requirement"] is True
    assert payload["korvold_historical_list_is_current_baseline"] is False
