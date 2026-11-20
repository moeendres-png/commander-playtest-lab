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
from commander_lab.studio.decks import (
    export_text,
    lab_snapshot,
    list_rows,
    parse_decklist_text,
    revision_rows,
    validate_rows,
)
from commander_lab.studio.gc_band import GC_BAND_0
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
    store.bind_unbound("Test Commander")
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
    shapes = {shape["cohort"]: shape for shape in builder.cohort_shapes(studio, ["Test Commander"])}
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
    assert not (studio.path.parent / "images").exists()
    studio.connection.execute(
        "UPDATE scryfall_card SET image_front = 'https://example.invalid/x.jpg' "
        "WHERE oracle_id = 'oracle-swarm-rat'"
    )
    assert image_address(studio, "card:project:0007") is None  # foreign host is rejected
    assert cached_image(studio, "card:project:0007") is None


def test_web_application_round_trip(studio: StudioStore) -> None:
    assert studio.path is not None
    folder = studio.path.parent
    studio.close()
    marker = {"X-Studio": "1"}
    with TestClient(create_app(folder)) as client:
        assert client.get("/").status_code == 200
        csp = client.get("/").headers["content-security-policy"]
        assert "script-src 'self'" in csp
        assert "img-src 'self' data: https://cards.scryfall.io" in csp
        status_json = client.get("/api/status").json()
        assert status_json["cards"] == 77
        assert status_json["image_cache"]["cache_enabled"] is False
        pool = client.get("/api/pool", params={"commander": "Test Commander"}).json()
        assert len(pool["commander_ids"]) == 1
        forest_card = next(c for c in pool["cards"] if c["card_id"] == "card:project:0002")
        assert forest_card["image_url_front"] == IMAGE.format("forest")
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
        export_url = f"/api/revisions/{saved['revision_id']}/export"
        block = client.get(export_url, params={"format": "moxfield"}).text
        assert block.startswith("Commander\n1 Test Commander\n\nDeck\n")
        assert "29 Forest\n" in block
        plain = client.get(export_url, params={"format": "plain"}).text
        assert plain.splitlines()[0] == "1 Test Commander"
        assert "Commander" not in plain.splitlines()  # no zone heading in the plain format
        assert client.get(export_url, params={"format": "pdf"}).status_code == 422
        assert (
            client.get("/api/revisions/nope/export", params={"format": "moxfield"}).status_code
            == 404
        )
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
        named = {"commander": "Test Commander"}
        card_url = "/api/cards/card:project:0007"
        assert client.get(card_url, params=named).json()["observations"] == []
        assert client.get("/api/cards/card:project:9999", params=named).status_code == 404
        assert client.get("/api/cohorts", params=named).json()[0]["cohort"] == "all"
        # deck figures are never served without a commander
        assert client.get(card_url).status_code == 422
        assert client.get("/api/cohorts").status_code == 422
        assert client.get("/api/simulations").status_code == 422
        known = {item["name"]: item for item in client.get("/api/commanders").json()}
        assert known["Test Commander"]["source_decks"] == 3
        assert known["Test Commander"]["in_collection"] is True
        diff_resp = client.post(
            "/api/diff",
            json={"base_revision_id": saved["revision_id"], "cards": cards},
            headers=marker,
        ).json()
        assert diff_resp["added_slots"] == 0
        # Q1-b1 (#1676): the heuristic prefilter route left the Studio
        pf_resp = client.post(
            "/api/prefilter",
            json={"base_revision_id": saved["revision_id"], "cards": cards, "trials": 100},
            headers=marker,
        )
        # no POST route there any more: the page fallback answers 405
        assert pf_resp.status_code == 405
        assert client.get("/img/card:project:0002", params={"face": "side"}).status_code == 422
        redir = client.get("/img/card:project:0002", follow_redirects=False)
        assert redir.status_code == 302
        assert redir.headers["location"] == IMAGE.format("forest")
        assert redir.headers["referrer-policy"] == "no-referrer"
        assert not (folder / "images").exists()
        assert client.get("/api/revisions/nope").status_code == 404


def _role_payload(role_ids: dict[str, list[str]]) -> dict[str, object]:
    """A complete role file in the current format (full snapshot of one color identity)."""
    return {
        "schema": roles.ROLES_SCHEMA,
        "role_origin": roles.ORIGIN_TAGGER,
        "fetched_at": "2026-11-10T00:00:00Z",
        "scope": {"mode": roles.FULL_SNAPSHOT, "key": "WUG", "completeness": "COMPLETE_FOR_SCOPE"},
        "tags": {role: roles.ROLES[role] for role in role_ids},
        "roles": role_ids,
    }


