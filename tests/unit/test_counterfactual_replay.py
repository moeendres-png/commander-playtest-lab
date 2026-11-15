from __future__ import annotations

import json
from pathlib import Path


def _write_replay(root: Path, *, eliminated: bool = False) -> str:
    target = root / "data/runs/counterfactual/source/events/example.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "event_type": "game_started",
            "game_id": "g1",
            "sequence": 0,
            "actor_id": None,
            "payload": {"seed": 17},
        },
        {
            "event_type": "state_checkpoint",
            "game_id": "g1",
            "sequence": 1,
            "actor_id": None,
            "payload": {"reason": "before_decision", "players": [{"player_id": "p1", "life": 40}]},
        },
    ]
    if eliminated:
        rows.append(
            {
                "event_type": "player_eliminated",
                "game_id": "g1",
                "sequence": 2,
                "actor_id": "p1",
                "payload": {},
            }
        )
    rows.append(
        {
            "event_type": "pilot_decision",
            "game_id": "g1",
            "sequence": len(rows),
            "actor_id": "p1",
            "payload": {
                "phase": "counter",
                "selected_action_id": "counter:Kaervek",
                "selected_utility": 2.0,
                "candidates": [["counter:Kaervek", 2.0], ["pass", 3.5], ["counter:Value", 1.0]],
            },
        }
    )
    target.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8"
    )
    return str(target.relative_to(root))
