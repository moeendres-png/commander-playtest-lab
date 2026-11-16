"""Hardening of the universal deck-list import (Refs #1404): linear time, BOM, no echoed
amounts, typographic characters, quantity bounds, back-face names, oversize baseline ids."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from commander_lab.studio import DataClass, StudioStore, decks

EN_DASH = chr(0x2013)
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


def _assert_no_figures(parsed: dict[str, object], *figures: str) -> None:
    dumped = json.dumps(parsed, ensure_ascii=False)
    for figure in figures:
        assert figure not in dumped, figure


@pytest.mark.parametrize(
    ("text", "figures"),
    [
        ("-1 Sol Ring $12345678901234567", ("12345678901234567", "34567", "$")),
        ("1 Unknown Card $12345678901234567", ("12345678901234567", "$")),
        ("1 Sol Ring $1.20 extra", ("1.20", "$")),
        ("1 Sol Ring ($1.20)", ("1.20", "$")),
        ("1 Sol Ring US$1.20", ("1.20", "US$")),
        ("1 Sol Ring CHF 3", ("CHF",)),
        ("1 Sol Ring 1'200 €", ("1'200", "200", "€")),
        ("1 Sol Ring ¥300", ("300",)),
        ("1 Sol Ring 300 JPY", ("300", "JPY")),
        ("1 Sol Ring 1 000 €", ("000", "€")),
        (f"1 Sol Ring {EN_DASH} $1.20", ("1.20", "$")),
        ("1 Sol Ring\n  $1.20", ("1.20", "$")),
        ("1 $5", ("$5",)),
        ("1 5 USD", ("5 USD", "USD")),
        # a number before a currency symbol must not swallow the symbol of the NEXT amount
        ("1 Sol Ring 1 $1.20", ("1.20", "$")),
        ("1 Foo 2 $1.20", ("1.20", "$")),
        ("1 Foo 3 $ 4,50", ("4,50", "$")),
        ("1 Foo (5 $) 2 $3", ("$3", "$")),
        ("3 $7.50", ("7.50", "$")),
        ("1 Sol Ring x2 $1.20", ("1.20", "$")),
    ],
)
def test_amounts_never_returned_in_any_form(
    store: StudioStore, text: str, figures: tuple[str, ...]
) -> None:
    parsed = decks.parse_decklist_text(store, CMD, text)
    _assert_no_figures(parsed, *figures)
    for entry in parsed["not_in_collection"]:  # type: ignore[attr-defined]
        assert entry["name"] not in ("", "-")


def test_amount_forms_keep_the_card(store: StudioStore) -> None:
    for text in (
        "1 Sol Ring $1.20 extra",
        "1 Sol Ring ($1.20)",
        "1 Sol Ring 1 000 €",
        f"1 Sol Ring {EN_DASH} $1.20",
        "1 Sol Ring 300 JPY",
    ):
        parsed = decks.parse_decklist_text(store, CMD, text)
        if text.endswith("extra"):
            continue  # trailing words are part of the name; only the figure must vanish
        assert _names(parsed) == ["Sol Ring"], text


def test_amount_only_line_is_unreadable(store: StudioStore) -> None:
    parsed = decks.parse_decklist_text(store, CMD, "1 Sol Ring\n  $1.20\n")
    assert _names(parsed) == ["Sol Ring"]
    unrecognized = parsed["unrecognized_lines"]
    assert isinstance(unrecognized, list)
    assert [(u["line"], u["status"]) for u in unrecognized] == [(2, "unreadable")]


@pytest.mark.parametrize(
    "text",
    [
        "Count,Name,Price\nabc,Sol Ring,1.20",
        "Count,Name,Price\n-1,Sol Ring,12.50",
        "Count,Name,Price\n100,Sol Ring,1.20",
    ],
)
def test_csv_unreadable_rows_never_echo_price_column(store: StudioStore, text: str) -> None:
    parsed = decks.parse_decklist_text(store, CMD, text)
    unrecognized = parsed["unrecognized_lines"]
    assert isinstance(unrecognized, list)
    assert len(unrecognized) == 1
    assert unrecognized[0]["status"] == "unreadable"
    _assert_no_figures(parsed, "1.20", "12.50")


def test_csv_long_row_is_judged_on_name_and_quantity_cells(store: StudioStore) -> None:
    padded = "Count,Name,Notes,Price\n1,Sol Ring," + "n" * 400 + ",9.99"
    parsed = decks.parse_decklist_text(store, CMD, padded)
    assert _names(parsed) == ["Sol Ring"]
    long_name = "Count,Name,Price\n1," + "x" * 400 + ",9.99"
    parsed = decks.parse_decklist_text(store, CMD, long_name)
    assert parsed["unrecognized_lines"][0]["status"] == "zu lang"  # type: ignore[index]
    _assert_no_figures(parsed, "9.99")


def test_every_unrecognized_line_has_status(store: StudioStore) -> None:
    parsed = decks.parse_decklist_text(store, CMD, "1 $5\nCount,Name\nx")
    assert all("status" in u for u in parsed["unrecognized_lines"])  # type: ignore[attr-defined]
    csv_parsed = decks.parse_decklist_text(store, CMD, "Count,Name\nbad,Island\n1, ")
    entries = csv_parsed["unrecognized_lines"]
    assert isinstance(entries, list)
    assert len(entries) == 2
    assert all("status" in u for u in entries)


def test_enclosing_quotes_match_original_name_first(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "quoted")
    src = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE,
        title="c.csv",
        sha256="b" * 64,
        snapshot_date="2026-11-10",
    )
    with store.connection as db:
        for cid, name, ident in (
            ("cmd-chulane", "Chulane, Teller of Tales", "GWU"),
            ("c-q", '"Ach! Hans, Run!"', "G"),
        ):
            db.execute(
                "INSERT INTO card (card_id, oracle_id, oracle_name, color_identity, mana_cost, "
                "mana_value, type_line, oracle_text, is_basic_land, commander_legal, "
                "legality_verified_at, identity_evidence, source_id) "
                "VALUES (?, ?, ?, ?, '{1}', 1, 'Card', '', 0, 1, '2026-11-10', 'scryfall', ?)",
                (cid, "oid-" + cid, name, ident, src),
            )
            db.execute(
                "INSERT INTO inventory VALUES (?, 1, 2, 0, 2, 1, 1, '2026-11-10', ?)", (cid, src)
            )
    parsed = decks.parse_decklist_text(store, CMD, '1 "Ach! Hans, Run!"')
    assert _names(parsed) == ['"Ach! Hans, Run!"']


def test_amount_scrub_stays_linear(store: StudioStore) -> None:
    started = time.perf_counter()
    decks.parse_decklist_text(store, CMD, "9" * 80000)
    decks.parse_decklist_text(store, CMD, ("1,1" * 100 + "\n") * 2000)
    decks.parse_decklist_text(store, CMD, "Count,Name\n" + ("1," + "1 000 " * 50 + "\n") * 1500)
    assert time.perf_counter() - started < 2