def test_export_text_formats_read_back_through_the_list_import(studio: StudioStore) -> None:
    db = studio.connection
    # a double-faced card is held under its full name, the engine under the front face
    db.execute(
        "UPDATE card SET oracle_name = 'Filler 00 // Hidden Back' WHERE oracle_name = 'Filler 00'"
    )
    ids = {str(r["oracle_name"]): str(r["card_id"]) for r in db.execute("SELECT * FROM card_fact")}
    two_face = ids["Filler 00 // Hidden Back"]
    cards = [
        RevisionCard(ids["Test Commander"], 1, "commander"),
        RevisionCard(two_face, 1),
        RevisionCard(ids["Forest"], 8),
        *[RevisionCard(ids[f"Filler {i:02d}"]) for i in range(1, 6)],
    ]
    revision = create_revision(studio, deck_id="d", name="D", cards=cards)
    rows = revision_rows(studio, revision)
    block = export_text(rows, "moxfield")
    lines = block.splitlines()
    assert lines[:4] == ["Commander", "1 Test Commander", "", "Deck"]
    assert "1 Filler 00 // Hidden Back" in lines  # the full name as the store holds it
    assert "8 Forest" in lines
    deck = lines[4:]
    assert len(deck) == 7
    assert deck == sorted(deck, key=lambda line: line.split(" ", 1)[1])  # name order
    assert export_text(rows, "plain").splitlines()[:2] == [
        "1 Test Commander",
        "1 Filler 00 // Hidden Back",
    ]
    wanted = {(c.card_id, c.quantity, c.zone) for c in cards}
    assert wanted
    for text_format in ("moxfield", "plain"):
        parsed = parse_decklist_text(studio, ["Test Commander"], export_text(rows, text_format))
        assert parsed["unrecognized_lines"] == []
        assert {(c["card_id"], c["quantity"], c["zone"]) for c in parsed["cards"]} == wanted
    with pytest.raises(ValueError):
        export_text(rows, "mtgo")
    # two commanders (partners): both stay in the commander zone through the round trip
    pair = [
        RevisionCard(ids["Test Commander"], 1, "commander"),
        RevisionCard(ids["Filler 01"], 1, "commander"),
        RevisionCard(ids["Forest"], 8),
    ]
    pair_rows = revision_rows(studio, create_revision(studio, deck_id="p", name="P", cards=pair))
    assert export_text(pair_rows, "moxfield").splitlines()[:5] == [
        "Commander",
        "1 Filler 01",
        "1 Test Commander",
        "",
        "Deck",
    ]
    names = ["Test Commander", "Filler 01"]
    wanted_pair = {(c.card_id, c.quantity, c.zone) for c in pair}
    for text_format in ("moxfield", "plain"):
        parsed = parse_decklist_text(studio, names, export_text(pair_rows, text_format))
        assert parsed["unrecognized_lines"] == []
        assert {(c["card_id"], c["quantity"], c["zone"]) for c in parsed["cards"]} == wanted_pair


