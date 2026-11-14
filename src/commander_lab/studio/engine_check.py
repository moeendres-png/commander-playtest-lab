"""The binding engine check of the deck builder ("Prüfung durch die Engine").

The data check of the builder reads stored card facts. This check asks what the game
runner asks before a game: the full-game runner's deck construction validation
(``_validate_deck_construction``: hash, duplicates, colour identity) and the list of cards the
pinned rules engine cannot load. It starts no game. XMage's own deck import still runs when a
game starts and is not part of this check.

Three outcomes, never more: ``FAIL`` (something was found), ``PASS`` and ``UNKNOWN``.
``PASS`` needs all three at once: the runner's construction validation really ran and found
nothing, the engine's card list was really consulted and found nothing, and the engine is
really provisioned (its command resolves and the jar it names is a file). Anything else that
found no defect is ``UNKNOWN``, never green. A deck the Studio can already tell is unfit for
the runner (not exactly 100 cards, no commander) names that as a failed precondition.
"""

from __future__ import annotations

import os
import shlex
import shutil
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path

LABEL = "Prüfung durch die Engine"
SCHEMA = "studio-engine-check-1"
_CODE_TEXT = {
    "deck_hash_mismatch": "Die Prüfsumme passt nicht zum Inhalt.",
    "deck_duplicate_card": "Eine Karte außer Standardländern ist mehrfach im Deck.",
    "deck_color_identity_violation": (
        "Mindestens eine Karte liegt außerhalb der Farbidentität des Commanders."
    ),
    "deck_color_identity_unknown": (
        "Für mindestens eine Karte kennt der Spielstarter keine Farbidentität."
    ),
    "deck_not_buildable": "Das Deck hat nicht genau 100 Karten; die Prüfung des Starters ist nicht möglich.",
}
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
    from pydantic import ValidationError

    from commander_lab.engine.rules.full_game import (
        FullGameConformanceError,
        _validate_deck_construction,
    )

    try:
        deck = _deck_input(rows)
    except ValidationError as error:
        # the runner's deck model takes exactly 100 cards: a draft of another size cannot be put
        # through its validation, which is "not checked", never a pass
        reason = "; ".join(str(item["msg"]) for item in error.errors())
        return {
            "status": "NOT_CHECKED",
            "code": "deck_not_buildable",
            "message": reason,
            "text": _CODE_TEXT["deck_not_buildable"],
        }
    try:
        _validate_deck_construction(deck)  # type: ignore[arg-type]
    except FullGameConformanceError as error:
        message = str(error)
        code = message.split(":", 1)[0].strip()
        return {
            "status": "FAIL",
            "code": code,
            "message": message,
            "text": _CODE_TEXT.get(code, "Der Spielstarter lehnt das Deck ab."),
        }
    return {"status": "PASS", "code": None, "message": "", "text": ""}


_JAVA_MAJOR_CACHE: dict[tuple[str, int], int | None] = {}


def _java_major_cached(java: str) -> int | None:
    """The Java major version, probed once per process for one binary (path and mtime)."""
    from commander_lab.studio import launch

    try:
        key = (java, os.stat(java).st_mtime_ns)
    except OSError:
        return None
    if key not in _JAVA_MAJOR_CACHE:
        _JAVA_MAJOR_CACHE[key] = launch._java_major(java)
    return _JAVA_MAJOR_CACHE[key]


def _runnable(token: str) -> bool:
    if os.sep in token or (os.altsep and os.altsep in token):
        return os.path.isfile(token) and os.access(token, os.X_OK)
    return shutil.which(token) is not None


