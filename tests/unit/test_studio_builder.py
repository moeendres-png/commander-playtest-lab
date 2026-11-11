"""Studio deck builder: public card data, read models, drafts and the local web application.

All data here is synthetic.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import (
    RevisionCard,
    StudioStore,
    builder,
    catalog,
    create_revision,
    importers,
    roles,
)
from commander_lab.studio.decks import lab_snapshot, list_rows, validate_rows
from commander_lab.studio.images import cached_image, image_address
from commander_lab.studio.store import SCHEMA_VERSION
from commander_lab.studio.web import create_app
from tests.unit.test_studio_store import (
    _card_row,
    _register_row,
    _synthetic_cards,
    _workbook,
    _write_csv,
)

IMAGE = "https://cards.scryfall.io/normal/front/a/b/{}.jpg"


def _public(name: str, colors: list[str], type_line: str, **extra: object) -> dict[str, object]:
    slug = name.casefold().replace(" ", "-").replace("/", "")
    card: dict[str, object] = {
        "id": f"print-{slug}",
        "oracle_id": f"oracle-{slug}",
        "name": name,
        "layout": "normal",
        "mana_cost": "{1}{G}",
        "cmc": 2.0,
        "type_line": type_line,
        "oracle_text": "",
        "color_identity": colors,
        "legalities": {"commander": "legal"},
        "keywords": [],
        "image_uris": {"normal": IMAGE.format(slug)},
    }
    card.update(extra)
    return card


def _public_file(path: Path) -> Path:
    cards = [
        _public("Test Commander", ["G", "U", "W"], "Legendary Creature — Human Druid"),
        _public("Forest", ["G"], "Basic Land — Forest", mana_cost="", cmc=0.0, produced_mana=["G"]),
        _public("Red Outsider", ["R"], "Creature — Goblin"),
        _public("Banned Relic", [], "Artifact", legalities={"commander": "banned"}),
        _public("Unverified Charm", ["U"], "Instant"),
        # the workbook says G; the public data says GW
        _public("Reserved Bear", ["G", "W"], "Creature — Bear"),
        _public("Swarm Rat", ["W"], "Creature — Rat",
                oracle_text="A deck can have any number of cards named Swarm Rat."),
        _public("Token Thing", ["G"], "Token Creature", layout="token"),
        {
            "id": "print-two-face",
            "oracle_id": "oracle-two-face",
            "name": "Filler 00 // Hidden Back",
            "layout": "transform",
            "cmc": 3.0,
            "type_line": "Creature — Wolf // Land",
            "color_identity": ["G"],
            "legalities": {"commander": "legal"},
            "card_faces": [
                {"name": "Filler 00", "mana_cost": "{2}{G}", "oracle_text": "Front.",
                 "image_uris": {"normal": IMAGE.format("two-face-front")}},
                {"name": "Hidden Back", "mana_cost": "", "oracle_text": "Back.",
                 "image_uris": {"normal": IMAGE.format("two-face-back")}},
            ],
        },
    ]  # fmt: skip
    cards += [_public(f"Filler {i:02d}", ["GWU"[i % 3]], "Creature") for i in range(1, 70)]
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write("[\n" + ",\n".join(json.dumps(card) for card in cards) + "\n]\n")
    return path


def _fill(store: StudioStore, folder: Path) -> dict[str, object]:
    importers.import_inventory_workbook(store, _workbook(folder / "cards.xlsx", _synthetic_cards()))
    register = _write_csv(
        folder / "register.csv",
        [
            _register_row("d1", "community"),
            _register_row("d2", "community"),
            _register_row("d3", "turnier_cedh"),
            _register_row("d4", "community", duplicate_of="d1"),
        ],
    )
    rows = [
        {**_card_row("d1", "Forest", 30), "oracle_id": "oracle-forest"},
        {**_card_row("d1", "Swarm Rat"), "oracle_id": "oracle-swarm-rat"},
        {**_card_row("d2", "Forest", 36), "oracle_id": "oracle-forest"},
        {**_card_row("d3", "Swarm Rat"), "oracle_id": "oracle-swarm-rat"},
        {**_card_row("d3", "Unknown Card"), "oracle_id": ""},
        {**_card_row("d4", "Swarm Rat"), "oracle_id": "oracle-swarm-rat"},
    ]
    importers.import_corpus_register(store, register)
    importers.import_corpus_cards(store, _write_csv(folder / "cards.csv", rows))
    report = catalog.import_scryfall_oracle(store, _public_file(folder / "oracle.jsonl.gz"))
    cohort = _write_csv(folder / "cohort.csv", [{"deck_id": "d1"}, {"deck_id": "nope"}])
    assert catalog.import_cohort(store, cohort, cohort="picked") == {
        "cohort": "picked",
        "decks": 1,
        "unknown_decks": 1,
    }
    return report


@pytest.fixture
def studio(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    return store


def _deck() -> list[RevisionCard]:
    cards = [RevisionCard("card:project:0001", 1, "commander")]
    cards += [RevisionCard(f"card:project:{100 + i:04d}") for i in range(70)]
    cards.append(RevisionCard("card:project:0002", 29))
    return cards


def test_public_card_data_links_the_collection_and_reports_differences(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    report = _fill(store, tmp_path)
    assert report["oracle_cards"] == 77  # the token is left out
    assert report["linked"] == 77
    assert report["unlinked"] == []
    assert report["fact_differences"] == [
        {"oracle_name": "Reserved Bear", "field": "color_identity", "workbook": "G",
         "public": "WG"},
    ]  # fmt: skip
    fact = store.connection.execute(
        "SELECT * FROM card_fact WHERE oracle_name = 'Filler 00'"
    ).fetchone()
    assert fact["engine_name"] == "Filler 00"
    assert fact["fact_source"] == "scryfall"
    assert fact["mana_cost"] == "{2}{G}"
    assert fact["image_back"] == IMAGE.format("two-face-back")
    # the public legality wins over an unknown workbook value
    charm = store.connection.execute(
        "SELECT commander_legal FROM card_fact WHERE oracle_name = 'Unverified Charm'"
    ).fetchone()
    assert charm["commander_legal"] == 1


def test_an_older_store_is_upgraded_in_place(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path)
    store.connection.execute("UPDATE meta SET value = '1' WHERE key = 'schema_version'")
    store.connection.commit()
    store.close()
    again = StudioStore.open(tmp_path)
    row = again.connection.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    assert row["value"] == str(SCHEMA_VERSION)
    assert again.count("scryfall_card") == 0


def test_pool_carries_counts_with_denominators(studio: StudioStore) -> None:
    pool = builder.pool_cards(studio, ["Test Commander"])
    assert pool["identity"] == "WUG"
    assert pool["cohorts"] == {"all": 3, "community": 2, "turnier_cedh": 1, "picked": 1}
    cards = {card["name"]: card for card in pool["cards"]}  # type: ignore[union-attr]
    assert "Banned Relic" not in cards
    assert "Red Outsider" not in cards
    assert cards["Swarm Rat"]["decks"] == {"all": 2, "community": 1, "turnier_cedh": 1, "picked": 1}
    assert cards["Forest"]["basic"] is True
    assert cards["Forest"]["group"] == "Land"
    assert cards["Filler 00"]["has_back"] is True
    assert cards["Filler 01"]["decks"] == {}
    assert cards["Filler 01"]["edhrec"] is None
    with pytest.raises(KeyError):
        builder.pool_cards(studio, ["Nobody"])


def test_source_deck_shapes_leave_out_unresolved_decks(studio: StudioStore) -> None:
    shapes = {shape["cohort"]: shape for shape in builder.cohort_shapes(studio)}
    assert shapes["all"]["decks"] == 3
    assert shapes["all"]["decks_counted"] == 2
    assert shapes["community"]["lands"] == {"median": 33.0, "p25": 31.5, "p75": 34.5}
    assert shapes["turnier_cedh"]["decks_counted"] == 0
    assert "lands" not in shapes["turnier_cedh"]
    assert shapes["picked"]["decks"] == 1


def test_deck_shape_and_check_work_on_an_unsaved_list(studio: StudioStore) -> None:
    rows = list_rows(studio, _deck())
    assert validate_rows(rows) == []
    shape = builder.deck_shape(rows)
    assert shape["cards"] == 100
    assert shape["lands"] == 29
    assert shape["nonland"] == 70
    assert shape["mana_sources"] == {"G": 29}
    assert shape["curve"]["2"] == 69  # type: ignore[index]
    assert shape["curve"]["3"] == 1  # type: ignore[index]
    assert shape["pips"] == {"G": 70}
    too_many = [*_deck(), RevisionCard("card:project:0003")]
    codes = {issue.code for issue in validate_rows(list_rows(studio, too_many))}
    assert codes == {"deck_size", "color_identity"}


def test_snapshot_uses_the_engine_name(studio: StudioStore) -> None:
    revision = create_revision(studio, deck_id="test", name="Test", cards=_deck())
    names = {card["oracle_name"] for card in lab_snapshot(studio, revision)["cards"]}  # type: ignore[union-attr]
    assert "Filler 00" in names


def test_drafts_marks_and_listing(studio: StudioStore) -> None:
    revision = create_revision(studio, deck_id="test", name="Test", cards=_deck())
    assert builder.read_draft(studio, "test", "main") is None
    builder.write_draft(studio, "test", "main", _deck()[:5], revision)
    draft = builder.read_draft(studio, "test", "main")
    assert draft is not None
    assert len(draft["cards"]) == 5  # type: ignore[arg-type]
    listed = builder.list_decks(studio)
    assert listed[0]["branches"][0]["has_draft"] == 1  # type: ignore[index]
    builder.drop_draft(studio, "test", "main")
    assert builder.read_draft(studio, "test", "main") is None
    builder.set_mark(studio, "card:project:0007", favorite=True, excluded=False, note="try it")
    pool = builder.pool_cards(studio, ["Test Commander"])
    rat = next(card for card in pool["cards"] if card["name"] == "Swarm Rat")  # type: ignore[union-attr]
    assert (rat["favorite"], rat["note"]) == (True, "try it")
    with pytest.raises(KeyError):
        builder.set_mark(studio, "card:project:9999", favorite=True, excluded=False, note="")
    assert builder.history(studio, "test")[0]["cards"] == 100


def test_images_come_from_the_cache_and_only_from_the_image_host(
    studio: StudioStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("no network in tests")

    monkeypatch.setattr("urllib.request.urlopen", no_network)
    assert image_address(studio, "card:project:0002") == (
        "oracle-forest",
        IMAGE.format("forest"),
    )
    assert image_address(studio, "card:project:0002", "back") is None
    assert cached_image(studio, "card:project:0002", fetch=False) is None
    assert studio.path is not None
    (studio.path.parent / "images" / "oracle-forest-front.jpg").write_bytes(b"jpeg")
    assert cached_image(studio, "card:project:0002") is not None
    studio.connection.execute(
        "UPDATE scryfall_card SET image_front = 'https://example.invalid/x.jpg' "
        "WHERE oracle_id = 'oracle-swarm-rat'"
    )
    assert cached_image(studio, "card:project:0007") is None  # foreign host is never fetched


def test_web_application_round_trip(studio: StudioStore) -> None:
    assert studio.path is not None
    folder = studio.path.parent
    studio.close()
    marker = {"X-Studio": "1"}
    with TestClient(create_app(folder)) as client:
        assert client.get("/").status_code == 200
        assert "script-src 'self'" in client.get("/").headers["content-security-policy"]
        assert client.get("/api/status").json()["cards"] == 77
        pool = client.get("/api/pool", params={"commander": "Test Commander"}).json()
        assert len(pool["commander_ids"]) == 1
        assert client.get("/api/pool", params={"commander": "Nobody"}).status_code == 404
        # writes need the request marker, and the host must be local
        body = {"name": "Mein Deck", "commander_card_ids": pool["commander_ids"]}
        assert client.post("/api/decks", json=body).status_code == 403
        assert client.get("/api/status", headers={"host": "evil.example"}).status_code == 403
        created = client.post("/api/decks", json=body, headers=marker).json()
        assert created["deck_id"] == "mein-deck"
        second = client.post("/api/decks", json=body, headers=marker).json()
        assert second["deck_id"] == "mein-deck-2"
        cards = [{"card_id": c.card_id, "quantity": c.quantity, "zone": c.zone} for c in _deck()]
        checked = client.post("/api/check", json={"cards": cards[:10]}, headers=marker).json()
        assert [issue["code"] for issue in checked["issues"]] == ["deck_size"]
        draft_url = "/api/decks/mein-deck/branches/main/draft"
        assert client.put(draft_url, json={"cards": cards[:10]}, headers=marker).status_code == 200
        assert len(client.get(draft_url).json()["draft"]["cards"]) == 10
        saved = client.post(
            "/api/decks/mein-deck/revisions",
            json={"cards": cards, "branch": "main", "note": "erste Fassung"},
            headers=marker,
        ).json()
        assert client.get(draft_url).json()["draft"] is None
        revision = client.get(f"/api/revisions/{saved['revision_id']}").json()
        assert revision["issues"] == []
        assert revision["shape"]["cards"] == 100
        text = client.get(f"/api/revisions/{saved['revision_id']}/export").text
        assert "1 Test Commander" in text
        assert "29 Forest" in text
        snapshot = client.get(
            f"/api/revisions/{saved['revision_id']}/export", params={"format": "json"}
        ).json()
        assert snapshot["commander"]["commanders"] == ["Test Commander"]
        assert len(client.get("/api/decks/mein-deck/history").json()) == 2
        unknown = [{"card_id": "card:project:9999"}]
        assert (
            client.post(
                "/api/decks/mein-deck/revisions", json={"cards": unknown}, headers=marker
            ).status_code
            == 422
        )
        mark = {"favorite": True, "excluded": False, "note": "gut"}
        assert (
            client.put("/api/cards/card:project:0007/mark", json=mark, headers=marker).status_code
            == 200
        )
        assert client.get("/api/cards/card:project:0007").json()["observations"] == []
        assert client.get("/api/cards/card:project:9999").status_code == 404
        assert client.get("/api/cohorts").json()[0]["cohort"] == "all"
        assert client.get("/img/card:project:0002", params={"face": "side"}).status_code == 422
        assert client.get("/api/revisions/nope").status_code == 404


def test_roles_are_read_from_a_role_file_and_counted(studio: StudioStore, tmp_path: Path) -> None:
    role_file = tmp_path / "roles.json"
    role_file.write_text(
        json.dumps(
            {
                "fetched_at": "2026-11-10T00:00:00Z",
                "roles": {
                    "ramp": ["oracle-forest", "oracle-filler-01"],
                    "removal": ["oracle-swarm-rat", "oracle-not-in-collection"],
                },
            }
        ),
        encoding="utf-8",
    )
    assert roles.import_roles(studio, role_file) == {
        "roles": 2,
        "role_rows": 4,
        "collection_cards_with_role": 3,
    }
    pool = builder.pool_cards(studio, ["Test Commander"])
    assert pool["roles"] == ["ramp", "removal"]
    cards = {card["name"]: card for card in pool["cards"]}  # type: ignore[union-attr]
    assert cards["Swarm Rat"]["roles"] == ["removal"]
    assert cards["Filler 02"]["roles"] == []
    assert builder.deck_roles(studio, _deck()) == {"ramp": 30}
    shapes = {shape["cohort"]: shape for shape in builder.cohort_shapes(studio)}
    assert shapes["community"]["roles"] == {
        "ramp": {"median": 33.0, "p25": 31.5, "p75": 34.5},
        "removal": {"median": 0.5, "p25": 0.25, "p75": 0.75},
    }
    role_file.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="no roles"):
        roles.import_roles(studio, role_file)


def test_role_fetch_asks_only_the_card_search(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []

    def page(address: str) -> dict[str, object]:
        asked.append(address)
        if "page=2" in address:
            return {"data": [{"oracle_id": "b"}], "has_more": False}
        return {
            "data": [{"oracle_id": "a"}, {"name": "no id"}],
            "has_more": True,
            "next_page": roles.SEARCH + "?page=2",
        }

    monkeypatch.setattr(roles, "_page", page)
    written = roles.fetch_role_file("WUG", tmp_path / "roles.json", pause=0)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["identity"] == "WUG"
    assert set(payload["roles"]) == set(roles.ROLES)
    assert payload["roles"]["ramp"] == ["a", "b"]
    assert len(asked) == 2 * len(roles.ROLES)
    assert all(address.startswith(roles.SEARCH) for address in asked)
    assert "id%3C%3Dwug" in asked[0]

    def elsewhere(address: str) -> dict[str, object]:
        return {"data": [], "has_more": True, "next_page": "https://example.invalid/next"}

    monkeypatch.setattr(roles, "_page", elsewhere)
    with pytest.raises(ValueError, match="unexpected address"):
        roles.fetch_role_file("WUG", tmp_path / "other.json", pause=0)


def test_cooccurrence_neutral_boards_diff_and_draw_probabilities(
    studio: StudioStore, tmp_path: Path
) -> None:
    co = builder.card_cooccurrence(studio, "card:project:0007")
    assert co["card_decks"] == 2
    assert co["data_class"] == "DERIVED_DESCRIPTIVE"
    assert co["cards"] == [
        {
            "card_id": "card:project:0002",
            "name": "Forest",
            "both_hits": 1,
            "card_decks": 2,
            "share": 0.5,
        }
    ]
    base_cards = _deck()
    target_cards = [
        *base_cards[:-1],
        RevisionCard("card:project:0002", 28),
        RevisionCard("card:project:0007", 1),
    ]
    diff = builder.diff_lists(studio, base_cards, target_cards)
    assert diff["data_class"] == "DERIVED_DESCRIPTIVE"
    assert diff["added"] == [
        {"card_id": "card:project:0007", "name": "Swarm Rat", "group": "Creature", "quantity": 1}
    ]
    assert diff["removed"] == []
    assert diff["changed"] == [
        {
            "card_id": "card:project:0002",
            "name": "Forest",
            "group": "Land",
            "base_quantity": 29,
            "target_quantity": 28,
            "delta": -1,
        }
    ]
    dp = builder.draw_probabilities(99, 29)
    assert dp is not None
    assert dp["data_class"] == "DERIVED_DESCRIPTIVE"
    assert dp["main_cards"] == 99
    assert dp["lands"] == 29
    opening = dp["opening_7"]
    assert isinstance(opening, dict)
    assert 0.0 < float(opening["at_least_3_lands"]) < 1.0


def test_multipart_scryfall_folder_and_disambiguation(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    importers.import_inventory_workbook(
        store, _workbook(tmp_path / "cards.xlsx", _synthetic_cards()[:2])
    )
    scry_dir = tmp_path / "scry"
    scry_dir.mkdir()
    part1 = scry_dir / "default-cards-20261109_part_001.jsonl"
    part2 = scry_dir / "default-cards-20261109_part_002.jsonl"
    part1.write_text(
        json.dumps(_public("Test Commander", ["G", "U", "W"], "Legendary Creature — Human Druid"))
        + "\n",
        encoding="utf-8",
    )
    part2.write_text(
        "\n".join(
            [
                json.dumps(
                    _public(
                        "Forest",
                        ["G"],
                        "Basic Land — Forest",
                        oracle_id="oracle-forest-paper",
                        games=["paper"],
                    )
                ),
                json.dumps(
                    _public(
                        "Forest // Forest",
                        ["G"],
                        "Basic Land — Forest",
                        oracle_id="oracle-forest-rev",
                        layout="reversible_card",
                    )
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    dis = _write_csv(
        tmp_path / "11_ORACLE_DISAMBIGUATION.csv",
        [
            {
                "name": "Forest",
                "num_possible_oracle_ids": "2",
                "selected_oracle_id": "oracle-forest-paper",
                "selection_rule": "PAPER_LEGAL",
                "candidate_ids": "oracle-forest-paper;oracle-forest-rev",
            }
        ],
    )
    res = catalog.import_scryfall_oracle(store, scry_dir, disambiguation_path=dis)
    assert res["files"] == 2
    assert res["linked"] == 2
    forest = store.connection.execute(
        "SELECT oracle_id FROM card WHERE oracle_name = 'Forest'"
    ).fetchone()
    assert forest["oracle_id"] == "oracle-forest-paper"