def test_roles_are_read_from_a_role_file_and_counted(studio: StudioStore, tmp_path: Path) -> None:
    role_file = tmp_path / "roles.json"
    role_file.write_text(
        json.dumps(
            _role_payload(
                {
                    "ramp": ["oracle-forest", "oracle-filler-01"],
                    "removal": ["oracle-swarm-rat", "oracle-not-in-collection"],
                }
            )
        ),
        encoding="utf-8",
    )
    report = roles.import_roles(studio, role_file)
    assert {key: report[key] for key in ("roles", "role_rows", "collection_cards_with_role")} == {
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
    shapes = {shape["cohort"]: shape for shape in builder.cohort_shapes(studio, ["Test Commander"])}
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
    co = builder.card_cooccurrence(studio, "card:project:0007", ["Test Commander"])
    assert co["card_decks"] == 2
    assert co["data_class"] == "DERIVED_DESCRIPTIVE"
    assert co["cards"] == [
        {
            "card_id": "card:project:0002",
            "name": "Forest",
            "both_hits": 1,
            "card_decks": 2,
            "partner_decks": 2,
            "cohort_decks": 3,
            "share": 0.5,
            "lift": 0.75,
            "combo_partner": False,
        }
    ]
    role_file = tmp_path / "diff_roles.json"
    role_file.write_text(
        json.dumps(_role_payload({"ramp": ["oracle-forest"], "removal": ["oracle-swarm-rat"]})),
        encoding="utf-8",
    )
    roles.import_roles(studio, role_file)
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
    assert diff["role_deltas"] == {
        "ramp": {"base": 29, "target": 28, "delta": -1},
        "removal": {"base": 0, "target": 1, "delta": 1},
    }
    dp = builder.draw_probabilities(99, 29)
    assert dp is not None
    assert dp["data_class"] == "DERIVED_DESCRIPTIVE"
    assert dp["main_cards"] == 99
    assert dp["lands"] == 29
    opening = dp["opening_7"]
    assert isinstance(opening, dict)
    assert 0.0 < float(opening["at_least_3_lands"]) < 1.0
    # sim_status is populated on pool and card_detail
    pool = builder.pool_cards(studio, ["Test Commander"])
    cards_by_name = {card["name"]: card for card in pool["cards"]}  # type: ignore[union-attr]
    assert cards_by_name["Forest"]["sim_status"] == "OK"
    assert cards_by_name["Swarm Rat"]["sim_status"] == "NO_CARD_FACTS"
    detail = builder.card_detail(studio, "card:project:0002", ["Test Commander"])
    assert detail["sim_status"] == "OK"
    assert not hasattr(builder, "prefilter_lists")  # Q1-b1 (#1676)


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


def test_cooccurrence_runs_a_constant_number_of_statements_without_card_fact_join(
    studio: StudioStore,
) -> None:
    """Regression: the card window took minutes on the full store because every card fact was
    joined to every deck row on an OR condition (no index). The count is now one grouped pass;
    the test pins the shape of the work (statements, no card-fact join over deck rows)."""
    statements: list[str] = []
    studio.connection.set_trace_callback(statements.append)
    try:
        builder.card_cooccurrence(studio, "card:project:0007", ["Test Commander"])
    finally:
        studio.connection.set_trace_callback(None)
    deck_row_statements = [s for s in statements if "corpus_deck_card" in s]
    assert len(statements) <= 8
    assert not [s for s in deck_row_statements if "card_fact" in s]


def test_cooccurrence_counts_a_deck_once_when_lists_name_a_card_by_id_and_by_name(
    studio: StudioStore,
) -> None:
    """Some lists carry a card by oracle id, others by name only, and one deck can hold both
    spellings in two sections: the deck count is the union, never the sum."""
    with studio.connection:
        studio.connection.executemany(
            "INSERT INTO corpus_deck_card(deck_id, card_name, oracle_id, quantity, section, "
            "normalization_status) VALUES (?, 'Forest', NULL, 1, ?, 'exact')",
            [("d3", "mainboard"), ("d1", "commander")],
        )
    co = builder.card_cooccurrence(studio, "card:project:0007", ["Test Commander"])
    assert co["card_decks"] == 2
    forest = next(card for card in co["cards"] if card["name"] == "Forest")
    assert (forest["both_hits"], forest["share"]) == (2, 1.0)


def test_history_resolves_branch_from_heads_and_parent_chain(studio: StudioStore) -> None:
    cards1 = _deck()
    cards2 = [*cards1[:-1], RevisionCard("card:project:0002", 28)]
    cards3 = [*cards1[:-1], RevisionCard("card:project:0002", 27)]
    cards_orphan = [*cards1[:-1], RevisionCard("card:project:0002", 26)]
    rev1 = create_revision(
        studio, deck_id="hist-deck", branch="main", name="History Deck", cards=cards1, note="r1"
    )
    rev2 = create_revision(
        studio,
        deck_id="hist-deck",
        branch="main",
        name="History Deck",
        cards=cards2,
        parent_revision_id=rev1,
        note="r2",
    )
    rev3 = create_revision(
        studio,
        deck_id="hist-deck",
        branch="variant-a",
        name="History Deck",
        cards=cards3,
        parent_revision_id=rev1,
        note="r3",
    )
    rev_orphan = create_revision(
        studio,
        deck_id="hist-deck",
        branch="temp-branch",
        name="History Deck",
        cards=cards_orphan,
        note="orphan",
    )
    with studio.connection:
        studio.connection.execute(
            "DELETE FROM deck_branch WHERE deck_id = 'hist-deck' AND branch = 'temp-branch'"
        )
    rows = {str(r["revision_id"]): r for r in builder.history(studio, "hist-deck")}
    assert rows[rev2]["branch"] == "main"
    assert rows[rev1]["branch"] == "main"  # shared ancestor prefers main over variant-a
    assert rows[rev3]["branch"] == "variant-a"
    assert rows[rev_orphan]["branch"] is None


def test_favicon_returns_204_no_content(studio: StudioStore) -> None:
    client = TestClient(create_app(studio.path))
    res = client.get("/favicon.ico")
    assert res.status_code == 204


def test_ui_js_number_helpers_use_typographic_minus_and_no_negative_zero() -> None:
    import shutil
    import subprocess

    node = shutil.which("node") or "/usr/local/bin/node"
    ui_js = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "commander_lab"
        / "studio"
        / "static"
        / "ui.js"
    )
    script = f"""
const fs = require("fs");
global.window = {{ matchMedia: () => ({{ matches: false }}) }};
global.document = {{
  documentElement: {{ dataset: {{}} }},
  addEventListener: () => {{}},
  getElementById: () => null,
  querySelectorAll: () => [],
  createElement: () => ({{ setAttribute: () => {{}}, addEventListener: () => {{}}, append: () => {{}}, classList: {{ add: () => {{}}, remove: () => {{}} }} }}),
  createTextNode: (t) => t,
  body: {{ append: () => {{}} }},
}};
global.localStorage = {{ getItem: () => null, setItem: () => {{}} }};
global.location = {{ pathname: "/index.html" }};
eval(fs.readFileSync({json.dumps(str(ui_js))}, "utf8") + "\\nglobal.S = StudioUI;");
const out = {{
  negInt: global.S.num(-1, 0),
  negZero: global.S.num(-0.0001, 2),
  negFlex: global.S.numFlex(-1.5, 2),
  negSig: global.S.numSig(-0.045, 2),
  negPct: global.S.pct(-0.123, 1),
  thousands: global.S.num(10348, 0),
}};
console.log(JSON.stringify(out));
"""
    proc = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    data = json.loads(proc.stdout.strip())
    assert data["negInt"] == "\u22121"
    assert data["negZero"] == "0,00"
    assert data["negFlex"] == "\u22121,5"
    assert data["negSig"] == "\u22120,045"
    assert data["negPct"] == "\u221212,3 %"
    assert data["thousands"] == "10.348"


def _insert_scryfall(
    store: StudioStore,
    *,
    oracle_id: str,
    name: str,
    colors: str,
    type_line: str,
    oracle_text: str = "",
    legality: str = "legal",
) -> None:
    db = store.connection
    source_id = str(db.execute("SELECT source_id FROM scryfall_card LIMIT 1").fetchone()[0])
    db.execute(
        "INSERT OR REPLACE INTO scryfall_card("
        "oracle_id, scryfall_id, name, front_name, layout, mana_cost, mana_value, type_line, "
        "oracle_text, color_identity, commander_legality, edhrec_rank, keywords, produced_mana, "
        "power, toughness, game_changer, released_at, image_front, image_back, source_id) "
        "VALUES (?, ?, ?, ?, 'normal', '{3}', 3.0, ?, ?, ?, ?, NULL, '', '', NULL, NULL, 0, "
        "'2026-01-01', NULL, NULL, ?)",
        (
            oracle_id,
            f"scry-{oracle_id}",
            name,
            name,
            type_line,
            oracle_text,
            colors,
            legality,
            source_id,
        ),
    )


