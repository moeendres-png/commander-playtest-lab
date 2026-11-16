"""Hardening of the universal deck-list import (Refs #1404): linear time, BOM, no echoed
amounts, typographic characters, quantity bounds, back-face names, oversize baseline ids."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from commander_lab.studio import DataClass, StudioStore, decks

CMD = ["Chulane, Teller of Tales"]


@pytest.fixture()
def store(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path / "studio")
    src = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE,
        title="coll.csv",
        sha256="a" * 64,
        snapshot_date="2026-11-10",
    )
    cards = [
        ("cmd-chulane", "Chulane, Teller of Tales", "GWU"),
        ("c-sol", "Sol Ring", ""),
        ("c-signet", "Arcane Signet", ""),
        ("c-counter", "Counterspell", "U"),
        ("c-island", "Island", "U"),
        ("c-mantra", "Ajani's Mantra", "W"),
        ("c-squire", "Faithful Squire // Kaiso, Memory of Loyalty", "U"),
    ]
    with store.connection as db:
        for cid, name, identity in cards:
            db.execute(
                "INSERT INTO card (card_id, oracle_id, oracle_name, color_identity, mana_cost, "
                "mana_value, type_line, oracle_text, is_basic_land, commander_legal, "
                "legality_verified_at, identity_evidence, source_id) "
                "VALUES (?, ?, ?, ?, '{1}', 1, 'Card', '', 0, 1, '2026-11-10', 'scryfall', ?)",
                (cid, "oid-" + cid, name, identity, src),
            )
            db.execute(
                "INSERT INTO inventory VALUES (?, 1, 2, 0, 2, 1, 1, '2026-11-10', ?)",
                (cid, src),
            )
    return store


def _names(parsed: dict[str, object], bucket: str = "in_collection") -> list[str]:
    entries = parsed[bucket]
    assert isinstance(entries, list)
    return [str(e["name"]) for e in entries]


def test_decorator_input_is_linear_time(store: StudioStore) -> None:
    started = time.perf_counter()
    parsed = decks.parse_decklist_text(store, CMD, " *a*" * 20000)
    assert time.perf_counter() - started < 2
    unrecognized = parsed["unrecognized_lines"]
    assert isinstance(unrecognized, list)
    assert len(unrecognized) == 1
    assert unrecognized[0]["status"] == "zu lang"
    assert len(str(unrecognized[0]["raw"])) <= 300


def test_too_many_lines_is_refused_with_german_error(store: StudioStore) -> None:
    with pytest.raises(ValueError, match="zu lang"):
        decks.parse_decklist_text(store, CMD, "1 Sol Ring\n" * 2001)


def test_bom_plain_and_csv(store: StudioStore) -> None:
    plain = decks.parse_decklist_text(store, CMD, "﻿1 Sol Ring")
    assert _names(plain) == ["Sol Ring"]
    parsed = decks.parse_decklist_text(store, CMD, "﻿Count,Name\n3,Sol Ring")
    assert parsed["detected_format"] == "csv"
    matched = parsed["in_collection"]
    assert isinstance(matched, list)
    assert [(m["name"], m["quantity"]) for m in matched] == [("Sol Ring", 3)]


@pytest.mark.parametrize(
    "line",
    [
        "1 Sol Ring $1.20",
        "1 Sol Ring 1,20 €",
        "1 Sol Ring 0.75 USD",
        "1 Sol Ring € 3",
        "1 Sol Ring $1.20 *F*",
    ],
)
def test_prices_are_stripped_and_never_echoed(store: StudioStore, line: str) -> None:
    parsed = decks.parse_decklist_text(store, CMD, line)
    assert _names(parsed) == ["Sol Ring"]
    assert parsed["not_in_collection"] == []
    assert parsed["ignored_annotations"] == [{"line": 1, "annotation": "Betragsangabe (ignoriert)"}]
    dumped = json.dumps(parsed, ensure_ascii=False)
    for figure in ("1.20", "1,20", "0.75", "$", "€", "USD"):
        assert figure not in dumped


def test_price_after_other_name(store: StudioStore) -> None:
    parsed = decks.parse_decklist_text(store, CMD, "Arcane Signet 0.75 USD")
    assert _names(parsed) == ["Arcane Signet"]
    assert "0.75" not in json.dumps(parsed)


def test_price_in_unreadable_line_is_not_echoed(store: StudioStore) -> None:
    parsed = decks.parse_decklist_text(store, CMD, "-1 Sol Ring $9.99")
    assert "9.99" not in json.dumps(parsed)


def test_csv_price_column_still_ignored(store: StudioStore) -> None:
    parsed = decks.parse_decklist_text(store, CMD, "Count,Name,Price\n1,Sol Ring,1.20\n")
    assert _names(parsed) == ["Sol Ring"]
    assert "1.20" not in json.dumps(parsed)


def test_typographic_characters_are_normalised(store: StudioStore) -> None:
    apos, lq, rq, nbsp, zwsp = (chr(c) for c in (0x2019, 0x201C, 0x201D, 0xA0, 0x200B))
    text = f"1 Ajani{apos}s Mantra\n1 {lq}Sol Ring{rq}\n1{nbsp}Arcane{nbsp}Signet\n1 Coun{zwsp}terspell\n"
    parsed = decks.parse_decklist_text(store, CMD, text)
    assert sorted(_names(parsed)) == ["Ajani's Mantra", "Arcane Signet", "Counterspell", "Sol Ring"]
    assert parsed["not_in_collection"] == []


@pytest.mark.parametrize(
    "line", ["99999999999999999999 Island", "-1 Counterspell", "0 Island", "100 Island"]
)
def test_quantity_bounds(store: StudioStore, line: str) -> None:
    parsed = decks.parse_decklist_text(store, CMD, line)
    assert parsed["in_collection"] == []
    assert parsed["not_in_collection"] == []
    unrecognized = parsed["unrecognized_lines"]
    assert isinstance(unrecognized, list)
    assert len(unrecognized) == 1
    assert unrecognized[0]["status"] == "unreadable"
    assert unrecognized[0]["raw"] == line


def test_csv_quantity_bounds(store: StudioStore) -> None:
    parsed = decks.parse_decklist_text(store, CMD, "Count,Name\n-1,Sol Ring\n500,Island\n2,Island")
    assert [(m["name"], m["quantity"]) for m in parsed["in_collection"]] == [("Island", 2)]  # type: ignore[attr-defined]
    assert len(parsed["unrecognized_lines"]) == 2  # type: ignore[arg-type]


def test_back_face_name_resolves_to_owned_card(store: StudioStore) -> None:
    parsed = decks.parse_decklist_text(store, CMD, "1 Kaiso, Memory of Loyalty")
    assert _names(parsed) == ["Faithful Squire // Kaiso, Memory of Loyalty"]


def test_oversize_baseline_id_is_refused_like_unknown(store: StudioStore, tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        decks.resolve_repo_baseline_cards(store, "repo:" + "a" * 5000, decks_dir=tmp_path)
