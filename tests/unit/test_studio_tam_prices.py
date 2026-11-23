"""TAM purchase prices (#1637, register entry "Preise für TAM"): Scryfall approximation,
Cardmarket price guide and entered Cardmarket prices.

Only synthetic price values (no real Scryfall or Cardmarket prices). The guards prove: the
values go only into the local store tables, only the commander TAM gets values and only for
cards not owned, a missing value is unknown (never 0), and no strength, swap, cut, pool or card
answer carries or is ordered by a price.
"""

from __future__ import annotations

import gzip
import json
import re
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, builder, cache, state_export, tam_prices
from commander_lab.studio.tam_import import TAM_COMMANDER_NAME
from commander_lab.studio.web import create_app

ROOT = Path(__file__).resolve().parents[2]
HEADER = {"X-Studio": "1"}
SENTINEL_CENTS = 987_654  # synthetic, appears nowhere else
GUIDE_SENTINEL_CENTS = 876_543  # synthetic price guide low
ENTRY_SENTINEL_CENTS = 765_432  # synthetic entered Cardmarket price
PRICE_TABLES = frozenset(
    {
        "tam_price_eur",
        "tam_price_snapshot",
        "tam_price_print",
        "tam_cardmarket_guide",
        "tam_cardmarket_guide_snapshot",
        "tam_cardmarket_price",
    }
)
LEAK_MARKERS = (
    "eur_cents", "tam_price", "tam_cardmarket", "richtwert", "prices.eur", "987654", "876543",
    "765432", "low_cents", "trend_cents", "preisführer", "eingetragen am",
)  # fmt: skip