def test_pool_include_unowned_tam_superfriends_and_color_identity(studio: StudioStore) -> None:
    db = studio.connection
    source_id = str(db.execute("SELECT source_id FROM card LIMIT 1").fetchone()[0])
    # Add Tam, the Possibility (WUBRG) to collection
    _insert_scryfall(
        studio,
        oracle_id="oracle-tam",
        name="Tam, the Possibility",
        colors="WUBRG",
        type_line="Legendary Creature — Avatar",
    )
    db.execute(
        "INSERT INTO card(card_id, oracle_name, oracle_id, color_identity, mana_cost, mana_value, "
        "type_line, oracle_text, is_basic_land, commander_legal, source_id) "
        "VALUES ('card:project:tam', 'Tam, the Possibility', 'oracle-tam', 'WUBRG', "
        "'{W}{U}{B}{R}{G}', 5.0, 'Legendary Creature — Avatar', '', 0, 1, ?)",
        (source_id,),
    )
    db.execute(
        "INSERT INTO inventory(card_id, observed, owned_lower_bound, reserved, "
        "available_lower_bound, quantity_exact, source_id) "
        "VALUES ('card:project:tam', 1, 1, 0, 1, 1, ?)",
        (source_id,),
    )
    # Add unowned cards to scryfall_card only (NOT in inventory)
    _insert_scryfall(
        studio,
        oracle_id="oracle-bolas",
        name="Nicol Bolas, Dragon-God",
        colors="UBR",
        type_line="Legendary Planeswalker — Bolas",
    )
    _insert_scryfall(
        studio,
        oracle_id="oracle-teferi",
        name="Teferi, Hero of Dominaria",
        colors="WU",
        type_line="Legendary Planeswalker — Teferi",
    )
    _insert_scryfall(
        studio,
        oracle_id="oracle-flux",
        name="Flux Channeler",
        colors="U",
        type_line="Creature — Human Wizard",
        oracle_text="Whenever you cast a noncreature spell, proliferate.",
    )
    _insert_scryfall(
        studio,
        oracle_id="oracle-corpus-staple",
        name="Corpus Staple",
        colors="G",
        type_line="Instant",
        oracle_text="Draw a card.",
    )
    _insert_scryfall(
        studio,
        oracle_id="oracle-vanilla",
        name="Irrelevant Vanilla",
        colors="G",
        type_line="Creature — Elk",
    )
    _insert_scryfall(
        studio,
        oracle_id="oracle-banned-pw",
        name="Banned Walker",
        colors="W",
        type_line="Legendary Planeswalker — Test",
        legality="banned",
    )
    db.execute(
        "INSERT INTO corpus_deck_card(deck_id, card_name, oracle_id, quantity, section, "
        "normalization_status) VALUES ('d1', 'Corpus Staple', 'oracle-corpus-staple', 1, "
        "'mainboard', 'exact')"
    )
    db.commit()

    # Default include_unowned=False: strictly inventory cards only
    default_pool = builder.pool_cards(studio, ["Test Commander"])
    default_cards = {str(c["name"]): c for c in default_pool["cards"]}  # type: ignore[union-attr]
    # The Zukauf fields exist only on request (#1648): the default answer keeps its old form.
    for key in ("include_unowned", "unowned_selection", "sim_readiness_unowned"):
        assert key not in default_pool
    assert all(
        "in_collection" not in c and "wishlist_candidate" not in c and "selected_by" not in c
        for c in default_cards.values()
    )
    assert "Teferi, Hero of Dominaria" not in default_cards
    assert "Flux Channeler" not in default_cards
    assert "Corpus Staple" not in default_cards

    # include_unowned=True for Tam, the Possibility (WUBRG)
    tam_pool = builder.pool_cards(studio, ["Tam, the Possibility"], include_unowned=True)
    tam_cards = {str(c["name"]): c for c in tam_pool["cards"]}  # type: ignore[union-attr]
    assert tam_pool["include_unowned"] is True
    for expected_name in ("Nicol Bolas, Dragon-God", "Teferi, Hero of Dominaria", "Flux Channeler"):
        card = tam_cards[expected_name]
        assert card["in_collection"] is False
        assert card["wishlist_candidate"] is True
        assert card["owned"] == 0
        assert card["available"] == 0
        assert card["reserved"] == 0
    assert "Irrelevant Vanilla" not in tam_cards
    assert "Banned Walker" not in tam_cards
    assert "Corpus Staple" not in tam_cards  # corpus deck belongs to Test Commander, not Tam

    # include_unowned=True for Test Commander (WUG) enforces color_identity
    wug_pool = builder.pool_cards(studio, ["Test Commander"], include_unowned=True)
    wug_cards = {str(c["name"]): c for c in wug_pool["cards"]}  # type: ignore[union-attr]
    assert "Teferi, Hero of Dominaria" in wug_cards
    assert "Flux Channeler" in wug_cards
    assert "Corpus Staple" in wug_cards
    assert "Nicol Bolas, Dragon-God" not in wug_cards  # UBR violates WUG identity
    assert "Irrelevant Vanilla" not in wug_cards
    assert "Banned Walker" not in wug_cards


def test_build_wishlist_counts_owned_and_missing_without_prices() -> None:
    pool_by_id: dict[str, dict[str, object]] = {
        "c1": {"card_id": "c1", "name": "Sol Ring", "owned": 2, "in_collection": True},
        "c2": {"card_id": "c2", "name": "Forest", "owned": 2, "in_collection": True},
        "s1": {
            "card_id": "s1",
            "name": "Teferi, Hero of Dominaria",
            "owned": 0,
            "in_collection": False,
        },
        "s2": {"card_id": "s2", "name": "Doubling Season", "owned": 0, "in_collection": False},
    }
    deck = [
        RevisionCard("c1", 1, "main"),
        RevisionCard("c2", 5, "main"),
        RevisionCard("s1", 1, "main"),
        RevisionCard("s2", 1, "main"),
    ]
    res = builder.build_wishlist(deck, pool_by_id)
    assert res["total_count"] == 8
    assert res["owned_count"] == 3
    assert res["missing_count"] == 5
    missing = res["missing_cards"]
    assert isinstance(missing, list)
    assert [m["name"] for m in missing] == [
        "Doubling Season",
        "Forest",
        "Teferi, Hero of Dominaria",
    ]
    assert [m["missing"] for m in missing] == [1, 3, 1]
    text = str(res["text"])
    assert text == "1 Doubling Season\n3 Forest\n1 Teferi, Hero of Dominaria"
    for forbidden in ("€", "$", "eur", "usd", "price", "preis"):
        assert forbidden not in text.casefold()


