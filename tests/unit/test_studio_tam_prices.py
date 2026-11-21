"""TAM purchase guide values, stage 1 (#1637, register entry "Preise für TAM").

Only synthetic price values (no real Scryfall prices). The guards prove: the field prices.eur
goes only into the local store tables, only the commander TAM gets values and only for cards not
owned, a missing value is unknown (never 0), and no strength, swap, cut, pool or card answer
carries or is ordered by a guide value.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, builder, cache, state_export, tam_prices
from commander_lab.studio.tam_import import TAM_COMMANDER_NAME
from commander_lab.studio.web import create_app

ROOT = Path(__file__).resolve().parents[2]
HEADER = {"X-Studio": "1"}
SENTINEL_CENTS = 987_654  # synthetic, appears nowhere else
PRICE_TABLES = frozenset({"tam_price_eur", "tam_price_snapshot"})
LEAK_MARKERS = ("eur_cents", "tam_price", "richtwert", "prices.eur", "987654")


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
    assert report["cards_with_value"] == 1
    assert report["cards_without_value"] == 4  # o-b (foil only), o-c (0.00), o-d, o-e
    rows = store.connection.execute(
        "SELECT oracle_id, eur_cents, scryfall_id FROM tam_price_eur"
    ).fetchall()
    assert [tuple(row) for row in rows] == [("o-a", 175, "s-a2")]  # eur_foil 0.10 not read
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
    assert answer["kind"] == "Richtwert"
    assert answer["source"] == "Scryfall prices.eur (lokale Bulk-Datei)"
    assert answer["snapshot"]["bulk_date"] == "2026-11-20"
    assert "nicht Deutschland" in answer["notice"] and "kein Angebot" in answer["notice"]
    assert "günstigste Angebot" in answer["notice"]  # only as a negation
    assert answer["not_in_deck"] == 0
    assert answer["cards"] == [
        {"card_id": ids["priced"], "status": "value", "eur_cents": 1234},
        {"card_id": ids["unknown"], "status": "unknown"},
        # owned in the collection: no value although the snapshot has one for its oracle_id
        {"card_id": ids["owned"], "status": "owned"},
    ]
    # a card of no deck (with a value row) is left out and counted, never answered
    mixed = _ask(client, ids["tam_deck"], [ids["foreign"], ids["priced"]]).json()
    assert mixed["cards"] == [{"card_id": ids["priced"], "status": "value", "eur_cents": 1234}]
    assert mixed["not_in_deck"] == 1 and "777" not in json.dumps(mixed)


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
    assert answer["cards"] == [{"card_id": ids["later"], "status": "value", "eur_cents": 888}]
    # a Chulane draft never turns into a TAM answer
    chulane = [{"card_id": "card:t:chulane", "quantity": 1, "zone": "commander"}, *cards[1:]]
    client.put(f"/api/decks/{ids['chulane_deck']}/branches/main/draft", json={"cards": chulane})
    assert _ask(client, ids["chulane_deck"], [ids["later"]]).status_code == 403


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
    store.close()
    cache.invalidate()
    with_values = _answers(client, cmd_id, "rem-high")
    assert with_values == without


def test_no_answer_holds_a_price_field_or_value(tmp_path: Path) -> None:
    """Scan guard: with a sentinel value for every card, no answer of the pool (TAM and Chulane
    included), strength, swap, cut lab, alternatives or card page names a price field or holds
    the value."""
    store, cmd_id = _leak_store(tmp_path)
    _seed_prices(store, dict.fromkeys(_all_oracle_ids(store), SENTINEL_CENTS))
    store.close()
    cache.invalidate()
    client = TestClient(create_app(tmp_path / "studio"), headers=HEADER)
    answers = _answers(client, cmd_id, "rem-high")
    assert len(answers) == 33
    for name, answer in answers.items():
        text = json.dumps(answer, ensure_ascii=False).casefold()
        for marker in LEAK_MARKERS:
            assert marker not in text, (name, marker)


def test_price_tables_stay_out_of_the_user_state_export() -> None:
    assert not (PRICE_TABLES & state_export._TABLE_NAMES)


def test_the_local_store_refuses_the_repository(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="outside the repository"):
        StudioStore.open(ROOT / "data" / "tam-prices-guard")


# Committed data carries no price values: no price key with a figure in the tracked data,
# source and script files. ``tests/`` holds synthetic values only and is not scanned here; the
# real Scryfall prices in ``tests/fixtures/scryfall_default_cards_fixture.jsonl`` predate #1637
# and are reported in the pull request for a separate decision.
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


# Structural guard: the guide values have one reader. The table names and the value field occur
# only where the tables are declared (schema, cache group, source register text) and in the one
# module that writes and reads them; that module is imported only by the TAM route and the CLI,
# and in web.py only the TAM route and its body model use it. A new route that reads the values
# (e.g. a MAX(eur_cents) into a ranking) fails here even when no answer test calls it.
_VALUE_NAMES = re.compile(r"tam_price_eur|tam_price_snapshot|eur_cents")
# the display of the TAM purchase list (static/wishlist.js) reads eur_cents of the route answer
_VALUE_FILES = frozenset(
    {"tam_prices.py", "store.py", "cache.py", "sources.py", "static/wishlist.js"}
)
_MODULE_USERS = frozenset({"web.py", "__main__.py"})


def test_guide_values_have_one_reader_in_src() -> None:
    src = ROOT / "src"
    files = sorted(
        path
        for path in src.rglob("*")
        if path.is_file() and path.suffix in {".py", ".js", ".html", ".sql"}
    )
    assert len(files) > 100
    by_value = {
        p.relative_to(src).as_posix()
        for p in files
        if _VALUE_NAMES.search(p.read_text(encoding="utf-8"))
    }
    assert by_value == {f"commander_lab/studio/{name}" for name in _VALUE_FILES}
    module_users = {
        p.relative_to(src).as_posix()
        for p in files
        if p.name != "tam_prices.py" and re.search(r"\btam_prices\b", p.read_text(encoding="utf-8"))
    }
    assert module_users == {f"commander_lab/studio/{name}" for name in _MODULE_USERS}
    web = (src / "commander_lab/studio/web.py").read_text(encoding="utf-8")
    body = web[web.index("class TamPurchaseBody(BaseModel):") :]
    body = body[: body.index("\nclass ")]
    route = web[web.index('    @app.post("/api/tam/zukauf-richtwerte")') :]
    route = route[: route.index("\n    @app.")]
    uses = len(re.findall(r"\btam_prices\.", web))
    assert uses == len(re.findall(r"\btam_prices\.", body)) + len(
        re.findall(r"\btam_prices\.", route)
    )
    assert uses >= 3 and web.count("tam_prices,") == 1  # the import line
    main = (src / "commander_lab/studio/__main__.py").read_text(encoding="utf-8")
    assert len(re.findall(r"\btam_prices\.", main)) == 1  # import-tam-prices only
