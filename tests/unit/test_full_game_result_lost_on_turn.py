"""``lost_on_turn`` in a game result is public information outside the semantic hash (#874)."""

from __future__ import annotations

import copy
from typing import Any

from commander_lab.engine.rules.full_game import XmageFullGameRunner


def _result() -> dict[str, Any]:
    return {
        "seed": 7,
        "turn_number": 31,
        "decision_count": 12,
        "transcript": [],
        "outcomes": [
            {"seat": 0, "life": 12, "won": True, "lost": False, "left": False},
            {"seat": 1, "life": 0, "won": False, "lost": True, "left": False},
            {"seat": 2, "life": 0, "won": False, "lost": True, "left": False},
        ],
    }


def test_lost_on_turn_does_not_change_the_semantic_transcript() -> None:
    plain = _result()
    with_turns = copy.deepcopy(plain)
    for outcome, turn in zip(with_turns["outcomes"], (None, 24, 17), strict=True):
        outcome["lost_on_turn"] = turn
    assert XmageFullGameRunner.semantic_transcript(
        with_turns
    ) == XmageFullGameRunner.semantic_transcript(plain)
    assert XmageFullGameRunner._sha256(
        XmageFullGameRunner.semantic_transcript(with_turns)
    ) == XmageFullGameRunner._sha256(XmageFullGameRunner.semantic_transcript(plain))