def test_api_pool_caches_include_unowned_separately(studio: StudioStore) -> None:
    _insert_scryfall(
        studio,
        oracle_id="oracle-teferi-cache",
        name="Teferi, Time Raveler",
        colors="WU",
        type_line="Legendary Planeswalker — Teferi",
    )
    studio.connection.commit()
    assert studio.path is not None
    folder = studio.path.parent
    studio.close()

    with TestClient(create_app(folder)) as client:
        r_false_1 = client.get("/api/pool", params={"commander": "Test Commander"})
        assert r_false_1.status_code == 200
        names_false_1 = {c["name"] for c in r_false_1.json()["cards"]}
        assert "Teferi, Time Raveler" not in names_false_1

        r_true = client.get(
            "/api/pool", params={"commander": "Test Commander", "include_unowned": "true"}
        )
        assert r_true.status_code == 200
        cards_true = {c["name"]: c for c in r_true.json()["cards"]}
        assert "Teferi, Time Raveler" in cards_true
        assert cards_true["Teferi, Time Raveler"]["in_collection"] is False
        assert cards_true["Teferi, Time Raveler"]["wishlist_candidate"] is True

        # Re-requesting include_unowned=false must still return the unowned-free cached answer
        r_false_2 = client.get(
            "/api/pool", params={"commander": "Test Commander", "include_unowned": "false"}
        )
        assert r_false_2.status_code == 200
        names_false_2 = {c["name"] for c in r_false_2.json()["cards"]}
        assert "Teferi, Time Raveler" not in names_false_2


def test_unowned_scryfall_card_check_revision_and_marks(studio: StudioStore) -> None:
    """Unowned scryfall:<oracle_id> cards must work in /api/check, revision saves, marks and labels
    without leaking into the owned-only pool, while bogus scryfall IDs still fail closed (422)."""
    _insert_scryfall(
        studio,
        oracle_id="oracle-teferi-save",
        name="Teferi, Hero of Dominaria",
        colors="WU",
        type_line="Legendary Planeswalker — Teferi",
        oracle_text="+1: Draw a card.",
    )
    source_id = str(
        studio.connection.execute("SELECT source_id FROM scryfall_card LIMIT 1").fetchone()[0]
    )
    studio.connection.execute(
        "INSERT OR IGNORE INTO card_role(oracle_id, role, source_id) VALUES (?, ?, ?)",
        ("oracle-teferi-save", "card-draw", source_id),
    )
    studio.connection.commit()
    cmd_row = studio.connection.execute(
        "SELECT card_id FROM card WHERE oracle_name = 'Test Commander'"
    ).fetchone()
    assert cmd_row is not None
    cmd_id = str(cmd_row["card_id"])
    unowned_id = "scryfall:oracle-teferi-save"
    assert studio.path is not None
    folder = studio.path.parent
    studio.close()

    marker = {"X-Studio": "1"}
    with TestClient(create_app(folder)) as client:
        # 1. /api/check resolves scryfall:<oracle_id> read-only (shape, roles, owned_only toggle)
        check_cards = [
            {"card_id": cmd_id, "zone": "commander", "quantity": 1},
            {"card_id": unowned_id, "zone": "main", "quantity": 1},
        ]
        r_check_owned = client.post(
            "/api/check", json={"cards": check_cards, "owned_only": True}, headers=marker
        )
        assert r_check_owned.status_code == 200
        body_owned = r_check_owned.json()
        assert body_owned["shape"]["cards"] == 2
        assert body_owned["shape"]["types"].get("Planeswalker") == 1
        assert body_owned["roles"].get("card-draw") == 1
        assert any(
            i["code"] == "not_owned" and i["card_id"] == unowned_id for i in body_owned["issues"]
        )

        r_check_wishlist = client.post(
            "/api/check", json={"cards": check_cards, "owned_only": False}, headers=marker
        )
        assert r_check_wishlist.status_code == 200
        assert not any(i["code"] == "not_owned" for i in r_check_wishlist.json()["issues"])

        # 2. Saving a revision with a known scryfall:<oracle_id> succeeds and preserves card
        r_deck = client.post(
            "/api/decks",
            json={"name": "Wishlist Test Deck", "commander_card_ids": [cmd_id]},
            headers=marker,
        )
        assert r_deck.status_code == 200
        deck_id = r_deck.json()["deck_id"]

        r_rev = client.post(
            f"/api/decks/{deck_id}/revisions",
            json={"cards": check_cards, "branch": "main", "note": "with wishlist card"},
            headers=marker,
        )
        assert r_rev.status_code == 200
        rev_id = r_rev.json()["revision_id"]

        r_get_rev = client.get(f"/api/revisions/{rev_id}")
        assert r_get_rev.status_code == 200
        rev_card_ids = {c["card_id"] for c in r_get_rev.json()["cards"]}
        assert unowned_id in rev_card_ids

        # 3. Bogus scryfall:<unknown> still fails closed with HTTP 422
        r_bad = client.post(
            f"/api/decks/{deck_id}/revisions",
            json={
                "cards": [
                    {"card_id": cmd_id, "zone": "commander", "quantity": 1},
                    {"card_id": "scryfall:does-not-exist", "zone": "main", "quantity": 1},
                ],
                "branch": "main",
            },
            headers=marker,
        )
        assert r_bad.status_code == 422

        # 4. Marks and labels work for scryfall:<oracle_id> and show up in include_unowned=true
        r_mark = client.put(
            f"/api/cards/{unowned_id}/mark",
            json={"favorite": True, "excluded": False, "note": "Zukauf Prio 1"},
            headers=marker,
        )
        assert r_mark.status_code == 200
        r_lbl = client.put(
            f"/api/cards/{unowned_id}/labels",
            json={"labels": ["Superfriends"]},
            headers=marker,
        )
        assert r_lbl.status_code == 200

        # 5. Materialized unowned card must NOT leak into default include_unowned=false pool
        r_pool_owned = client.get("/api/pool", params={"commander": "Test Commander"})
        assert r_pool_owned.status_code == 200
        assert all(c["card_id"] != unowned_id for c in r_pool_owned.json()["cards"])

        r_pool_unowned = client.get(
            "/api/pool", params={"commander": "Test Commander", "include_unowned": "true"}
        )
        assert r_pool_unowned.status_code == 200
        teferi = next(c for c in r_pool_unowned.json()["cards"] if c["card_id"] == unowned_id)
        assert teferi["in_collection"] is False
        assert teferi["favorite"] is True
        assert teferi["note"] == "Zukauf Prio 1"
        assert teferi["labels"] == ["Superfriends"]