def engine_readiness(data_folder: str | Path) -> tuple[bool, str]:
    """Whether the engine is really provisioned for this check, and the reason when not.

    With the environment command the program must resolve and a jar it names (``-jar``) must
    be a file. Otherwise the jar of the data folder must exist and a Java of at least the
    minimum version must be found. Nothing here starts a game."""
    from commander_lab.studio import launch

    raw = os.environ.get(launch.ENGINE_COMMAND_ENV, "").strip()
    if raw:
        try:
            command = shlex.split(raw, posix=(os.name != "nt"))
        except ValueError:
            return False, "Der Startbefehl der Engine ist nicht lesbar."
        if not command or not _runnable(command[0]):
            shown = command[0] if command else raw
            return False, f"Das Startprogramm der Engine ist nicht vorhanden: {shown}"
        if "-jar" in command:
            at = command.index("-jar") + 1
            if at >= len(command) or not os.path.isfile(command[at]):
                shown = command[at] if at < len(command) else "(fehlt)"
                return False, f"Die Engine-Datei ist nicht vorhanden: {shown}"
        return True, ""
    jar = Path(data_folder) / launch.ENGINE_JAR
    if not jar.is_file():
        return False, f"Die Engine-Datei fehlt: {jar}"
    java = launch._java_executable()
    if not java:
        return False, "Java ist nicht installiert (Java 17 oder neuer)."
    major = _java_major_cached(java)
    if major is None:
        return False, "Die Java-Version ist nicht lesbar."
    if major < launch.MIN_JAVA_MAJOR:
        return False, f"Java ist zu alt: Version {major}, nötig ist {launch.MIN_JAVA_MAJOR}."
    return True, ""


def preconditions(rows: Sequence[Mapping[str, object] | sqlite3.Row]) -> list[str]:
    """What the Studio can already decide: a deck of another size or without a commander
    cannot go through the runner's validation."""
    total = sum(int(str(row["quantity"])) for row in rows)
    commanders = sum(int(str(row["quantity"])) for row in rows if row["zone"] == "commander")
    found: list[str] = []
    if total != 100:
        found.append(f"Das Deck hat {total} statt 100 Karten.")
    if commanders == 0:
        found.append("Das Deck hat keinen Commander.")
    elif commanders > 2:
        found.append("Das Deck hat mehr als zwei Commander.")
    return found


def check_rows(
    rows: Sequence[Mapping[str, object] | sqlite3.Row], data_folder: str | Path
) -> dict[str, object]:
    """The whole check for deck rows (``decks.list_rows`` / ``revision_rows``)."""
    from commander_lab.studio import builder, launch

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
    failed_preconditions = preconditions(rows)
    construction = construction_check(rows)
    consulted = builder.sim_readiness_available()
    unsupported = launch.cards_unsupported_by_engine(snapshot) if consulted else []
    unknown = launch.cards_unknown_to_pilots(snapshot) if consulted else []
    ready, reason = engine_readiness(data_folder)
    found = construction["status"] == "FAIL" or bool(unsupported) or bool(unknown)
    if found:
        status, headline = "FAIL", "Die Engine würde dieses Deck nicht annehmen"
    elif failed_preconditions:
        status, headline = "UNKNOWN", "nicht geprüft: Voraussetzung nicht erfüllt"
    elif construction["status"] != "PASS":
        status, headline = "UNKNOWN", "nicht geprüft: Deck-Aufbau nicht prüfbar"
    elif not ready:
        status, headline = "UNKNOWN", UNKNOWN_HEADLINE
    elif not consulted:
        status, headline = "UNKNOWN", "nicht geprüft: Kartenliste der Engine nicht lesbar"
    else:
        status, headline = "PASS", "Die Prüfung der Engine findet nichts"
    return {
        "schema": SCHEMA,
        "label": LABEL,
        "status": status,
        "headline": headline,
        "engine_ready": ready,
        "engine_reason": reason,
        "cards_consulted": consulted,
        "precondition_failures": failed_preconditions,
        "construction": construction,
        "unsupported_by_engine": unsupported,
        "unknown_to_pilots": unknown,
        "meaning": (
            "Geprüft wird, was der Spielstarter vor einer Partie prüft: Prüfsumme, Einzelkarten-Regel "
            "und Farbidentität sowie die Karten, die die Engine nicht laden kann. Es wird keine "
            "Partie gestartet. Den Deck-Import selbst macht XMage erst beim Spielstart. "
            "„Bestanden“ gilt nur, wenn alle drei Teile wirklich gelaufen sind und nichts fanden: "
            "der Deck-Aufbau, die Kartenliste und eine vorhandene Engine."
        ),
    }
