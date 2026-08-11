import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_playstyle_preference_is_soft_not_archetype_ban() -> None:
    payload = json.loads(
        (ROOT / "data/collections/current/PLAYSTYLE_PREFERENCE_CURRENT.json").read_text(encoding="utf-8")
    )
    assert payload["preference_type"] == "soft_practicality_and_fun_preference"
    assert "archetype_ban" in payload["explicitly_not"]
    assert "ban_on_engines_or_combos" in payload["explicitly_not"]
