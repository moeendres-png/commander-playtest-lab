"""The binding engine check of the deck builder ("Prüfung durch die Engine").

The data check of the builder reads stored card facts. This check asks what the game
runner asks before a game: the full-game runner's deck construction validation
(``_validate_deck_construction``: hash, duplicates, colour identity) and the list of cards the
pinned rules engine cannot load. It starts no game. XMage's own deck import still runs when a
game starts and is not part of this check.

Three outcomes, never more: ``FAIL`` (something was found), ``PASS`` (the runner's validation
and the card list find nothing and the engine is provisioned) and ``UNKNOWN`` (nothing found,
but the engine is not provisioned, so the check is not binding). UNKNOWN is never shown as
green.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path

LABEL = "Prüfung durch die Engine"
SCHEMA = "studio-engine-check-1"
UNKNOWN_HEADLINE = "nicht geprüft: Engine nicht bereitgestellt"


def _deck_input(rows: Sequence[Mapping[str, object] | sqlite3.Row]) -> object:
    from commander_lab.models import RulesDeckInput
    from commander_lab.studio.play import _with_hash

    def name(row: Mapping[str, object] | sqlite3.Row) -> str:
        return str(row["engine_name"] or row["oracle_name"])

    commanders = tuple(name(row) for row in rows if row["zone"] == "commander")
    mainboard: list[str] = []
    for row in rows:
        if row["zone"] != "commander":
            mainboard.extend([name(row)] * int(str(row["quantity"])))
    deck = RulesDeckInput(
        deck_id="studio-entwurf",
        name="Entwurf",
        commander_names=commanders,
        mainboard=tuple(mainboard),
        sideboard=(),
    )
    return _with_hash(deck)


def construction_check(rows: Sequence[Mapping[str, object] | sqlite3.Row]) -> dict[str, object]:
    """Run the runner's own ``_validate_deck_construction`` on the deck rows."""
    from commander_lab.engine.rules.full_game import (
        FullGameConformanceError,
        _validate_deck_construction,
    )

    try:
        _validate_deck_construction(_deck_input(rows))  # type: ignore[arg-type]
    except FullGameConformanceError as error:
        message = str(error)
        code = message.split(":", 1)[0].strip()
        return {"status": "FAIL", "code": code, "message": message}
    return {"status": "PASS", "code": None, "message": ""}


def check_rows(
    rows: Sequence[Mapping[str, object] | sqlite3.Row], data_folder: str | Path
) -> dict[str, object]:
    """The whole check for deck rows (``decks.list_rows`` / ``revision_rows``)."""
    from commander_lab.studio import launch

    snapshot: dict[str, object] = {
        "cards": [
            {
                "oracle_name": str(row["engine_name"] or row["oracle_name"]),
                "quantity": int(str(row["quantity"])),
                "zone": str(row["zone"]),
            }
            for row in rows
        ]
    }
    construction = construction_check(rows)
    unsupported = launch.cards_unsupported_by_engine(snapshot)
    unknown = launch.cards_unknown_to_pilots(snapshot)
    ready = launch.engine_command(data_folder) is not None
    found = construction["status"] == "FAIL" or bool(unsupported) or bool(unknown)
    if found:
        status, headline = "FAIL", "Die Engine würde dieses Deck nicht annehmen"
    elif ready:
        status, headline = "PASS", "Die Prüfung der Engine findet nichts"
    else:
        status, headline = "UNKNOWN", UNKNOWN_HEADLINE
    return {
        "schema": SCHEMA,
        "label": LABEL,
        "status": status,
        "headline": headline,
        "engine_ready": ready,
        "construction": construction,
        "unsupported_by_engine": unsupported,
        "unknown_to_pilots": unknown,
        "meaning": (
            "Geprüft wird, was der Spielstarter vor einer Partie prüft: Hash, Einzelkarten-Regel "
            "und Farbidentität sowie die Karten, die die Engine nicht laden kann. Es wird keine "
            "Partie gestartet. Den Deck-Import selbst macht XMage erst beim Spielstart."
        ),
    }