def test_unowned_commander_resolution_and_scryfall_card_detail(studio: StudioStore) -> None:
    """A commander present in scryfall_card (e.g. Tam, the Possibility) but absent from
    card/inventory resolves cleanly in list_commanders, commander_identity, /api/pool, and
    /api/cards/scryfall:<oid>, while truly unknown commanders still fail closed."""
    _insert_scryfall(
        studio,
        oracle_id="oracle-tam-unowned",
        name="Tam, the Possibility",
        colors="WUBRG",
        type_line="Legendary Planeswalker — Tam",
        oracle_text="Tam, the Possibility can be your commander.",
    )
    studio.connection.execute(
        "INSERT OR IGNORE INTO commander_binding(kind, key, commander_name, basis) "
        "VALUES ('observation_cohort', 'tam:edhrec_view:planeswalkers', 'Tam, the Possibility', 'IMPORT_DECLARED')"
    )
    studio.connection.commit()

    commanders = {c["name"]: c for c in builder.list_commanders(studio)}
    assert "Tam, the Possibility" in commanders
    tam = commanders["Tam, the Possibility"]
    assert tam["in_collection"] is False
    assert tam["card_id"] == "scryfall:oracle-tam-unowned"
    assert tam["identity"] == "WUBRG"

    ident, ids = builder.commander_identity(studio, ["Tam, the Possibility"])
    assert ident == frozenset("WUBRG")
    assert ids == ["scryfall:oracle-tam-unowned"]
    with pytest.raises(KeyError):
        builder.commander_identity(studio, ["Nonexistent Commander"])

    assert studio.path is not None
    folder = studio.path.parent
    studio.close()

    with TestClient(create_app(folder)) as client:
        r_pool = client.get(
            "/api/pool",
            params={"commander": "Tam, the Possibility", "include_unowned": "true"},
        )
        assert r_pool.status_code == 200
        assert r_pool.json()["commander_ids"] == ["scryfall:oracle-tam-unowned"]

        r_detail = client.get(
            "/api/cards/scryfall:oracle-tam-unowned",
            params={"commander": "Tam, the Possibility"},
        )
        assert r_detail.status_code == 200
        assert r_detail.json()["card_id"] == "scryfall:oracle-tam-unowned"

        r_unknown = client.get("/api/pool", params={"commander": "Nonexistent Commander"})
        assert r_unknown.status_code == 404


# ---------- Zukauf pool selection (#1648, Co-Lead decision 2026-11-20) ----------

COMMANDER = "Test Commander"


def _corpus_card(store: StudioStore, deck_id: str, name: str, oracle_id: str) -> None:
    store.connection.execute(
        "INSERT INTO corpus_deck_card(deck_id, card_name, oracle_id, quantity, section, "
        "normalization_status) VALUES (?, ?, ?, 1, 'mainboard', 'exact')",
        (deck_id, name, oracle_id),
    )


def _source_id(store: StudioStore) -> str:
    return str(store.connection.execute("SELECT source_id FROM card LIMIT 1").fetchone()[0])


def _bind_observation(store: StudioStore, cohort: str) -> None:
    store.connection.execute(
        "INSERT OR IGNORE INTO commander_binding(kind, key, commander_name, basis) "
        "VALUES ('observation_cohort', ?, ?, 'IMPORT_DECLARED')",
        (cohort, COMMANDER),
    )


def _observation(store: StudioStore, name: str, cohort: str, numerator: int, denominator: int):
    store.connection.execute(
        "INSERT INTO observation(card_id, card_name, metric, cohort, value, numerator, "
        "denominator, data_class, source_id) VALUES (NULL, ?, 'inclusion_pct', ?, ?, ?, ?, "
        "'OBSERVED_EXTERNAL', ?)",
        (name, cohort, 100 * numerator / denominator, numerator, denominator, _source_id(store)),
    )


def _signal(
    store: StudioStore, name: str, signal: str, value: float, num: int | None, den: int | None
):
    store.connection.execute(
        "INSERT INTO card_signal(commander_name, signal, card_name, value, numerator, "
        "denominator, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (COMMANDER, signal, name, value, num, den, _source_id(store)),
    )


def _unowned(pool: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(c["name"]): c
        for c in pool["cards"]  # type: ignore[union-attr]
        if c.get("in_collection") is False
    }


