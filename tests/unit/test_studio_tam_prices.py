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
    assert _rows(store, "tam_price_snapshot") == 0  # refused, nothing written
    tam_prices.import_scryfall_prices(store, plain, bulk_date="2026-11-19")
    later = _bulk(tmp_path / "later.jsonl", [_card("o-z", "s-z", {"eur": "4.20"})])
    report = tam_prices.import_scryfall_prices(store, later, bulk_date="2026-11-21")
    assert report["date_basis"] == "angegeben"
    rows = store.connection.execute("SELECT oracle_id, eur_cents FROM tam_price_eur").fetchall()
    assert [tuple(row) for row in rows] == [("o-z", 420)]  # the old snapshot is gone
    assert _rows(store, "tam_price_snapshot") == 1
    store.close()


def _tam_store(tmp_path: Path) -> tuple[StudioStore, dict[str, str]]:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    owned = store.connection.execute(
        "SELECT c.card_id, c.oracle_id FROM card c JOIN inventory i ON i.card_id = c.card_id "
        "WHERE i.owned_lower_bound > 0 AND c.oracle_id IS NOT NULL ORDER BY c.card_id LIMIT 1"
    ).fetchone()
    ids = {"owned": str(owned["card_id"]), "owned_oracle": str(owned["oracle_id"])}
    ids["priced"] = "scryfall:o-tam-priced"
    ids["unknown"] = "scryfall:o-tam-unknown"
    return store, ids


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


def test_only_tam_gets_values_and_only_for_cards_not_owned(tmp_path: Path) -> None:
    store, ids = _tam_store(tmp_path)
    wanted = [ids["priced"], ids["unknown"], ids["owned"]]
    # without a snapshot: every card unknown, no value field anywhere
    empty = tam_prices.purchase_guide_values(store, TAM_COMMANDER_NAME, wanted)
    assert empty["snapshot"] is None
    assert [c["status"] for c in empty["cards"]] == ["unknown", "unknown", "owned"]
    assert "eur_cents" not in json.dumps(empty)
    _seed_prices(store, {"o-tam-priced": 1234, ids["owned_oracle"]: 555})
    answer = tam_prices.purchase_guide_values(store, TAM_COMMANDER_NAME, wanted)
    assert answer["kind"] == "Richtwert"
    assert answer["source"] == "Scryfall prices.eur (lokale Bulk-Datei)"
    assert answer["snapshot"]["bulk_date"] == "2026-11-20"
    assert "nicht Deutschland" in str(answer["notice"]) and "kein Angebot" in str(answer["notice"])
    assert "günstigste Angebot" in str(answer["notice"])  # only as a negation
    cards = {c["card_id"]: c for c in answer["cards"]}
    assert cards[ids["priced"]] == {"card_id": ids["priced"], "status": "value", "eur_cents": 1234}
    assert cards[ids["unknown"]] == {"card_id": ids["unknown"], "status": "unknown"}
    # owned in the collection: no value although the snapshot has one for its oracle_id
    assert cards[ids["owned"]] == {"card_id": ids["owned"], "status": "owned"}
    for other in ("Chulane, Teller of Tales", "Test Commander", "tam, the possibility", ""):
        with pytest.raises(tam_prices.NotTamError):
            tam_prices.purchase_guide_values(store, other, wanted)
    store.close()


def test_route_refuses_chulane_and_serves_tam(tmp_path: Path) -> None:
    store, ids = _tam_store(tmp_path)
    _seed_prices(store, {"o-tam-priced": 1234})
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers=HEADER)
    refused = client.post(
        "/api/tam/zukauf-richtwerte",
        json={"commander": "Chulane, Teller of Tales", "card_ids": [ids["priced"]]},
    )
    assert refused.status_code == 403
    assert "eur_cents" not in refused.text and "1234" not in refused.text
    served = client.post(
        "/api/tam/zukauf-richtwerte",
        json={"commander": TAM_COMMANDER_NAME, "card_ids": [ids["priced"], ids["owned"]]},
    )
    assert served.status_code == 200
    assert [c.get("eur_cents") for c in served.json()["cards"]] == [1234, None]
    too_many = client.post(
        "/api/tam/zukauf-richtwerte",
        json={"commander": TAM_COMMANDER_NAME, "card_ids": [f"x{i}" for i in range(251)]},
    )
    assert too_many.status_code == 422


CHULANE = "Chulane, Teller of Tales"
WALKERS = (("o-leak-walker-a", "Leak Walker Alpha"), ("o-leak-walker-b", "Leak Walker Beta"))


def _leak_store(tmp_path: Path) -> tuple[StudioStore, str]:
    """The swap store plus TAM and Chulane in the collection and unowned WUBRG planeswalkers:
    the commander with a live guide-value path, the one that must never get one, and Zukauf
    candidates that have a value row."""
    from tests.unit.test_studio_builder import _insert_scryfall
    from tests.unit.test_studio_swap import _seed_swap_store

    store = _seed_swap_store(tmp_path)
    cmd_id = str(builder.pool_cards(store, ["Test Commander"])["commander_ids"][0])
    db = store.connection
    source_id = str(db.execute("SELECT source_id FROM card LIMIT 1").fetchone()[0])
    for card_id, oracle_id, name, colors in (
        ("card:leak:tam", "o-leak-tam", TAM_COMMANDER_NAME, "WUBRG"),
        ("card:leak:chulane", "o-leak-chulane", CHULANE, "WUG"),
    ):
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
    for oracle_id, name in WALKERS:
        _insert_scryfall(
            store,
            oracle_id=oracle_id,
            name=name,
            colors="WU",
            type_line="Legendary Planeswalker — Test",
        )
    db.commit()
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
    assert len(answers) == 14
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
