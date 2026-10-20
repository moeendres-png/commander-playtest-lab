"""Read the games of a ``pilot_decision_report.py`` report for the card analyses.

The report written by ``pilot_decision_report.py run`` has ``games`` rows. An ``ok`` row carries
``players``, ``winners`` (a list of 1-based seats, the same numbering as ``per_card[*].seat``) and
``per_card`` entries ``{"seat", "card", "cast", ...}``. A card counts as played by a seat when it
was cast at least once; a card that was only offered is not played.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def ok_games(report: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Per finished game: ``players``, ``winners`` (set of seats) and ``cards_by_seat``.

    Failed games and rows without a ``winners`` list are skipped; they carry no outcome.
    """
    for game in report.get("games", []):
        if game.get("status") != "ok" or not isinstance(game.get("winners"), list):
            continue
        players = int(game.get("players") or 0)
        cards_by_seat: dict[int, set[str]] = {seat: set() for seat in range(1, players + 1)}
        for entry in game.get("per_card", []):
            seat = entry.get("seat")
            name = entry.get("card")
            if seat in cards_by_seat and name and (entry.get("cast") or 0) > 0:
                cards_by_seat[seat].add(str(name))
        yield {
            "players": players,
            "winners": {int(seat) for seat in game["winners"]},
            "cards_by_seat": cards_by_seat,
        }