def test_unowned_corpus_threshold_counts_decks_over_the_bound_corpus(
    studio: StudioStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert builder.UNOWNED_MIN_CORPUS_PCT == 2  # Co-Lead decision 2026-11-20
    assert builder.UNOWNED_MIN_EDHREC_DENOMINATOR == 30
    _insert_scryfall(
        studio, oracle_id="o-one", name="One Deck Card", colors="G", type_line="Instant"
    )
    _corpus_card(studio, "d1", "One Deck Card", "o-one")
    # A deck bound to no commander counts neither in n nor in N (N is the bound corpus).
    studio.connection.execute(
        "INSERT INTO corpus_deck(deck_id, cohort, url, platform, play_group, deck_date, tags, "
        "fingerprint, duplicate_of, legality_audit, source_id) VALUES ('loose', 'all', "
        "'https://example.invalid/loose', 'test', 'community', NULL, '', 'fp-loose', NULL, "
        "'{}', ?)",
        (_source_id(studio),),
    )
    _corpus_card(studio, "loose", "One Deck Card", "o-one")
    studio.connection.commit()
    total = builder.cohort_sizes(studio, [COMMANDER])[builder.ALL_DECKS]
    assert builder.corpus_binding(studio, [COMMANDER])["unbound_decks"] >= 1
    assert total >= 2
    # One deck of N: in exactly when 1 * 100 >= pct * N (integers, no rounding).
    monkeypatch.setattr(builder, "UNOWNED_MIN_CORPUS_PCT", 100 // total)
    pool = builder.pool_cards(studio, [COMMANDER], include_unowned=True)
    card = _unowned(pool)["One Deck Card"]
    assert card["selected_by"] == ["corpus"]
    assert card["decks"][builder.ALL_DECKS] == 1  # type: ignore[index]
    selection = pool["unowned_selection"]
    assert selection["corpus_denominator"] == total  # type: ignore[index]
    assert selection["min_corpus_pct"] == 100 // total  # type: ignore[index]
    assert selection["counts"]["corpus"] >= 1  # type: ignore[index]
    monkeypatch.setattr(builder, "UNOWNED_MIN_CORPUS_PCT", 100 // total + 1)
    assert "One Deck Card" not in _unowned(
        builder.pool_cards(studio, [COMMANDER], include_unowned=True)
    )
    # Exactly at the limit counts: a card in every bound deck meets 100 %.
    _insert_scryfall(
        studio, oracle_id="o-all", name="Every Deck Card", colors="U", type_line="Instant"
    )
    for deck_id in builder._corpus_deck_ids(studio, [COMMANDER]):
        _corpus_card(studio, deck_id, "Every Deck Card", "o-all")
    studio.connection.commit()
    monkeypatch.setattr(builder, "UNOWNED_MIN_CORPUS_PCT", 100)
    every = _unowned(builder.pool_cards(studio, [COMMANDER], include_unowned=True))
    assert every["Every Deck Card"]["decks"][builder.ALL_DECKS] == total  # type: ignore[index]
    assert "One Deck Card" not in every


def test_unowned_edhrec_needs_a_denominator_of_thirty(studio: StudioStore) -> None:
    cohort = "edhrec:test-commander"
    _bind_observation(studio, cohort)
    for oracle_id, name in (
        ("o-obs29", "Obs Twentynine"),
        ("o-obs30", "Obs Thirty"),
        ("o-sig29", "Sig Twentynine"),
        ("o-sig30", "Sig Thirty"),
        ("o-syn", "Synergy Only"),
    ):
        _insert_scryfall(studio, oracle_id=oracle_id, name=name, colors="U", type_line="Sorcery")
    _observation(studio, "Obs Twentynine", cohort, 10, 29)
    _observation(studio, "Obs Thirty", cohort, 10, 30)
    # an observation of another commander's cohort selects nothing here
    _insert_scryfall(
        studio, oracle_id="o-foreign", name="Foreign Obs", colors="U", type_line="Sorcery"
    )
    studio.connection.execute(
        "INSERT INTO commander_binding(kind, key, commander_name, basis) "
        "VALUES ('observation_cohort', 'edhrec:other', 'Other Commander', 'IMPORT_DECLARED')"
    )
    _observation(studio, "Foreign Obs", "edhrec:other", 20, 400)
    _signal(studio, "Sig Twentynine", "edhrec_commander_inclusion", 0.5, 14, 29)
    _signal(studio, "Sig Thirty", "edhrec_commander_inclusion", 0.5, 15, 30)
    _signal(studio, "Sig Thirty", "edhrec_commander_synergy", 0.25, None, None)
    _signal(studio, "Synergy Only", "edhrec_commander_synergy", 0.9, None, None)
    studio.connection.commit()
    unowned = _unowned(builder.pool_cards(studio, [COMMANDER], include_unowned=True))
    assert "Obs Twentynine" not in unowned
    assert "Sig Twentynine" not in unowned
    assert "Synergy Only" not in unowned  # only an inclusion figure selects a card
    assert "Foreign Obs" not in unowned  # bound to another commander
    assert unowned["Obs Thirty"]["selected_by"] == ["edhrec"]
    assert unowned["Obs Thirty"]["edhrec"]["denominator"] == 30  # type: ignore[index]
    sig = unowned["Sig Thirty"]
    assert sig["selected_by"] == ["edhrec"]
    # Chosen through card_signal: the card carries the signal figures, with n/N.
    assert sig["signals"]["inclusion"] == {"value": 0.5, "numerator": 15, "denominator": 30}  # type: ignore[index]
    assert sig["signals"]["synergy"]["value"] == 0.25  # type: ignore[index]
    assert sig["edhrec"]["origin"] == "signal"  # type: ignore[index]
    assert sig["edhrec"]["denominator"] == 30  # type: ignore[index]


def test_unowned_pool_splits_sim_readiness_and_keeps_saved_deck_cards(studio: StudioStore) -> None:
    _insert_scryfall(
        studio, oracle_id="o-kept", name="Kept Choice", colors="W", type_line="Instant"
    )
    _insert_scryfall(
        studio, oracle_id="o-walker", name="Test Walker", colors="W",
        type_line="Legendary Planeswalker — Test",
    )  # fmt: skip
    studio.connection.commit()
    default = builder.pool_cards(studio, [COMMANDER])
    assert "Kept Choice" not in _unowned(
        builder.pool_cards(studio, [COMMANDER], include_unowned=True)
    )
    revision = create_revision(studio, deck_id="keep", name="Keep", cards=_deck())
    builder.write_draft(
        studio, "keep", "main", [*_deck(), RevisionCard("scryfall:o-kept", 1, "main")], revision
    )
    pool = builder.pool_cards(studio, [COMMANDER], include_unowned=True)
    unowned = _unowned(pool)
    assert unowned["Kept Choice"]["selected_by"] == ["in_saved_deck"]
    assert unowned["Test Walker"]["selected_by"] == ["planeswalker"]
    # the collection figure is the same as without the Zukauf cards; those are counted apart
    assert pool["sim_readiness"] == default["sim_readiness"]
    extra = pool["sim_readiness_unowned"]
    assert extra["total"] == len(unowned)  # type: ignore[index]
    assert pool["unowned_selection"]["total"] == len(unowned)  # type: ignore[index]
    assert pool["unowned_selection"]["counts"]["in_saved_deck"] == 1  # type: ignore[index]


def test_unowned_card_is_listed_once_when_catalog_cards_share_an_oracle_id(
    studio: StudioStore,
) -> None:
    db = studio.connection
    _insert_scryfall(
        studio, oracle_id="o-twice", name="Twice Walker", colors="U",
        type_line="Legendary Planeswalker — Twice",
    )  # fmt: skip
    for card_id in ("card:catalog:b", "card:catalog:a"):
        db.execute(
            "INSERT INTO card(card_id, oracle_name, oracle_id, color_identity, type_line, "
            "is_basic_land, commander_legal, source_id) VALUES (?, 'Twice Walker', 'o-twice', "
            "'U', 'Legendary Planeswalker — Twice', 0, 1, ?)",
            (card_id, _source_id(studio)),
        )
    db.commit()
    pool = builder.pool_cards(studio, [COMMANDER], include_unowned=True)
    rows = [c for c in pool["cards"] if c["name"] == "Twice Walker"]  # type: ignore[union-attr]
    assert len(rows) == 1
    assert rows[0]["card_id"] == "card:catalog:a"


def test_unowned_card_in_a_counted_scope_is_unknown_over_the_scope_denominator(
    studio: StudioStore,
) -> None:
    _insert_scryfall(
        studio, oracle_id="o-scope", name="Scope Walker", colors="G",
        type_line="Legendary Planeswalker — Scope",
    )  # fmt: skip
    studio.connection.commit()
    band = builder.pool_cards(studio, [COMMANDER], gc_band=GC_BAND_0, include_unowned=True)
    card = _unowned(band)["Scope Walker"]
    universe = card["universe"]
    assert universe["matched"] is False  # type: ignore[index]
    assert universe["hits"] is None  # type: ignore[index]
    assert universe["share"] is None  # type: ignore[index]
    assert "level" not in universe  # type: ignore[operator]  # no level letter since Q1-b5 (#1680)
    assert universe["denominator"] == band["universe"]["denominator"]  # type: ignore[index]
    assert universe["reason"] == builder.UNOWNED_NOT_COUNTED  # type: ignore[index]
    # collection cards keep their counted rows; the default pool never carries this entry
    plain = builder.pool_cards(studio, [COMMANDER], gc_band=GC_BAND_0)
    assert all(
        c.get("universe", {}).get("reason") != builder.UNOWNED_NOT_COUNTED  # type: ignore[union-attr]
        for c in plain["cards"]  # type: ignore[union-attr]
    )


def test_saved_deck_criterion_is_bound_to_the_commander_and_ignores_history(
    studio: StudioStore,
) -> None:
    for oracle_id, name in (("o-foreign-pick", "Foreign Pick"), ("o-old-pick", "Old Pick")):
        _insert_scryfall(studio, oracle_id=oracle_id, name=name, colors="G", type_line="Instant")
    studio.connection.commit()
    before = builder.pool_cards(studio, [COMMANDER], include_unowned=True)
    # A deck under another commander (another commander-zone card) with a green pick.
    other = [RevisionCard("card:project:0101", 1, "commander")]
    other += [RevisionCard(f"card:project:{110 + i:04d}") for i in range(10)]
    revision = create_revision(studio, deck_id="other", name="Other", cards=other)
    builder.write_draft(
        studio, "other", "main", [*other, RevisionCard("scryfall:o-foreign-pick", 1)], revision
    )
    # A deck of this commander whose OLD revision held a pick that the head dropped.
    first = create_revision(
        studio,
        deck_id="mine",
        name="Mine",
        cards=[*_deck(), RevisionCard("scryfall:o-old-pick", 1)],
    )
    create_revision(studio, deck_id="mine", name="Mine", cards=_deck(), parent_revision_id=first)
    after = builder.pool_cards(studio, [COMMANDER], include_unowned=True)
    assert "Foreign Pick" not in _unowned(after)
    assert "Old Pick" not in _unowned(after)
    assert after["unowned_selection"] == before["unowned_selection"]
    assert len(_unowned(after)) == len(_unowned(before))