def _rows(store: StudioStore, table: str) -> int:
    assert table in PRICE_TABLES
    return int(store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _card(oracle_id: str, scryfall_id: str, prices: object, **extra: object) -> dict[str, object]:
    return {
        "object": "card",
        "id": scryfall_id,
        "oracle_id": oracle_id,
        "name": f"Synthetic {oracle_id}",
        "prices": prices,
        "purchase_uris": {"cardmarket": "https://example.invalid/synthetic"},
        **extra,
    }


def _bulk(path: Path, cards: list[dict[str, object]]) -> Path:
    """A bulk file in Scryfall's layout: a JSON array with one card per line."""
    lines = ",\n".join(json.dumps(card) for card in cards)
    path.write_text("[\n" + lines + "\n]\n", encoding="utf-8")
    return path


SYNTHETIC = [
    _card("o-a", "s-a1", {"eur": "2.50", "eur_foil": "0.10", "usd": "0.01"}),
    _card("o-a", "s-a2", {"eur": "1.75", "eur_foil": None}),
    _card("o-b", "s-b", {"eur": None, "eur_foil": "3.00"}),
    _card("o-c", "s-c", {"eur": "0.00"}),
    _card("o-d", "s-d", {"eur": "abc"}),
    _card("o-e", "s-e", None),
    {"object": "card", "id": "s-x", "name": "No oracle", "prices": {"eur": "5.00"}},
]


def test_import_keeps_only_prices_eur_lowest_over_printings_and_unknown_never_zero(
    tmp_path: Path,
) -> None:
    store = StudioStore.open(tmp_path / "studio")
    before = store.count("scryfall_card")
    report = tam_prices.import_scryfall_prices(
        store, _bulk(tmp_path / "default-cards-20261120093012.json", SYNTHETIC)
    )
    assert report["bulk_date"] == "2026-11-20"
    assert report["date_basis"] == "Dateiname"
    assert report["cards_with_value"] == 2
    assert report["cards_without_value"] == 3  # o-c (0.00), o-d (abc), o-e (no prices)
    rows = store.connection.execute(
        "SELECT oracle_id, eur_cents, scryfall_id, finish FROM tam_price_eur ORDER BY oracle_id"
    ).fetchall()
    # the foil printing can be lower (o-a: eur_foil 0.10 under eur 1.75); o-b has foil only
    assert [tuple(row) for row in rows] == [
        ("o-a", 10, "s-a1", "foil"),
        ("o-b", 300, "s-b", "foil"),
    ]
    snap = store.connection.execute("SELECT * FROM tam_price_snapshot").fetchone()
    assert snap["file_name"] == "default-cards-20261120093012.json"
    assert len(snap["file_sha256"]) == 64
    assert store.count("scryfall_card") == before  # the facts table gets no price
    # no purchase link and no other price field lands in any table of the store
    for (table,) in store.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall():
        dump = repr(store.connection.execute(f'SELECT * FROM "{table}"').fetchall())
        assert "example.invalid" not in dump and "cardmarket" not in dump.casefold(), table
    store.close()


def test_only_playable_paper_printings_give_the_value(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    cards = [
        _card("o-p", "s-normal", {"eur": "850.00"}),
        _card("o-p", "s-gold", {"eur": "9.50"}, border_color="gold"),
        _card("o-p", "s-silver", {"eur": "8.00"}, border_color="silver"),
        _card("o-p", "s-oversized", {"eur": "1.20"}, oversized=True),
        _card("o-p", "s-digital", {"eur": "0.50"}, digital=True),
        _card("o-p", "s-memorabilia", {"eur": "0.40"}, set_type="memorabilia"),
        _card("o-p", "s-art", {"eur": "0.30"}, layout="art_series"),
        _card("o-only-oversized", "s-o2", {"eur": "2.00"}, oversized=True),
    ]
    report = tam_prices.import_scryfall_prices(
        store, _bulk(tmp_path / "x.jsonl", cards), bulk_date="2026-11-20"
    )
    rows = store.connection.execute(
        "SELECT oracle_id, eur_cents, scryfall_id, finish FROM tam_price_eur"
    )
    assert [tuple(r) for r in rows] == [("o-p", 85000, "s-normal", "nonfoil")]
    assert report["cards_without_value"] == 1  # only an oversized printing: unknown
    assert "ohne Übergröße" in tam_prices.VALUE_RULE
    arabic_indic = "\u0661\u0662.\u0665\u0660"  # 12.50 in Arabic-Indic digits: no price
    assert tam_prices._cents(arabic_indic) is None
    assert tam_prices._cents("12.50") == 1250
    with pytest.raises(sqlite3.IntegrityError):  # the table itself refuses a 0 value
        store.connection.execute(
            "INSERT INTO tam_price_eur(oracle_id, eur_cents) VALUES ('o-zero', 0)"
        )
    store.close()


def test_future_dates_and_conflicting_dates_are_refused(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    plain = _bulk(tmp_path / "cards.jsonl", SYNTHETIC)
    with pytest.raises(ValueError, match="future"):
        tam_prices.import_scryfall_prices(store, plain, bulk_date="2099-12-31")
    future_name = _bulk(tmp_path / "report-20991231-v2.json", SYNTHETIC)
    with pytest.raises(ValueError, match="future"):
        tam_prices.import_scryfall_prices(store, future_name)
    named = _bulk(tmp_path / "default-cards-20261120093012.json", SYNTHETIC)
    with pytest.raises(ValueError, match="conflict"):
        tam_prices.import_scryfall_prices(store, named, bulk_date="2026-11-19")
    assert _rows(store, "tam_price_snapshot") == 0
    store.close()


def test_the_cli_passes_the_bulk_date(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from commander_lab.studio.__main__ import main as studio_main

    plain = _bulk(tmp_path / "cards.jsonl", SYNTHETIC)
    data = tmp_path / "studio"
    assert (
        studio_main(
            ["--data", str(data), "import-tam-prices", str(plain), "--bulk-date", "2026-11-18"]
        )
        == 0
    )
    assert '"bulk_date": "2026-11-18"' in capsys.readouterr().out
    store = StudioStore.open(data)
    snap = store.connection.execute(
        "SELECT bulk_date, date_basis FROM tam_price_snapshot"
    ).fetchone()
    assert tuple(snap) == ("2026-11-18", "angegeben")
    store.close()


def test_import_needs_a_bulk_date_and_replaces_the_snapshot(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    plain = _bulk(tmp_path / "cards.jsonl", SYNTHETIC)
    with pytest.raises(ValueError, match="bulk date"):
        tam_prices.import_scryfall_prices(store, plain)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        tam_prices.import_scryfall_prices(store, plain, bulk_date="20.11.2026")
    with pytest.raises(ValueError, match="no calendar date"):
        tam_prices.import_scryfall_prices(store, plain, bulk_date="2026-99-99")
    impossible = _bulk(tmp_path / "default-cards-20260231120000.json", SYNTHETIC)
    with pytest.raises(ValueError, match="no calendar date"):
        tam_prices.import_scryfall_prices(store, impossible)  # 31 February from the file name
    assert _rows(store, "tam_price_snapshot") == 0  # refused, nothing written
    tam_prices.import_scryfall_prices(store, plain, bulk_date="2026-11-19")
    later = _bulk(tmp_path / "later.jsonl", [_card("o-z", "s-z", {"eur": "4.20"})])
    report = tam_prices.import_scryfall_prices(store, later, bulk_date="2026-11-21")
    assert report["date_basis"] == "angegeben"
    rows = store.connection.execute("SELECT oracle_id, eur_cents FROM tam_price_eur").fetchall()
    assert [tuple(row) for row in rows] == [("o-z", 420)]  # the old snapshot is gone
    assert _rows(store, "tam_price_snapshot") == 1
    store.close()


def _seed_prices(store: StudioStore, values: dict[str, int], bulk_date: str = "2026-11-20") -> None:
    with store.connection as db:
        db.execute("DELETE FROM tam_price_eur")
        db.executemany(
            "INSERT INTO tam_price_eur(oracle_id, eur_cents, scryfall_id) VALUES (?, ?, NULL)",
            list(values.items()),
        )
        db.execute("DELETE FROM tam_price_snapshot")
        db.execute(
            "INSERT INTO tam_price_snapshot VALUES (1, 'synthetic.json', ?, ?, 'angegeben', "
            "'2026-11-21T00:00:00Z', ?, 0)",
            ("0" * 64, bulk_date, len(values)),
        )


def _seed_cardmarket(
    store: StudioStore, guide: dict[str, int], entered: dict[str, int], day: str = "2026-11-20"
) -> None:
    """Price guide values (low and trend) and entered Cardmarket prices, synthetic."""
    with store.connection as db:
        db.execute("DELETE FROM tam_cardmarket_guide")
        db.executemany(
            "INSERT INTO tam_cardmarket_guide(oracle_id, low_cents, low_finish, low_set_code, "
            "low_collector_number, trend_cents) VALUES (?, ?, 'foil', 'SYN', '1', ?)",
            [(oid, cents, cents + 1) for oid, cents in guide.items()],
        )
        db.execute("DELETE FROM tam_cardmarket_guide_snapshot")
        db.execute(
            "INSERT INTO tam_cardmarket_guide_snapshot VALUES (1, ?, 'angegeben', ?, "
            "'2026-11-21T00:00:00Z', 1, 1, 1, 0, 1, ?)",
            (day, "0" * 64, len(guide)),
        )
        db.execute("DELETE FROM tam_cardmarket_price")
        db.executemany(
            "INSERT INTO tam_cardmarket_price(oracle_id, eur_cents, price_date, recorded_at, "
            "filter_code, source_url) VALUES (?, ?, ?, '2026-11-21T00:00:00Z', 'DE/EX/EN+DE', "
            "NULL)",
            [(oid, cents, day) for oid, cents in entered.items()],
        )


CHULANE = "Chulane, Teller of Tales"


def _add_owned_commander(
    store: StudioStore, card_id: str, oracle_id: str, name: str, colors: str
) -> None:
    from tests.unit.test_studio_builder import _insert_scryfall

    db = store.connection
    source_id = str(db.execute("SELECT source_id FROM card LIMIT 1").fetchone()[0])
    _insert_scryfall(
        store, oracle_id=oracle_id, name=name, colors=colors, type_line="Legendary Creature"
    )
    db.execute(
        "INSERT INTO card(card_id, oracle_name, oracle_id, color_identity, mana_cost, "
        "mana_value, type_line, oracle_text, is_basic_land, commander_legal, source_id) "
        "VALUES (?, ?, ?, ?, '{5}', 5.0, 'Legendary Creature', '', 0, 1, ?)",
        (card_id, name, oracle_id, colors, source_id),
    )
    db.execute(
        "INSERT INTO inventory(card_id, observed, owned_lower_bound, reserved, "
        "available_lower_bound, quantity_exact, source_id) VALUES (?, 1, 1, 0, 1, 1, ?)",
        (card_id, source_id),
    )


def _deck(client: TestClient, name: str, commander_id: str, main: list[str]) -> str:
    created = client.post("/api/decks", json={"name": name, "commander_card_ids": [commander_id]})
    assert created.status_code == 200, created.text
    head = str(created.json()["revision_id"])
    cards = [{"card_id": commander_id, "quantity": 1, "zone": "commander"}]
    cards += [{"card_id": card_id, "quantity": 1, "zone": "main"} for card_id in main]
    saved = client.post(
        f"/api/decks/{created.json()['deck_id']}/revisions",
        json={"cards": cards, "parent_revision_id": head, "expected_parent": head},
    )
    assert saved.status_code == 200, saved.text
    return str(created.json()["deck_id"])


def _tam_store(tmp_path: Path) -> tuple[TestClient, dict[str, str]]:
    """TAM and Chulane decks with the same purchase cards (one with a value, one without, one
    owned), and a card of neither deck."""
    from tests.unit.test_studio_builder import _fill, _insert_scryfall

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    owned = store.connection.execute(
        "SELECT c.card_id, c.oracle_id FROM card c JOIN inventory i ON i.card_id = c.card_id "
        "WHERE i.owned_lower_bound > 0 AND c.oracle_id IS NOT NULL "
        "AND c.type_line NOT LIKE 'Basic%' ORDER BY c.card_id LIMIT 1"
    ).fetchone()
    ids = {"owned": str(owned["card_id"]), "owned_oracle": str(owned["oracle_id"])}
    _add_owned_commander(store, "card:t:tam", "o-tam", TAM_COMMANDER_NAME, "WUBRG")
    _add_owned_commander(store, "card:t:chulane", "o-chulane", CHULANE, "WUG")
    for key, oracle_id in (("priced", "o-tam-priced"), ("unknown", "o-tam-unknown"),
                           ("foreign", "o-foreign"), ("later", "o-tam-later")):  # fmt: skip
        _insert_scryfall(
            store, oracle_id=oracle_id, name=f"Walker {key}", colors="W",
            type_line="Legendary Planeswalker — Test",
        )  # fmt: skip
        ids[key] = f"scryfall:{oracle_id}"
    # another printing of the owned card: not in the inventory itself
    store.connection.execute(
        "INSERT INTO card(card_id, oracle_name, oracle_id, color_identity, mana_cost, mana_value, "
        "type_line, oracle_text, is_basic_land, commander_legal, source_id) SELECT "
        "'card:t:owned-alt', oracle_name, oracle_id, color_identity, mana_cost, mana_value, "
        "type_line, oracle_text, is_basic_land, commander_legal, source_id FROM card "
        "WHERE card_id = ?",
        (ids["owned"],),
    )
    ids["owned_alt"] = "card:t:owned-alt"
    store.connection.commit()
    _seed_prices(
        store,
        {"o-tam-priced": 1234, ids["owned_oracle"]: 555, "o-foreign": 777, "o-tam-later": 888},
    )
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers=HEADER)
    main = [ids["priced"], ids["unknown"], ids["owned"]]
    ids["tam_deck"] = _deck(client, "TAM Zukauf", "card:t:tam", main)
    ids["chulane_deck"] = _deck(client, "Chulane Zukauf", "card:t:chulane", main)
    return client, ids


def _entry(card_id: str, zone: str = "main") -> dict[str, object]:
    return {"card_id": card_id, "quantity": 1, "zone": zone}


def _draft(
    client: TestClient, deck_id: str, cards: list[dict[str, object]], branch: str = "main"
) -> httpx.Response:
    return client.put(f"/api/decks/{deck_id}/branches/{branch}/draft", json={"cards": cards})


def _ask(client: TestClient, deck_id: str, card_ids: list[str], **extra: object) -> object:
    return client.post(
        "/api/tam/zukauf-richtwerte", json={"deck_id": deck_id, "card_ids": card_ids, **extra}
    )


def test_only_a_stored_tam_deck_gets_values_and_only_for_its_cards_not_owned(
    tmp_path: Path,
) -> None:
    client, ids = _tam_store(tmp_path)
    wanted = [ids["priced"], ids["unknown"], ids["owned"]]
    response = _ask(client, ids["tam_deck"], wanted)
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["kind"] == "Näherung"
    assert answer["source"] == (
        "Scryfall (Cardmarket-Preisführer, kein Filter Deutschland/Excellent)"
    )
    assert answer["snapshot"]["bulk_date"] == "2026-11-20"
    assert "nicht Deutschland" in answer["notice"] and "kein Angebot" in answer["notice"]
    assert answer["guide_snapshot"] is None  # no price guide imported
    assert answer["not_in_deck"] == 0
    assert answer["cards"] == [
        {
            "card_id": ids["priced"],
            "name": "Walker priced",
            "status": "value",
            "eur_cents": 1234,
            "finish": "",
            "printing": "",
        },
        {"card_id": ids["unknown"], "name": "Walker unknown", "status": "unknown"},
        # owned in the collection: no value although the snapshot has one for its oracle_id
        {"card_id": ids["owned"], "status": "owned"},
    ]
    # a card of no deck (with a value row) is left out and counted, never answered
    mixed = _ask(client, ids["tam_deck"], [ids["foreign"], ids["priced"]]).json()
    assert [(c["card_id"], c.get("eur_cents")) for c in mixed["cards"]] == [(ids["priced"], 1234)]
    assert mixed["not_in_deck"] == 1 and "777" not in json.dumps(mixed)
    # the commander of the deck is part of the list and answered (here: owned)
    commander = _ask(client, ids["tam_deck"], ["card:t:tam"]).json()
    assert commander["cards"] == [{"card_id": "card:t:tam", "status": "owned"}]


def test_a_card_owned_in_another_printing_gets_no_value(tmp_path: Path) -> None:
    client, ids = _tam_store(tmp_path)
    cards = [_entry("card:t:tam", "commander"), _entry(ids["owned_alt"]), _entry(ids["priced"])]
    assert _draft(client, ids["tam_deck"], cards).status_code == 200
    answer = _ask(client, ids["tam_deck"], [ids["owned_alt"], ids["priced"]]).json()
    assert [(c["card_id"], c["status"], c.get("eur_cents")) for c in answer["cards"]] == [
        (ids["owned_alt"], "owned", None),  # the snapshot has 555 for its oracle
        (ids["priced"], "value", 1234),
    ]


def test_the_stored_commander_decides_not_the_name_the_client_sends(tmp_path: Path) -> None:
    client, ids = _tam_store(tmp_path)
    wanted = [ids["priced"], ids["owned"]]
    for extra in ({}, {"commander": TAM_COMMANDER_NAME}):
        refused = _ask(client, ids["chulane_deck"], wanted, **extra)
        assert refused.status_code == 403, extra
        assert "eur_cents" not in refused.text and "1234" not in refused.text
    # a TAM deck asked under another name is refused as well
    assert _ask(client, ids["tam_deck"], wanted, commander=CHULANE).status_code == 403
    assert _ask(client, "no-such-deck", wanted).status_code == 404
    too_many = _ask(client, ids["tam_deck"], [f"x{i}" for i in range(251)])
    assert too_many.status_code == 422


def test_the_working_draft_is_the_list_answered(tmp_path: Path) -> None:
    client, ids = _tam_store(tmp_path)
    assert _ask(client, ids["tam_deck"], [ids["later"]]).json()["cards"] == []
    cards = [{"card_id": "card:t:tam", "quantity": 1, "zone": "commander"}]
    cards += [{"card_id": ids["later"], "quantity": 1, "zone": "main"}]
    put = client.put(f"/api/decks/{ids['tam_deck']}/branches/main/draft", json={"cards": cards})
    assert put.status_code == 200, put.text
    answer = _ask(client, ids["tam_deck"], [ids["later"], ids["priced"]]).json()
    assert [(c["card_id"], c.get("eur_cents")) for c in answer["cards"]] == [(ids["later"], 888)]


def test_a_draft_never_makes_a_tam_deck(tmp_path: Path) -> None:
    """The saved revision of the variant must exist and be TAM-only; a draft can only narrow."""
    client, ids = _tam_store(tmp_path)
    main = [_entry(ids["priced"]), _entry(ids["owned"])]
    wanted = [ids["priced"]]
    # (a) a Chulane deck whose draft names TAM as commander
    assert (
        _draft(client, ids["chulane_deck"], [_entry("card:t:tam", "commander"), *main]).status_code
        == 200
    )
    refused = _ask(client, ids["chulane_deck"], wanted, commander=TAM_COMMANDER_NAME)
    assert refused.status_code == 403 and "1234" not in refused.text
    # (b) a draft whose commander id is the name of TAM (no such card): never read as the name
    assert (
        _draft(
            client, ids["tam_deck"], [_entry(TAM_COMMANDER_NAME, "commander"), *main]
        ).status_code
        == 200
    )
    assert _ask(client, ids["tam_deck"], wanted).status_code == 403
    # TAM plus a second commander (Chulane) in the draft: not TAM-only
    two = [_entry("card:t:tam", "commander"), _entry("card:t:chulane", "commander"), *main]
    assert _draft(client, ids["tam_deck"], two).status_code == 200
    assert _ask(client, ids["tam_deck"], wanted).status_code == 403
    # a draft without any commander: refused as well
    assert _draft(client, ids["tam_deck"], main).status_code == 200
    assert _ask(client, ids["tam_deck"], wanted).status_code == 403
    # (c) a draft on a variant that was never saved
    ghost = _draft(client, ids["tam_deck"], [_entry("card:t:tam", "commander"), *main], "ghost")
    assert ghost.status_code == 200
    assert _ask(client, ids["tam_deck"], wanted, branch="ghost").status_code == 404
    # the TAM deck with a proper TAM draft answers again
    assert (
        _draft(client, ids["tam_deck"], [_entry("card:t:tam", "commander"), *main]).status_code
        == 200
    )
    assert _ask(client, ids["tam_deck"], wanted).status_code == 200


def test_without_a_snapshot_every_card_is_unknown(tmp_path: Path) -> None:
    client, ids = _tam_store(tmp_path)
    store = StudioStore.open(tmp_path / "studio")
    with store.connection as db:
        db.execute("DELETE FROM tam_price_snapshot")
    store.close()
    answer = _ask(client, ids["tam_deck"], [ids["priced"], ids["owned"]]).json()
    assert answer["snapshot"] is None
    assert [c["status"] for c in answer["cards"]] == ["unknown", "owned"]
    assert "eur_cents" not in json.dumps(answer)


WALKERS = (("o-leak-walker-a", "Leak Walker Alpha"), ("o-leak-walker-b", "Leak Walker Beta"))


def _leak_store(tmp_path: Path) -> tuple[StudioStore, str]:
    """The swap store plus TAM and Chulane in the collection and unowned WUBRG planeswalkers:
    the commander with a live guide-value path, the one that must never get one, and Zukauf
    candidates that have a value row."""
    from tests.unit.test_studio_builder import _insert_scryfall
    from tests.unit.test_studio_swap import _seed_swap_store

    store = _seed_swap_store(tmp_path)
    cmd_id = str(builder.pool_cards(store, ["Test Commander"])["commander_ids"][0])
    _add_owned_commander(store, "card:leak:tam", "o-leak-tam", TAM_COMMANDER_NAME, "WUBRG")
    _add_owned_commander(store, "card:leak:chulane", "o-leak-chulane", CHULANE, "WUG")
    for oracle_id, name in WALKERS:
        _insert_scryfall(
            store,
            oracle_id=oracle_id,
            name=name,
            colors="WU",
            type_line="Legendary Planeswalker — Test",
        )
    store.connection.commit()
    return store, cmd_id


def _answers(client: TestClient, cmd_id: str, card_id: str) -> dict[str, object]:
    """The answers that must never carry or be shaped by a guide value: pool (also the Zukauf
    candidates of TAM and Chulane), strength, swap, cut lab, alternatives and the card page."""
    commander = "Test Commander"
    out: dict[str, object] = {}
    for who in (commander, TAM_COMMANDER_NAME, CHULANE):
        for include in (False, True):
            response = client.get(
                "/api/pool", params={"commander": who, "include_unowned": include}
            )
            assert response.status_code == 200, response.text
            out[f"pool_{who}_{include}"] = response.json()
        strength = client.post("/api/strength", json={"commander": who})
        assert strength.status_code == 200, strength.text
        out[f"strength_{who}"] = strength.json()
    for mode in ("replace", "cut"):
        swap = client.post(
            "/api/swap",
            json={
                "commander": commander,
                "deck_card_ids": [cmd_id, "rem-low", "rem-mid"],
                "card_id": "rem-low" if mode == "replace" else "rem-high",
                "mode": mode,
                "cohort": "all",
            },
        )
        assert swap.status_code == 200, swap.text
        out[f"swap_{mode}"] = swap.json()
    cards = [{"card_id": cmd_id, "quantity": 1, "zone": "commander"}]
    cards += [
        {"card_id": c, "quantity": 1, "zone": "main"} for c in ("rem-low", "rem-mid", "draw-high")
    ]
    cut = client.post("/api/cut-lab", json={"cards": cards})
    assert cut.status_code == 200, cut.text
    out["cut_lab"] = cut.json()
    alternatives = client.post(
        f"/api/cards/{card_id}/alternatives",
        json={"commander": [commander], "in_deck": [cmd_id, "rem-low"]},
    )
    assert alternatives.status_code == 200, alternatives.text
    out["alternatives"] = alternatives.json()
    detail = client.get(f"/api/cards/{card_id}", params={"commander": commander})
    assert detail.status_code == 200, detail.text
    out["card"] = detail.json()
    # suggestions, deck plans, doctor, duel, evidence, data page and simulation lists
    plan = {"commander": commander, "cards": cards}
    q = {"commander": commander}
    for method, path, payload, params in (
        ("POST", "/api/packages", plan, None),
        ("POST", "/api/build-plan", plan, None),
        ("POST", "/api/upgrade-path", plan, None),
        ("POST", "/api/deck-doctor", plan, None),
        ("POST", "/api/deck-evidence", plan, None),
        ("POST", "/api/land-advisor", plan, None),
        ("POST", "/api/deck-facts", {"cards": cards}, None),
        ("POST", "/api/check", {"cards": cards}, None),
        ("POST", "/api/castability", {"cards": cards}, None),
        (
            "POST",
            "/api/card-duel",
            {"commander": commander, "card_a": "rem-low", "card_b": "rem-mid"},
            None,
        ),
        ("GET", "/api/similar-decks", None, q),
        ("GET", "/api/layers", None, q),
        ("GET", "/api/roles/audit", None, q),
        ("GET", "/api/cohorts", None, q),
        ("GET", "/api/simulations", None, q),
        ("GET", "/api/simulations/paired", None, None),
        ("GET", "/api/decks", None, None),
        ("GET", "/api/data-report", None, None),
        ("GET", "/api/status", None, None),
    ):
        response = client.request(method, path, json=payload, params=params)
        assert response.status_code == 200, (path, response.text)
        out[path] = response.json()
    # the Zukauf path is really walked: TAM's candidates hold the planeswalkers with a value row
    tam_cards = out[f"pool_{TAM_COMMANDER_NAME}_True"]["cards"]  # type: ignore[index]
    candidates = {c["name"] for c in tam_cards if c.get("wishlist_candidate")}
    assert {name for _oid, name in WALKERS} <= candidates
    return out


def _seed_all_sentinels(store: StudioStore) -> None:
    oracle_ids = _all_oracle_ids(store)
    _seed_prices(store, dict.fromkeys(oracle_ids, SENTINEL_CENTS))
    _seed_cardmarket(
        store,
        dict.fromkeys(oracle_ids, GUIDE_SENTINEL_CENTS),
        dict.fromkeys(oracle_ids, ENTRY_SENTINEL_CENTS),
        day=datetime.now(UTC).date().isoformat(),
    )


def _all_oracle_ids(store: StudioStore) -> list[str]:
    rows = store.connection.execute(
        "SELECT oracle_id FROM scryfall_card UNION SELECT oracle_id FROM card "
        "WHERE oracle_id IS NOT NULL ORDER BY 1"
    ).fetchall()
    return [str(row[0]) for row in rows]


def test_no_answer_carries_or_is_ordered_by_a_guide_value(tmp_path: Path) -> None:
    """Equality guard: pool (with and without Zukauf, also for TAM and Chulane), strength, swap,
    cut lab, alternatives and the card page are identical with an empty price table and with
    values that run against every order."""
    store, cmd_id = _leak_store(tmp_path)
    oracle_ids = _all_oracle_ids(store)
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers=HEADER)
    cache.invalidate()
    without = _answers(client, cmd_id, "rem-high")

    store = StudioStore.open(tmp_path / "studio")
    # varied values, the highest for the alphabetically first card: any use for ordering shows
    _seed_prices(store, {oid: 100 + 37 * (len(oracle_ids) - i) for i, oid in enumerate(oracle_ids)})
    _seed_cardmarket(
        store,
        {oid: 50 + 41 * (len(oracle_ids) - i) for i, oid in enumerate(oracle_ids)},
        {oid: 70 + 43 * i for i, oid in enumerate(oracle_ids)},
    )
    store.close()
    cache.invalidate()
    with_values = _answers(client, cmd_id, "rem-high")
    assert with_values == without


def test_no_answer_holds_a_price_field_or_value(tmp_path: Path) -> None:
    """Scan guard: with a sentinel value for every card, no answer of the pool (TAM and Chulane
    included), strength, swap, cut lab, alternatives or card page names a price field or holds
    the value."""
    store, cmd_id = _leak_store(tmp_path)
    _seed_all_sentinels(store)
    store.close()
    cache.invalidate()
    client = TestClient(create_app(tmp_path / "studio"), headers=HEADER)
    answers = _answers(client, cmd_id, "rem-high")
    assert len(answers) == 33
    for name, answer in answers.items():
        text = json.dumps(answer, ensure_ascii=False).casefold()
        for marker in LEAK_MARKERS:
            assert marker not in text, (name, marker)


_SWEEP_SKIP = ("/engine", "/games", "/play", "/img", "/table", "/outcomes", "/tam/")


def test_every_route_that_answers_holds_no_price(tmp_path: Path) -> None:
    """Sweep: every GET route of the app (path parameters filled with the TAM and the Chulane
    deck, with and without include_unowned) and the deck POST routes, against a store with a
    sentinel value for every card. Only the TAM route may carry it; routes that need an engine,
    a game or an image are left out (the one-reader guard covers them statically)."""
    store, _cmd_id = _leak_store(tmp_path)
    _seed_all_sentinels(store)
    store.close()
    cache.invalidate()
    app = create_app(tmp_path / "studio")
    client = TestClient(app, headers=HEADER)
    walkers = [f"scryfall:{oracle_id}" for oracle_id, _name in WALKERS]
    decks = {
        TAM_COMMANDER_NAME: (
            "card:leak:tam",
            _deck(client, "TAM", "card:leak:tam", [*walkers, "rem-low"]),
        ),
        CHULANE: (
            "card:leak:chulane",
            _deck(client, "Chu", "card:leak:chulane", [*walkers, "rem-low"]),
        ),
    }
    control = _ask(client, decks[TAM_COMMANDER_NAME][1], walkers)
    for sentinel in (SENTINEL_CENTS, GUIDE_SENTINEL_CENTS, ENTRY_SENTINEL_CENTS):
        assert str(sentinel) in control.text  # the sentinels are live on the one route
    scanned: list[str] = []
    hits: list[tuple[str, str]] = []

    def scan(label: str, response: httpx.Response) -> None:
        if response.status_code != 200:
            return
        scanned.append(label)
        low = response.text.casefold()
        hits.extend((label, marker) for marker in LEAK_MARKERS if marker in low)

    for who, (commander_id, deck_id) in decks.items():
        revision = client.get(f"/api/decks/{deck_id}/history").json()[0]["revision_id"]
        fill = {"card_id": walkers[0], "deck_id": deck_id, "revision_id": revision,
                "branch": "main", "name": "x"}  # fmt: skip
        for route in app.routes:
            path = str(getattr(route, "path", ""))
            if not path.startswith("/api/") or "GET" not in (
                getattr(route, "methods", None) or set()
            ):
                continue
            if any(part in path for part in _SWEEP_SKIP):
                continue
            url = re.sub(r"\{(\w+)(?::\w+)?\}", lambda m, f=fill: f.get(m.group(1), "x"), path)
            for params in ({"commander": who}, {"commander": who, "include_unowned": True}):
                scan(f"GET {path} {who} {len(params)}", client.get(url, params=params))
        cards = [_entry(commander_id, "commander"), *[_entry(c) for c in [*walkers, "rem-low"]]]
        plan = {"commander": who, "cards": cards}
        for path, body in (
            ("/api/build-list", plan), ("/api/sample-hand", {"cards": cards}),
            ("/api/tokens", {"cards": cards}), ("/api/diff", {"cards": cards, "commander": who}),
            ("/api/cut-lab", {"cards": cards}),
            ("/api/cut-lab/what-if", {"cards": cards, "cut": ["rem-low"]}),
            ("/api/deck-doctor", plan), ("/api/upgrade-path", plan), ("/api/packages", plan),
            ("/api/build-plan", plan), ("/api/deck-evidence", plan), ("/api/land-advisor", plan),
            ("/api/castability", {"cards": cards}), ("/api/deck-facts", {"cards": cards}),
            ("/api/check", {"cards": cards}), ("/api/public-cards", {"card_ids": walkers}),
            ("/api/swap", {"commander": who, "deck_card_ids": [commander_id, *walkers, "rem-low"],
                           "card_id": walkers[0], "mode": "replace", "cohort": "all"}),
            ("/api/strength", {"commander": who}),
            ("/api/card-duel", {"commander": who, "card_a": walkers[0], "card_b": walkers[1]}),
            (f"/api/cards/{walkers[0]}/alternatives", {"commander": [who], "in_deck": [commander_id]}),
        ):  # fmt: skip
            scan(f"POST {path} {who}", client.post(path, json=body))
    assert len(scanned) >= 150, len(scanned)
    assert hits == []


def test_price_tables_stay_out_of_the_user_state_export(tmp_path: Path) -> None:
    assert not (PRICE_TABLES & state_export._TABLE_NAMES)
    client, ids = _tam_store(tmp_path)
    saved = client.post(
        "/api/tam/cardmarket-eintrag",
        json={"deck_id": ids["tam_deck"], "card_id": ids["priced"], "eur_text": "7654,32"},
    )
    assert saved.status_code == 200, saved.text
    store = StudioStore.open(tmp_path / "studio")
    _seed_cardmarket(store, {"o-tam-priced": GUIDE_SENTINEL_CENTS}, {})
    store.connection.execute(
        "INSERT INTO tam_cardmarket_price VALUES ('o-tam-unknown', ?, '2026-11-20', 't', "
        "'DE/EX/EN+DE', NULL)",
        (ENTRY_SENTINEL_CENTS,),
    )
    store.connection.commit()
    target = tmp_path / "state.json.gz"
    state_export.export_state(store, target)
    store.close()
    text = gzip.decompress(target.read_bytes()).decode("utf-8").casefold()
    assert "deck" in text  # the export holds the user state
    for marker in ("765432", "876543", "1234", "tam_price", "tam_cardmarket", "eur_cents"):
        assert marker not in text, marker


def test_the_local_store_refuses_the_repository(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="outside the repository"):
        StudioStore.open(ROOT / "data" / "tam-prices-guard")


# Committed data carries no price values: no price key with a figure in the tracked data,
# source, script and config files, and no price values or ``purchase_uris`` in tracked
# ``tests/fixtures/`` (the legacy Scryfall card fixture was removed in #1749). Python test
# modules outside ``tests/fixtures/`` hold synthetic values only.
_COMMITTED_PRICE = re.compile(
    r'"(?:eur|eur_foil|eur_cents|usd|usd_foil|tix)"\s*:\s*"?\d', re.IGNORECASE
)


def test_no_committed_price_values_in_data_src_or_scripts() -> None:
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "data", "src", "scripts", "config"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    offenders: list[str] = []
    scanned = 0
    for relative in filter(None, tracked.split("\0")):
        path = ROOT / relative
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 20_000_000:
            continue
        if path.suffix not in {".json", ".jsonl", ".csv", ".py", ".js", ".txt", ".md", ".yml"}:
            continue
        scanned += 1
        if _COMMITTED_PRICE.search(path.read_text(encoding="utf-8", errors="replace")):
            offenders.append(relative)
    assert scanned > 1000
    assert offenders == []
    assert _COMMITTED_PRICE.search('{"eur": "1.75"}')  # the pattern still finds a value


def _has_committed_fixture_price(text: str) -> bool:
    return bool(_COMMITTED_PRICE.search(text)) or "purchase_uris" in text.casefold()


def test_no_committed_price_values_in_tracked_fixtures() -> None:
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "tests/fixtures"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    offenders: list[str] = []
    scanned = 0
    scanned_gz = 0
    for relative in filter(None, tracked.split("\0")):
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            continue
        if path.suffix == ".gz":
            text = gzip.decompress(path.read_bytes()).decode("utf-8", errors="replace")
            scanned_gz += 1
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
        scanned += 1
        if _has_committed_fixture_price(text):
            offenders.append(relative)
    assert scanned >= 10
    assert scanned_gz >= 1
    assert offenders == []
    assert _COMMITTED_PRICE.search('{"eur": "1.75"}')
    assert _COMMITTED_PRICE.search('{"usd": "1.98"}')
    assert _has_committed_fixture_price(
        '{"purchase_uris": {"cardmarket": "https://example.invalid"}}'
    )


# Structural guard: the prices have one reader. The table names and the value fields occur only
# where the tables are declared (schema, cache group, source register text) and in the one
# module that writes and reads them; that module is imported only by the TAM routes and the CLI,
# and in web.py only the TAM routes and their body models use it. A new route that reads the
# values (e.g. a MAX(eur_cents) into a ranking) fails here even when no answer test calls it.
_VALUE_NAMES = re.compile(
    r"tam_price_eur|tam_price_snapshot|tam_price_print|tam_cardmarket_guide|"
    r"tam_cardmarket_price|eur_cents|low_cents|trend_cents"
)
# the display of the TAM purchase list (static/wishlist.js) reads the values of the route answer
_VALUE_FILES = frozenset(
    {"tam_prices.py", "store.py", "cache.py", "sources.py", "static/wishlist.js"}
)
# the new tables only where they are declared and read (sources.py names only tam_price_eur)
_NEW_TABLES = re.compile(r"tam_price_print|tam_cardmarket_guide|tam_cardmarket_price")
_NEW_TABLE_FILES = frozenset({"tam_prices.py", "store.py", "cache.py"})
_MODULE_USERS = frozenset({"web.py", "__main__.py"})
_CARDMARKET_MODULE_USERS = frozenset({"tam_prices.py", "__main__.py"})
_TAM_WEB_PARTS = (
    ("class TamPurchaseBody(BaseModel):", "\nclass "),
    ("class TamCardmarketEntryBody(BaseModel):", "\nclass "),
    ('    @app.post("/api/tam/zukauf-richtwerte")', "\n    @app."),
    ('    @app.post("/api/tam/cardmarket-eintrag")', "\n    @app."),
)


def _src_files() -> list[Path]:
    files = sorted(
        path
        for path in (ROOT / "src").rglob("*")
        if path.is_file() and path.suffix in {".py", ".js", ".html", ".sql"}
    )
    assert len(files) > 100
    return files


def test_guide_values_have_one_reader_in_src() -> None:
    src = ROOT / "src"
    files = _src_files()
    texts = {p.relative_to(src).as_posix(): p.read_text(encoding="utf-8") for p in files}
    by_value = {name for name, text in texts.items() if _VALUE_NAMES.search(text)}
    assert by_value == {f"commander_lab/studio/{name}" for name in _VALUE_FILES}
    by_table = {name for name, text in texts.items() if _NEW_TABLES.search(text)}
    assert by_table == {f"commander_lab/studio/{name}" for name in _NEW_TABLE_FILES}
    module_users = {
        name
        for name, text in texts.items()
        if not name.endswith("/tam_prices.py") and re.search(r"\btam_prices\b", text)
    }
    assert module_users == {f"commander_lab/studio/{name}" for name in _MODULE_USERS}
    cardmarket_users = {
        name
        for name, text in texts.items()
        if not name.endswith("/tam_cardmarket.py") and re.search(r"\btam_cardmarket\b", text)
    }
    assert cardmarket_users == {f"commander_lab/studio/{name}" for name in _CARDMARKET_MODULE_USERS}
    web = texts["commander_lab/studio/web.py"]
    inside = 0
    for start, end in _TAM_WEB_PARTS:
        part = web[web.index(start) :]
        part = part[: part.index(end, len(start))]
        inside += len(re.findall(r"\btam_prices\.", part))
    uses = len(re.findall(r"\btam_prices\.", web))
    assert uses == inside and uses >= 5 and web.count("tam_prices,") == 1  # the import line
    main = texts["commander_lab/studio/__main__.py"]
    # import-tam-prices, import-cardmarket-priceguide, import-tam-cardmarket-csv
    assert len(re.findall(r"\btam_prices\.", main)) == 3


# Only the price guide download talks HTTP to Cardmarket: no other file of src pairs an HTTP
# call with a Cardmarket host, and the one module asks only downloads.s3.cardmarket.com (the
# card page address is built for the Owner's browser, never requested).
_HTTP_CALL = re.compile(
    r"\b(?:requests|httpx|aiohttp|urllib\.request|urlopen|http\.client|socket\.create_connection)\b"
    r"|\bfetch\(|XMLHttpRequest|sendBeacon"
)


def test_no_http_request_to_cardmarket_outside_the_price_guide_download() -> None:
    src = ROOT / "src"
    hosts: dict[str, int] = {}
    for path in _src_files():
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(src).as_posix()
        if "cardmarket.com" in text.casefold():
            hosts[name] = text.casefold().count("cardmarket.com")
            if name != "commander_lab/studio/tam_cardmarket.py":
                assert not _HTTP_CALL.search(text) or name.endswith("sources.py"), name
    # the address stands only in the download module, in the source register entry of the price
    # guide (text, no request) and in the two link constants of the TAM block of wishlist.js
    assert set(hosts) == {
        "commander_lab/studio/tam_cardmarket.py",
        "commander_lab/studio/sources.py",
        "commander_lab/studio/static/wishlist.js",
    }
    register = (src / "commander_lab/studio/sources.py").read_text(encoding="utf-8")
    entry = register[register.index('source_id="cardmarket:price-guide"') :]
    entry = entry[: entry.index("\n    ),\n")]
    assert hosts["commander_lab/studio/sources.py"] == entry.casefold().count("cardmarket.com")
    page = (src / "commander_lab/studio/static/wishlist.js").read_text(encoding="utf-8")
    assert hosts["commander_lab/studio/static/wishlist.js"] == 2
    assert 'const CM_CARD_BASE = "https://www.cardmarket.com/de/Magic/Cards/";' in page
    assert (
        'const CM_SEARCH_BASE = "https://www.cardmarket.com/de/Magic/Products/Search?searchString=";'
        in page
    )
    module = (src / "commander_lab/studio/tam_cardmarket.py").read_text(encoding="utf-8")
    hosts = set(re.findall(r"https://([a-z0-9.]+)", module))
    assert hosts == {"downloads.s3.cardmarket.com"}
    assert 'HOST = "www.cardmarket.com"' in module  # only for the link of the Owner's browser
    download = module[module.index("def http_get(") :]
    # the one request goes to the download base only (checked again at run time in download())
    assert "urllib.request.Request(" in download
    assert "HTTPCookieProcessor" not in module and '"Cookie"' not in module
    assert "ProxyHandler({})" in module and "_NoRedirect" in module
    assert 'USER_AGENT = "CommanderStudio/' in module
    assert module.count("_OPENER.open(") == 1


# --- entered Cardmarket prices (WP-10b) -------------------------------------------------------


def _enter(client: TestClient, deck_id: str, card_id: str, **extra: object) -> httpx.Response:
    return client.post(
        "/api/tam/cardmarket-eintrag", json={"deck_id": deck_id, "card_id": card_id, **extra}
    )


def test_an_entered_price_is_stored_dated_and_shown_first(tmp_path: Path) -> None:
    client, ids = _tam_store(tmp_path)
    today = datetime.now(UTC).date()
    saved = _enter(client, ids["tam_deck"], ids["priced"], eur_text="1.234,5 €")
    assert saved.status_code == 200, saved.text
    assert saved.json() == {
        "card_id": ids["priced"], "status": "value", "eur_cents": 123450,
        "price_date": today.isoformat(), "filter_code": "DE/EX/EN+DE", "link_kind": "karte",
    }  # fmt: skip
    answer = _ask(client, ids["tam_deck"], [ids["priced"]]).json()
    entered = answer["cards"][0]["entered"]
    assert entered == {
        "eur_cents": 123450, "price_date": today.isoformat(), "filter_code": "DE/EX/EN+DE",
        "age_days": 0, "stale": False,
    }  # fmt: skip
    assert answer["cards"][0]["eur_cents"] == 1234  # the approximation stays apart
    # an older date (German form) and other filters; 15 days is stale, 14 is not
    old = today - timedelta(days=15)
    _enter(
        client, ids["tam_deck"], ids["priced"], eur_text="9,99",
        entered_on=old.strftime("%d.%m.%Y"), filter_code="alle/NM/DE",
    )  # fmt: skip
    entered = _ask(client, ids["tam_deck"], [ids["priced"]]).json()["cards"][0]["entered"]
    assert (entered["eur_cents"], entered["stale"], entered["filter_code"]) == (
        999,
        True,
        "alle/NM/DE",
    )
    edge = (today - timedelta(days=14)).isoformat()
    _enter(client, ids["tam_deck"], ids["priced"], eur_text="9,99", entered_on=edge)
    assert (
        _ask(client, ids["tam_deck"], [ids["priced"]]).json()["cards"][0]["entered"]["stale"]
        is False
    )


@pytest.mark.parametrize(
    "text", ["-5", "abc", "12,345", "1.2.3", "1e3", "12,5o", "0,5,0", "1000000000"]
)
def test_unreadable_input_is_refused_and_keeps_the_entry(tmp_path: Path, text: str) -> None:
    """Review P3-3: text that is not a price is a 422 and never deletes a stored entry; only
    empty or 0 removes it (docs/STUDIO_TAM_PREISE.md)."""
    client, ids = _tam_store(tmp_path)
    assert _enter(client, ids["tam_deck"], ids["priced"], eur_text="5").status_code == 200
    refused = _enter(client, ids["tam_deck"], ids["priced"], eur_text=text)
    assert refused.status_code == 422, refused.text
    assert "Preis nicht lesbar" in refused.text
    card = _ask(client, ids["tam_deck"], [ids["priced"]]).json()["cards"][0]
    assert card["entered"]["eur_cents"] == 500
    store = StudioStore.open(tmp_path / "studio")
    assert _rows(store, "tam_cardmarket_price") == 1
    store.close()


@pytest.mark.parametrize("text", ["", "  ", "0", "0,00", "0.0", "0 €", "000"])
def test_empty_or_zero_input_removes_the_entry_never_zero(tmp_path: Path, text: str) -> None:
    client, ids = _tam_store(tmp_path)
    assert _enter(client, ids["tam_deck"], ids["priced"], eur_text="5").status_code == 200
    removed = _enter(client, ids["tam_deck"], ids["priced"], eur_text=text)
    assert removed.status_code == 200 and removed.json()["status"] == "unknown"
    assert removed.json()["eur_cents"] is None
    card = _ask(client, ids["tam_deck"], [ids["priced"]]).json()["cards"][0]
    assert "entered" not in card
    store = StudioStore.open(tmp_path / "studio")
    assert _rows(store, "tam_cardmarket_price") == 0
    with pytest.raises(sqlite3.IntegrityError):  # the table itself refuses a 0 value
        store.connection.execute(
            "INSERT INTO tam_cardmarket_price VALUES ('o-x', 0, '2026-11-20', 't', 'x', NULL)"
        )
    store.close()


def test_entries_follow_the_same_gate_as_the_guide_values(tmp_path: Path) -> None:
    client, ids = _tam_store(tmp_path)
    future = (datetime.now(UTC).date() + timedelta(days=3)).isoformat()
    cases = [
        (ids["chulane_deck"], ids["priced"], {}, 403),  # Chulane: never a price
        (ids["tam_deck"], ids["priced"], {"commander": CHULANE}, 403),
        ("no-such-deck", ids["priced"], {}, 404),
        (ids["tam_deck"], ids["owned"], {}, 422),  # owned: no price
        (ids["tam_deck"], ids["foreign"], {}, 422),  # not in the deck
        (ids["tam_deck"], ids["priced"], {"entered_on": future}, 422),
        (ids["tam_deck"], ids["priced"], {"entered_on": "2026-02-31"}, 422),
        (ids["tam_deck"], ids["priced"], {"entered_on": "gestern"}, 422),
        (ids["tam_deck"], ids["priced"], {"filter_code": "DE/PO/EN"}, 422),
        (ids["tam_deck"], ids["priced"], {"extra": 1}, 422),
        (ids["tam_deck"], ids["priced"], {"branch": "ghost"}, 404),  # never saved
    ]
    for deck_id, card_id, extra, status in cases:
        response = _enter(client, deck_id, card_id, eur_text="3,00", **extra)
        assert response.status_code == status, (extra, response.text)
    main = [_entry(ids["priced"]), _entry(ids["owned"])]
    forged = [
        # a Chulane deck whose draft names TAM as commander: the saved revision decides
        (ids["chulane_deck"], [_entry("card:t:tam", "commander"), *main]),
        # TAM plus a second commander in the draft
        (ids["tam_deck"], [_entry("card:t:tam", "commander"), _entry("card:t:chulane", "commander"), *main]),
        # a commander id that is only the name of TAM (no such card)
        (ids["tam_deck"], [_entry(TAM_COMMANDER_NAME, "commander"), *main]),
        # no commander at all
        (ids["tam_deck"], main),
    ]  # fmt: skip
    for deck_id, cards in forged:
        assert _draft(client, deck_id, cards).status_code == 200
        response = _enter(client, deck_id, ids["priced"], eur_text="3,00")
        assert response.status_code == 403, (deck_id, cards, response.text)
    store = StudioStore.open(tmp_path / "studio")
    assert _rows(store, "tam_cardmarket_price") == 0
    store.close()


# --- Cardmarket price guide (WP-10b) ----------------------------------------------------------


def _guide_store(tmp_path: Path) -> StudioStore:
    """Scryfall facts and a bulk file with cardmarket_id for three cards."""
    from tests.unit.test_studio_builder import _fill, _insert_scryfall

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    for oracle_id, name in (("o-g1", "Guide One"), ("o-g2", "Guide Two"), ("o-g3", "Guide Three")):
        _insert_scryfall(store, oracle_id=oracle_id, name=name, colors="W", type_line="Artifact")
    store.connection.commit()
    cards = [
        _card(
            "o-g1", "s-1a", {"eur": "0.94"}, cardmarket_id=101, set="cmm", collector_number="464"
        ),
        _card("o-g1", "s-1b", {"eur": "1.20"}, cardmarket_id=102, set="sld", collector_number="9"),
        _card("o-g1", "s-1c", {"eur": "0.01"}, cardmarket_id=103, oversized=True),
        _card("o-g2", "s-2a", {"eur": "5.00"}, cardmarket_id=201, set="abc", collector_number="7"),
        _card("o-g3", "s-3a", {"eur": "3.00"}, cardmarket_id=301, set="xyz", collector_number="1"),
        _card("o-g3", "s-3b", {"eur": "2.00"}, cardmarket_id=True),  # not an id
    ]
    report = tam_prices.import_scryfall_prices(
        store, _bulk(tmp_path / "cards.jsonl", cards), bulk_date="2026-11-20"
    )
    assert report["printings_with_cardmarket_id"] == 4  # oversized and the bool id left out
    return store


def _snapshot_name_check(store: StudioStore) -> int:
    row = store.connection.execute(
        "SELECT name_check FROM tam_cardmarket_guide_snapshot WHERE snapshot_id = 1"
    ).fetchone()
    return int(row[0])


def _guide_file(path: Path, guides: list[dict[str, object]], **meta: object) -> Path:
    path.write_text(json.dumps({"version": 1, **meta, "priceGuides": guides}), encoding="utf-8")
    return path


GUIDES = [
    {"idProduct": 101, "low": 0.45, "trend": 0.94, "low-foil": 2.0, "trend-foil": 3.5},
    {"idProduct": 102, "low": 0.6, "trend": 0.9, "low-foil": 0.3, "trend-foil": None},
    {"idProduct": 103, "low": 0.02, "trend": 0.05},  # oversized: no playable printing
    {"idProduct": 201, "low": 0, "trend": -1, "low-foil": "4.00", "trend-foil": 6.25},
    {"idProduct": 301, "low": 1.5, "trend": 2.5},
    {"idProduct": 999, "low": 0.01, "trend": 0.01},  # no known printing
]


def test_the_price_guide_keeps_the_lowest_low_and_trend_over_playable_printings(
    tmp_path: Path,
) -> None:
    store = _guide_store(tmp_path)
    guide = _guide_file(
        tmp_path / "price_guide_1.json", GUIDES, createdAt="2026-11-20T02:43:21+0100"
    )
    products = tmp_path / "products_singles_1.json"
    products.write_text(json.dumps({"products": [
        {"idProduct": 101, "name": "Guide One"}, {"idProduct": 102, "name": "Guide One"},
        {"idProduct": 201, "name": "Guide Two"}, {"idProduct": 301, "name": "Another Name"},
    ]}), encoding="utf-8")  # fmt: skip
    report = tam_prices.import_cardmarket_priceguide(store, guide, products_path=products)
    assert report["guide_date"] == "2026-11-20" and report["date_basis"] == "createdAt"
    assert report["printings_known"] == 4
    assert report["printings_matched"] == 3 and report["name_mismatches"] == 1
    rows = store.connection.execute(
        "SELECT oracle_id, low_cents, low_finish, low_set_code, low_collector_number, "
        "trend_cents FROM tam_cardmarket_guide ORDER BY oracle_id"
    ).fetchall()
    assert [tuple(r) for r in rows] == [
        # the foil of the second printing (0.30) is the lowest low; the lowest trend is 0.90
        ("o-g1", 30, "foil", "sld", "9", 90),
        # low 0, a negative trend and a text low-foil are no values: only trend-foil
        ("o-g2", None, None, None, None, 625),
    ]  # o-g3: its product name differs, left out
    assert _snapshot_name_check(store) == 1
    # without the product list no name check, o-g3 joins, and the snapshot says so
    report = tam_prices.import_cardmarket_priceguide(store, guide)
    assert report["name_check"] is False and report["printings_matched"] == 4
    assert _snapshot_name_check(store) == 0
    # files inside the repository are refused (they hold real prices)
    for kwargs in ({"guide_path": ROOT / "data" / "price_guide_1.json"},
                   {"guide_path": guide, "products_path": ROOT / "data" / "products.json"}):  # fmt: skip
        with pytest.raises(ValueError, match="outside the repository"):
            tam_prices.import_cardmarket_priceguide(store, **kwargs)  # type: ignore[arg-type]
    assert _rows(store, "tam_cardmarket_guide") == 3
    store.close()


def test_the_price_guide_needs_a_date_and_a_guide_list(tmp_path: Path) -> None:
    store = _guide_store(tmp_path)
    plain = _guide_file(tmp_path / "g.json", GUIDES)
    with pytest.raises(ValueError, match="no guide date"):
        tam_prices.import_cardmarket_priceguide(store, plain)
    stamped = _guide_file(tmp_path / "s.json", GUIDES, createdAt="2026-11-20T02:43:21+0100")
    with pytest.raises(ValueError, match="conflict"):
        tam_prices.import_cardmarket_priceguide(store, stamped, guide_date="2026-11-19")
    future = _guide_file(tmp_path / "f.json", GUIDES, createdAt="2099-01-01T00:00:00+0100")
    with pytest.raises(ValueError, match="future"):
        tam_prices.import_cardmarket_priceguide(store, future)
    wrong = tmp_path / "w.json"
    wrong.write_text(json.dumps({"products": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="priceGuides"):
        tam_prices.import_cardmarket_priceguide(store, wrong, guide_date="2026-11-20")
    assert _rows(store, "tam_cardmarket_guide_snapshot") == 0
    report = tam_prices.import_cardmarket_priceguide(store, plain, guide_date="2026-11-18")
    assert report["date_basis"] == "angegeben"
    store.close()


def test_the_cli_imports_a_downloaded_guide_and_the_reader_answers_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from commander_lab.studio.__main__ import main as studio_main

    client, ids = _tam_store(tmp_path)
    store = StudioStore.open(tmp_path / "studio")
    store.connection.execute(
        "INSERT INTO tam_price_print VALUES (501, 'o-tam-priced', 'syn', '5'), "
        "(502, 'o-tam-unknown', 'syn', '6')"
    )
    store.connection.commit()
    store.close()
    guide = _guide_file(
        tmp_path / "price_guide_1.json",
        [{"idProduct": 501, "low": 0.45, "trend": 0.94}, {"idProduct": 502, "trend": 7.0}],
        createdAt="2026-11-20T02:43:21+0100",
    )
    argv = [
        "--data",
        str(tmp_path / "studio"),
        "import-cardmarket-priceguide",
        "--file",
        str(guide),
    ]
    assert studio_main(argv) == 0
    assert '"printings_matched": 2' in capsys.readouterr().out
    answer = _ask(client, ids["tam_deck"], [ids["priced"], ids["unknown"], ids["owned"]]).json()
    assert answer["guide_snapshot"]["guide_date"] == "2026-11-20"
    assert answer["guide_label"] == "Cardmarket-Preisführer"
    assert "ohne Filter Land/Sprache/Zustand" in answer["guide_notice"]
    assert answer["guide_snapshot"]["name_check"] is False  # --file without --products
    cards = {c["card_id"]: c for c in answer["cards"]}
    assert cards[ids["priced"]]["guide"] == {
        "low_cents": 45, "low_finish": "nonfoil", "low_printing": "SYN 5", "trend_cents": 94,
    }  # fmt: skip
    assert cards[ids["unknown"]]["guide"] == {
        "low_cents": None, "low_finish": "", "low_printing": "", "trend_cents": 700,
    }  # fmt: skip
    assert cards[ids["owned"]] == {"card_id": ids["owned"], "status": "owned"}
    # Chulane never sees the guide
    assert _ask(client, ids["chulane_deck"], [ids["priced"]]).status_code == 403


def test_a_csv_of_read_prices_enters_only_cards_of_the_purchase_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from commander_lab.studio.__main__ import main as studio_main

    client, ids = _tam_store(tmp_path)
    store = StudioStore.open(tmp_path / "studio")
    owned_name = store.connection.execute(
        "SELECT oracle_name FROM card WHERE card_id = ?", (ids["owned"],)
    ).fetchone()[0]
    store.close()
    today = datetime.now(UTC).date().isoformat()
    sheet = tmp_path / "preise.csv"
    sheet.write_text(
        "Name;Preis;Datum\n"
        "Walker priced;12,50;20.11.2026\n"
        "walker unknown;3;\n"
        f"{owned_name};1,00;\n"
        "Walker foreign;4,00;\n"
        "Nobody;1;\n"
        "Walker priced;abc;2099-01-01\n",
        encoding="utf-8",
    )
    argv = [
        "--data",
        str(tmp_path / "studio"),
        "import-tam-cardmarket-csv",
        ids["tam_deck"],
        str(sheet),
    ]
    assert studio_main(argv) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["stored"] == 2 and report["filter_code"] == "DE/EX/EN+DE"
    assert [s["line"] for s in report["skipped"]] == [4, 5, 6, 7]  # owned, foreign, unknown, future
    answer = _ask(client, ids["tam_deck"], [ids["priced"], ids["unknown"]]).json()
    entered = {c["card_id"]: c["entered"] for c in answer["cards"]}
    assert entered[ids["priced"]]["eur_cents"] == 1250
    assert entered[ids["priced"]]["price_date"] == "2026-11-20"
    assert entered[ids["unknown"]] | {"age_days": 0} == {
        "eur_cents": 300, "price_date": today, "filter_code": "DE/EX/EN+DE", "age_days": 0,
        "stale": False,
    }  # fmt: skip
    # a price file inside the repository is refused; Chulane decks are refused
    store = StudioStore.open(tmp_path / "studio")
    with pytest.raises(ValueError, match="outside the repository"):
        tam_prices.import_cardmarket_csv(store, ids["tam_deck"], ROOT / "data" / "preise.csv")
    with pytest.raises(tam_prices.NotTamError):
        tam_prices.import_cardmarket_csv(store, ids["chulane_deck"], sheet)
    store.close()


def test_the_owner_exception_is_recorded_where_the_rules_are() -> None:
    """The Cardmarket price guide download rests on the Owner exception of 2026-11-22: the
    register quotes it with its limits, AGENTS.md names it in §8 and §12, the source register
    lists the price guide honestly as unclear."""
    register = (ROOT / "docs/OWNER_DECISIONS_STUDIO_20261118.md").read_text(encoding="utf-8")
    entry = register[register.index("#### Owner-Ausnahme Cardmarket für den TAM-Zukauf") :]
    entry = entry[: entry.index("Preis-Wächter beim Bau")]
    for needed in (
        "„Bitte die Regel für hier aufheben",
        "„Wieso kannst du dich nicht darum kümmern die Preise selber zu scrapen? Will kein Skript bei",
        "UNBELEGT",
        "liegt beim Owner",
        "Umgehung von Zugangsschutz",
        "ohne Filter Land/Sprache/Zustand",
        "`unclear`",
        "Kommentar 7077232382",
        "„Ja passt, das mit dem direkt abfragen auch gut, mach weiter“",
        "https://www.cardmarket.com/de/Magic/Cards/Rograkh-Son-of-Rohgahh?sellerCountry=7&language=1,3&minCondition=3",
        "Co-Lead-Auslegung, kein Owner-Wortlaut",
    ):
        assert needed in entry, needed
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.count("Owner exception of 2026-11-22") == 2
    assert "never circumventing access protection" in agents
    # review P3-8: both places mark the price guide as a Co-Lead reading to be confirmed
    assert (
        agents.count(
            "Owner's words do not name the price guide, it came afterwards as the\nreplacement, "
            "#1637 comment 7077232382; to be confirmed at acceptance"
        )
        == 1
    )
    assert (
        agents.count(
            "(Co-Lead reading, register: the\nOwner's words lift the scraping rule for these prices "
            "but do not name the price guide, which came\nafterwards as the replacement, #1637 "
            "comment 7077232382; to be confirmed at acceptance)"
        )
        == 1
    )
    from commander_lab.studio.sources import get_source

    guide = get_source("cardmarket:price-guide")
    assert guide.access_status == "unclear" and guide.status == "REVIEW"
    assert "UNBELEGT" in guide.license_terms
    guide_doc = (ROOT / "docs/STUDIO_TAM_PREISE.md").read_text(encoding="utf-8")
    assert "import-cardmarket-priceguide" in guide_doc and "Stichprobe" in guide_doc
    # review P3-8: the approximation steps in for a missing and for a stale price guide; no
    # page is read by the price module
    assert "nur wenn der Preisführer die Karte nicht hat oder veraltet ist |" in guide_doc
    assert "Leer oder 0 löscht den Eintrag (dann „unbekannt“). Unlesbarer Text" in guide_doc
    doc = tam_prices.__doc__ or ""
    assert "page reads" not in doc and "Cardmarket price guide and entries" in doc
    assert "no price guide value is there or the price guide is stale" in doc


# Owner wording of 2026-11-22, character for character as recorded by the Co-Lead in #1637,
# comment 7077232382 (sentence 5: only the quoted Owner part; the parenthesis is Co-Lead text).
OWNER_SENTENCES = (
    "„ich will eigentlich für die Zukäufe speziell die cardmarket Preise deutscher Anbieter und "
    "da das günstigste jeder Variante der Karte (egal ob foil, etc (manchmal sind auch foil "
    "günstiger)) und mind excellent Zustand“",
    "„Kannst die cardmarket Preise nicht einfach über den richtigen link (wo die Filter schon "
    "passend eingestellt sind) nicht scrapen? Das wäre z.b. der richtige link für Rograkh dafür: "
    "https://www.cardmarket.com/de/Magic/Cards/Rograkh-Son-of-Rohgahh"
    "?sellerCountry=7&language=1,3&minCondition=3“",
    "„Bitte die Regel für hier aufheben und kümmer dich vollständig darum dir die Preise so zu "
    "besorgen wie ich meinte“",
    "„Wieso kannst du dich nicht darum kümmern die Preise selber zu scrapen? Will kein Skript bei "
    "meinem Browser laufen lassen, entweder du kümmerst dich selber vollständig drum oder wir "
    "weichen auf etwas anderes aus was die Preise der karten auch möglichst gut repräsentiert und "
    "du aber automatisch suchen kannst“",
    "„Ja passt, das mit dem direkt abfragen auch gut, mach weiter“",
)


def test_the_register_quotes_the_five_owner_sentences_whole_and_in_order() -> None:
    """Review P3-5(b): each Owner sentence is pinned whole (a cut or changed word is red), with
    its number, in the order of comment 7077232382."""
    register = (ROOT / "docs/OWNER_DECISIONS_STUDIO_20261118.md").read_text(encoding="utf-8")
    entry = register[register.index("#### Owner-Ausnahme Cardmarket für den TAM-Zukauf") :]
    entry = " ".join(entry[: entry.index("Preis-Wächter beim Bau")].split())
    positions = []
    for number, sentence in enumerate(OWNER_SENTENCES, start=1):
        numbered = f"{number}. {sentence}"
        assert entry.count(numbered) == 1, numbered
        positions.append(entry.index(numbered))
    assert positions == sorted(positions)


def test_agents_section_12_keeps_the_risk_and_the_daily_limit() -> None:
    """Review P3-5(c): §12 names the unverified terms, the Owner's risk and the limit of one
    request per file and day; deleting any of them is red."""
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    section = agents[agents.index("## 12. Privacy") : agents.index("## 13. ")]
    section = " ".join(section.split())
    for needed in (
        "on the Owner's command only, once per file and day, with an honest User-Agent, "
        "stopping at any status other than 200 and never circumventing access protection",
        "the terms on automated retrieval are unverified and the risk lies with the Owner",
        "no Cardmarket page is read",
    ):
        assert needed in section, needed


def test_a_bool_is_no_product_id_of_the_price_guide(tmp_path: Path) -> None:
    """Review P3-9: JSON ``true`` never matches the printing with Cardmarket id 1."""
    store = _guide_store(tmp_path)
    store.connection.execute("INSERT INTO tam_price_print VALUES (1, 'o-g2', 'one', '1')")
    store.connection.commit()
    guide = _guide_file(
        tmp_path / "price_guide_1.json",
        [{"idProduct": True, "low": 0.11, "trend": 0.22}],
        createdAt="2026-11-20T02:43:21+0100",
    )
    report = tam_prices.import_cardmarket_priceguide(store, guide)
    assert report["printings_matched"] == 0
    assert _rows(store, "tam_cardmarket_guide") == 0
    store.close()


def test_products_without_file_is_an_error_and_asks_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review P3-9: ``--products`` without ``--file`` stops with a hint before any download."""
    from commander_lab.studio import tam_cardmarket
    from commander_lab.studio.__main__ import main as studio_main

    def refuse(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("no download may start")

    monkeypatch.setattr(tam_cardmarket, "download", refuse)
    monkeypatch.setattr(tam_cardmarket, "http_get", refuse)
    products = tmp_path / "products_singles_1.json"
    products.write_text('{"products": []}', encoding="utf-8")
    argv = ["--data", str(tmp_path / "studio"), "import-cardmarket-priceguide",
            "--products", str(products)]  # fmt: skip
    with pytest.raises(SystemExit, match="--products gilt nur zusammen mit --file"):
        studio_main(argv)


# The "Bleibt" guards of the register entry "Preise für TAM" (repository data, Chulane, rating)
# stay as they are: each listed file still holds its price check.
_KEPT_GUARDS = {
    "scripts/data_wave1/_common.py": ('PRICE_KEYS = frozenset({"prices", "purchase_uris"})',),
    "tests/unit/test_audit_committed_research_data.py": (
        'assert all("price" not in col.lower() for col in fieldnames)',
    ),
    "tests/unit/test_studio_strength.py": (
        'assert not any("price" in str(row[0]) for row in db.execute("SELECT signal FROM card_signal"))',
    ),
    "tests/unit/test_studio_swap.py": (
        'for forbidden in ("kaufen", "zukauf", "preis", "eur", "usd", "$", "€"):',
    ),
    "tests/unit/test_studio_card_duel.py": (
        '"price",',
        'assert "besser" not in text and "preis" not in text and "price" not in text',
    ),
    "tests/unit/test_studio_db_a_1404.py": (
        "FORBIDDEN_PURCHASE_TERMS = (",
        '"purchase",',
        "for term in FORBIDDEN_PURCHASE_TERMS:",
    ),
    "tests/unit/test_studio_data_page.py": (
        'for forbidden in ("preis", "euro", "dollar", "kaufen", "empfehl"):',
    ),
}


def test_the_kept_price_guards_are_unchanged() -> None:
    assert len(_KEPT_GUARDS) == 7
    for relative, needles in _KEPT_GUARDS.items():
        assert needles
        text = (ROOT / relative).read_text(encoding="utf-8")
        for needle in needles:
            assert needle in text, (relative, needle)


def test_a_price_guide_older_than_14_days_is_marked_stale(tmp_path: Path) -> None:
    client, ids = _tam_store(tmp_path)
    today = datetime.now(UTC).date()
    for age, stale in ((14, False), (15, True), (0, False)):
        store = StudioStore.open(tmp_path / "studio")
        _seed_cardmarket(
            store, {"o-tam-priced": 45}, {}, day=(today - timedelta(days=age)).isoformat()
        )
        store.close()
        snap = _ask(client, ids["tam_deck"], [ids["priced"]]).json()["guide_snapshot"]
        assert (snap["age_days"], snap["stale"], snap["name_check"]) == (age, stale, True)
