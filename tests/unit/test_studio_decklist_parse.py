"""Pasted deck lists: a status for every line, export annotations, no silent drops (#1404 D5)."""

from __future__ import annotations

from pathlib import Path

from commander_lab.studio import StudioStore
from commander_lab.studio.decks import parse_decklist_text

TEXT = """Commander
1 Test Commander *CMDR*
Deck
1x Filler 01 (C21) 263 *F*
1 Filler 02 [Ramp] ^Have^
2 Filler 03
1 Red Outsider
1 Banned Relic
2 Reserved Bear
1 Black Lotus
0 Island
?? !!
5 Swarm Rat # mehr Ratten
Sideboard
1 Filler 04
"""


def _store(tmp_path: Path) -> StudioStore:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    return store


def test_every_line_gets_a_status_and_nothing_is_dropped_silently(tmp_path: Path) -> None:
    result = parse_decklist_text(_store(tmp_path), ["Test Commander"], TEXT)
    statuses = [(line["line"], line["status"]) for line in result["lines"]]
    assert statuses == [
        (2, "commander"),
        (4, "matched"),
        (5, "matched"),
        (6, "insufficient"),  # 2 asked, 1 free: the free one is taken
        (7, "outside_identity"),
        (8, "not_legal"),
        (9, "insufficient"),  # Reserved Bear: 0 free (1 reserved)
        (10, "not_in_collection"),
        (11, "unreadable"),
        (12, "unreadable"),
        (13, "matched"),
        (15, "skipped_section"),
    ]
    by_line = {line["line"]: line for line in result["lines"]}
    assert by_line[4]["ignored"] == ["Foil/Etched-Markierung", "Druckangabe (C21)"]
    assert by_line[5]["ignored"] == ["Archidekt-Kategorie", "Archidekt-Markierung"]
    assert by_line[13]["ignored"] == ["Kommentar"]
    assert by_line[2]["ignored"] == ["Commander-Markierung (Deckstats)"]
    assert (by_line[6]["taken"], by_line[9]["taken"]) == (1, 0)
    taken = {row["name"]: row["quantity"] for row in result["in_collection"]}
    assert taken == {"Filler 01": 1, "Filler 02": 1, "Filler 03": 1, "Swarm Rat": 5}
    # The old reading listed out-of-identity and illegal cards as "not in your collection".
    assert [row["name"] for row in result["not_in_collection"]] == ["Black Lotus"]
    assert [row["name"] for row in result["outside_color_identity"]] == ["Red Outsider"]
    assert [row["name"] for row in result["not_legal"]] == ["Banned Relic"]
    assert result["summary"]["list_cards"] == 9  # 8 cards plus the commander
    raw = str(result).casefold()
    for forbidden in ("kaufen", "zukauf", "preis", "€", "$"):
        assert forbidden not in raw


def test_a_commander_line_naming_another_card_is_not_taken(tmp_path: Path) -> None:
    result = parse_decklist_text(_store(tmp_path), ["Test Commander"], "Commander\n1 Filler 05\n")
    assert [line["status"] for line in result["lines"]] == ["other_commander"]
    assert result["in_collection"] == []
