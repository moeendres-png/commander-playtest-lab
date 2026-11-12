"""Deck universe in the browser: profiles, counted spread per card, co-occurrence.

All decks and cards here are synthetic. Marks (favourite, exclude, note) are filters only
and must never change a count or a level.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, decklist_import, tiers, universe
from commander_lab.studio.web import STATIC, create_app
from tests.unit.test_studio_builder import _fill

MARK = {"X-Studio": "1"}
COMMANDER = {"view": "commander", "commander": "Test Commander"}
NAMES = [COMMANDER["commander"]]


def _deck(
    store: StudioStore,
    deck_id: str,
    platform: str,
    bracket: int,
    cards: list[str],
    section: str = "main",
) -> None:
    db = store.connection
    db.execute(
        "INSERT OR IGNORE INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES ('raw', 'DERIVED_DESCRIPTIVE', 'raw', 'x', '2026-01-01')"
    )
    db.execute(
        "INSERT INTO corpus_deck(deck_id, cohort, url, platform, play_group, deck_date, tags, "
        "fingerprint, duplicate_of, legality_audit, source_id) "
        "VALUES (?, 'c', '', ?, 'g', '2026-10-01', '[]', ?, NULL, 'not_audited', 'raw')",
        (deck_id, platform, f"fp-{deck_id}"),
    )
    db.executemany(
        "INSERT INTO corpus_deck_card(deck_id, card_name, section, oracle_id, quantity, "
        "normalization_status) VALUES (?, ?, ?, NULL, 1, 'source_name')",
        [(deck_id, name, section) for name in cards],
    )
    db.execute(
        "INSERT INTO corpus_cohort(cohort, deck_id) VALUES (?, ?)", (f"bracket:{bracket}", deck_id)
    )
    # Deck figures are only counted for a named commander: bind every test deck to one.
    db.execute(
        "INSERT OR IGNORE INTO commander_binding(kind, key, commander_name, basis) "
        "VALUES ('corpus_deck', ?, ?, 'TEST')",
        (deck_id, COMMANDER["commander"]),
    )


@pytest.fixture
def folder(tmp_path: Path) -> Iterator[Path]:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    db = store.connection
    db.execute(
        "UPDATE card SET oracle_name = 'Filler 01 // Back Side' WHERE card_id = 'card:project:0101'"
    )
    db.execute(
        "UPDATE card SET oracle_name = 'Filler 02 // Back Side' WHERE card_id = 'card:project:0102'"
    )
    # _fill already wrote three corpus-importer decks ("mainboard" section); with the
    # forty below the universe holds 43 decks.
    for index in range(40):
        cards = ["Forest", "Filler 03"]
        if index < 25:
            cards.append("swarm rat")  # differs from the oracle name by case only
        if index < 20:
            cards.append("Filler 01")  # front face of a double-faced name
        cards.append("Filler 02" if index < 10 else "Filler 02 // Back Side" if index < 25 else "X")
        _deck(store, f"u{index:02d}", "archidekt" if index % 2 else "edhrec", 3 + index % 2, cards)
    db.commit()
    store.close()
    yield tmp_path / "studio"


def _add_card(folder: Path, card_id: str, name: str, decks: list[list[str]]) -> None:
    """A Studio card without scryfall facts (engine name = oracle name) and its decks."""
    store = StudioStore.open(folder)
    try:
        store.connection.execute(
            "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, source_id) "
            "VALUES (?, NULL, ?, 'C', 'raw')",
            (card_id, name),
        )
        known = store.connection.execute("SELECT COUNT(*) FROM corpus_deck").fetchone()[0]
        for index, listed in enumerate(decks):
            _deck(store, f"x{card_id[-3:]}{known + index:03d}", "edhrec", 3, listed)
        store.connection.commit()
    finally:
        store.close()


class _CommanderClient(TestClient):
    """Sends the commander with every universe request, as the page does."""

    def request(self, method: str, url: Any, **kwargs: Any) -> Any:
        if "/universe" in str(url) or "/cooccurrence" in str(url):
            params = dict(kwargs.get("params") or {})
            params.setdefault("commander", COMMANDER["commander"])
            kwargs["params"] = params
        return super().request(method, url, **kwargs)


@pytest.fixture
def client(folder: Path) -> Iterator[TestClient]:
    with _CommanderClient(create_app(folder)) as test_client:
        yield test_client


def _put(client: TestClient, name: str, spec: dict[str, object]) -> dict[str, object]:
    answer = client.put(f"/api/universe/profiles/{name}", json=spec, headers=MARK)
    assert answer.status_code == 200, answer.text
    return answer.json()  # type: ignore[no-any-return]


def _spread(client: TestClient, name: str) -> dict[str, dict[str, object]]:
    answer = client.get("/api/universe/spread", params={"profile": name})
    assert answer.status_code == 200
    return {card["name"]: card for card in answer.json()["cards"]}


def test_profiles_are_saved_listed_and_read_back(client: TestClient) -> None:
    assert client.get("/api/universe/profiles").json() == []
    saved = _put(client, "alle", {"platforms": ["edhrec"], "min_main_cards": 3})
    assert saved["spec"] == {"platforms": ["edhrec"], "min_main_cards": 3}
    listed = client.get("/api/universe/profiles").json()
    assert [item["name"] for item in listed] == ["alle"]
    assert listed[0]["spec"] == {"platforms": ["edhrec"], "min_main_cards": 3}
    summary = client.get("/api/universe/profiles/alle/summary").json()
    assert summary["spec"] == listed[0]["spec"]
    assert summary["snapshot_id"].startswith("universe:")


def test_put_rejects_bad_input_and_a_missing_marker(client: TestClient) -> None:
    url = "/api/universe/profiles/x"
    assert client.put(url, json={"colour": "G"}, headers=MARK).status_code == 422
    assert client.put(url, json={"date_from": "gestern"}, headers=MARK).status_code == 422
    assert client.put(url, json={"min_main_cards": -1}, headers=MARK).status_code == 422
    assert client.put(url, json={}).status_code == 403
    assert client.get("/api/universe/profiles").json() == []


def test_summary_equals_the_inclusion_denominators(client: TestClient, folder: Path) -> None:
    _put(client, "alle", {})
    summary = client.get("/api/universe/profiles/alle/summary").json()
    store = StudioStore.open(folder)
    try:
        counted = universe.inclusion(store, profile="alle", card_names=[], commander_names=NAMES)
        assert summary["denominator"] == counted["denominator"] == 43
        assert summary["denominator_by_platform"] == counted["denominator_by_platform"]
        assert summary["denominator_by_bracket"] == counted["denominator_by_bracket"]
        assert summary["denominator_by_platform"] == {"archidekt": 20, "edhrec": 20, "example": 3}
        assert summary["denominator_by_bracket"] == {"bracket:3": 20, "bracket:4": 20, "unknown": 3}
        assert summary["snapshot_id"] == universe.snapshot_id(
            store, profile="alle", commander_names=NAMES
        )
    finally:
        store.close()


def test_card_spread_carries_hits_denominator_share_and_snapshot(client: TestClient) -> None:
    summary = _put(client, "alle", {})
    forest = client.get("/api/universe/spread", params={"profile": "alle"}).json()
    card = next(item for item in forest["cards"] if item["name"] == "Forest")
    assert (card["hits"], card["denominator"]) == (42, 43)
    assert card["share"] == pytest.approx(42 / 43)
    assert card["matched"] is True and card["level"] == "S" and card["reason"] == "SHARE_CUT"
    assert forest["universe"]["snapshot_id"] == summary["snapshot_id"]
    assert forest["universe"]["data_class"] == "DERIVED_DESCRIPTIVE"
    assert forest["params"]["min_universe"] == 30
    one = client.get("/api/cards/card:project:0002/universe", params={"profile": "alle"}).json()
    assert one["cards"] == [card]


def test_a_universe_below_the_minimum_is_level_u(client: TestClient) -> None:
    _put(client, "klein", {"platforms": ["archidekt"]})
    card = _spread(client, "klein")["Forest"]
    assert (card["hits"], card["denominator"]) == (20, 20)
    assert card["level"] == "U" and card["reason"] == "UNIVERSE_TOO_SMALL"


def test_an_unmatched_card_is_unknown_not_weak_and_not_zero(client: TestClient) -> None:
    _put(client, "alle", {})
    card = _spread(client, "alle")["Reserved Bear"]
    assert card["matched"] is False and card["share"] is None and card["hits"] is None
    assert card["level"] == "U" and card["reason"] == "NAME_NOT_FOUND_IN_UNIVERSE"


def test_front_face_and_case_variants_map_to_the_card(client: TestClient) -> None:
    _put(client, "alle", {})
    cards = _spread(client, "alle")
    front = cards["Filler 01 // Back Side"]
    assert front["matched"] and front["hits"] == 20 and front["matched_name"] == "Filler 01"
    rat = cards["Swarm Rat"]
    # 25 decks spell it "swarm rat"; two corpus decks spell it "Swarm Rat": 27 distinct decks.
    assert rat["matched"] and rat["hits"] == 27 and rat["matched_name"] == "swarm rat"


def test_two_spellings_count_the_union_of_their_decks(client: TestClient) -> None:
    _put(client, "alle", {})
    card = _spread(client, "alle")["Filler 02 // Back Side"]
    # decks 00-09 list "Filler 02", decks 10-24 the full name: disjoint, so 25 distinct decks.
    assert card["hits"] == 25 and card["matched_name"] == "Filler 02 // Back Side"
    assert {item["name"]: item["hits"] for item in card["spellings"]} == {
        "Filler 02 // Back Side": 15,
        "Filler 02": 10,
    }


def test_marks_never_change_spread_or_evidence(client: TestClient) -> None:
    _put(client, "alle", {})
    forest = "card:project:0002"
    rat = "card:project:0007"
    bear = "card:project:0006"
    one_url = f"/api/cards/{forest}/universe"
    spread_before = client.get("/api/universe/spread", params={"profile": "alle"}).text
    one_before = client.get(one_url, params={"profile": "alle"}).text
    evidence_before = client.get("/api/evidence", params=COMMANDER).text
    marks = (
        (forest, {"favorite": True, "excluded": False, "note": "private note text"}),
        (rat, {"favorite": False, "excluded": True, "note": ""}),
        (bear, {"favorite": False, "excluded": False, "note": "nur eine Notiz"}),
    )
    for card_id, body in marks:
        assert client.put(f"/api/cards/{card_id}/mark", json=body, headers=MARK).status_code == 200
    assert client.get("/api/universe/spread", params={"profile": "alle"}).text == spread_before
    assert client.get(one_url, params={"profile": "alle"}).text == one_before
    assert client.get("/api/evidence", params=COMMANDER).text == evidence_before
    assert "private note text" not in spread_before


def test_evidence_is_identical_with_or_without_a_profile(client: TestClient) -> None:
    before = client.get("/api/evidence", params=COMMANDER).json()
    _put(client, "alle", {})
    after = client.get("/api/evidence", params=COMMANDER).json()
    assert json.dumps(after, sort_keys=True) == json.dumps(before, sort_keys=True)
    assert after["tier_policy"]["version"] == before["tier_policy"]["version"]
    assert after["summary"]["unrated"] == after["summary"]["cards"] > 0
    assert {card["rating"]["tier"] for card in after["cards"]} == {None}


def test_cooccurrence_has_both_denominators_and_checks_the_limit(client: TestClient) -> None:
    _put(client, "alle", {})
    url = "/api/cards/card:project:0007/cooccurrence"
    data = client.get(url, params={"profile": "alle", "limit": 3}).json()
    assert data["decks_with_card"] == 27 and data["denominator"] == 43
    assert data["decks_with_card_label"] and data["denominator_label"]
    assert len(data["pairs"]) == 3
    assert {"Forest", "Filler 03"} == {pair["card_name"] for pair in data["pairs"][:2]}
    assert data["pairs"][0]["decks_together"] == 26
    assert client.get(url, params={"profile": "alle", "limit": 0}).status_code == 422
    unmatched = client.get(
        "/api/cards/card:project:0006/cooccurrence", params={"profile": "alle"}
    ).json()
    assert unmatched["matched"] is False and unmatched["decks_with_card"] is None
    assert unmatched["pairs"] == []


def test_unknown_profile_or_card_is_404(client: TestClient) -> None:
    _put(client, "alle", {})
    assert client.get("/api/universe/profiles/nope/summary").status_code == 404
    assert client.get("/api/universe/spread", params={"profile": "nope"}).status_code == 404
    assert client.get("/api/cards/x/universe", params={"profile": "alle"}).status_code == 404
    assert (
        client.get("/api/cards/card:project:0002/universe", params={"profile": "nope"}).status_code
        == 404
    )
    assert client.get("/api/cards/x/cooccurrence", params={"profile": "alle"}).status_code == 404


def test_the_page_carries_the_new_field_and_stays_free_of_inline_code() -> None:
    page = (STATIC / "tierliste.html").read_text(encoding="utf-8")
    script = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    assert "Verbreitung (gezählt)" in script
    assert 'id="universe-select"' in page and 'id="universe-panel"' in page
    assert "Unbewertet" in script
    assert "<script>" not in page and " style=" not in page and " onclick=" not in page


def test_case_variants_across_decks_count_distinct_decks(client: TestClient, folder: Path) -> None:
    _add_card(
        folder,
        "card:t:sol",
        "Sol Ring",
        [["Sol Ring"], ["sol ring"], ["SOL RING"], ["Sol Ring", "sol ring"]],
    )
    _put(client, "alle", {})
    card = _spread(client, "alle")["Sol Ring"]
    assert card["hits"] == 4 and card["matched_name"] == "Sol Ring"
    assert {item["name"]: item["hits"] for item in card["spellings"]} == {
        "Sol Ring": 2,
        "sol ring": 2,
        "SOL RING": 1,
    }
    together = client.get("/api/cards/card:t:sol/cooccurrence", params={"profile": "alle"}).json()
    assert together["decks_with_card"] == 4


def test_a_front_face_shared_with_another_card_is_not_used(
    client: TestClient, folder: Path
) -> None:
    _add_card(folder, "card:t:fire", "Fire", [["Fire"], ["Fire"]])
    _add_card(folder, "card:t:ice", "Fire // Ice", [["Fire // Ice"], ["Fire"]])
    _put(client, "alle", {})
    cards = _spread(client, "alle")
    assert cards["Fire // Ice"]["hits"] == 1
    assert cards["Fire // Ice"]["ambiguous_front_face"] is True
    assert cards["Fire"]["hits"] == 3 and "ambiguous_front_face" not in cards["Fire"]


def test_a_double_faced_card_listed_only_by_its_front_face_is_matched(
    client: TestClient, folder: Path
) -> None:
    _add_card(folder, "card:t:kala", "Kala // Verso", [["Kala"]] * 5)
    _put(client, "alle", {})
    card = _spread(client, "alle")["Kala // Verso"]
    assert card["matched"] and card["hits"] == 5 and card["matched_name"] == "Kala"


def test_min_main_cards_counts_a_card_in_main_and_mainboard_once(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        _deck(store, "a", "edhrec", 3, ["X", "Y"], section="main")
        _deck(store, "b", "edhrec", 3, ["X", "Y", "Z"], section="mainboard")
        store.connection.execute(
            "INSERT INTO corpus_deck_card(deck_id, card_name, section, oracle_id, quantity, "
            "normalization_status) VALUES ('a', 'X', 'mainboard', NULL, 1, 'source_name')"
        )
        store.connection.commit()
        assert universe.resolve_universe(store, {"min_main_cards": 3}) == ["b"]
        assert universe.resolve_universe(store, {"min_main_cards": 2}) == ["a", "b"]
    finally:
        store.close()


def test_the_profile_body_is_strict_about_min_main_cards(client: TestClient) -> None:
    url = "/api/universe/profiles/x"
    assert client.put(url, json={"min_main_cards": True}, headers=MARK).status_code == 422
    assert client.put(url, json={"min_main_cards": 1}, headers=MARK).status_code == 200


def test_universe_figures_need_a_commander_and_are_not_shared(folder: Path) -> None:
    with TestClient(create_app(folder)) as plain:
        assert plain.put("/api/universe/profiles/alle", json={}, headers=MARK).status_code == 422
        assert plain.get("/api/universe/spread", params={"profile": "alle"}).status_code == 422
        other = {"commander": "Second Commander"}
        saved = plain.put("/api/universe/profiles/alle", json={}, headers=MARK, params=other)
        assert saved.status_code == 200 and saved.json()["denominator"] == 0
        mine = plain.get("/api/universe/profiles/alle/summary", params=COMMANDER).json()
        assert mine["denominator"] == 43


# ---------- steps 1-3: options endpoint, spec validation, pool on the universe ----------


def test_options_endpoint_lists_the_stored_values_with_counts(
    client: TestClient, folder: Path
) -> None:
    data = client.get("/api/universe/options").json()
    assert {item["value"]: item["decks"] for item in data["platforms"]} == {
        "archidekt": 20,
        "edhrec": 20,
        "example": 3,
    }
    cohorts = {item["value"]: item["decks"] for item in data["cohorts"]}
    assert cohorts["bracket:3"] == 20 and cohorts["bracket:4"] == 20
    assert data["commanders"] == [{"value": "Test Commander", "decks": 43}]
    with TestClient(create_app(folder)) as plain:
        other = plain.get("/api/universe/options", params={"commander": "Second Commander"}).json()
        assert other == {"platforms": [], "cohorts": [], "commanders": [], "cards": []}


def test_put_rejects_unknown_values_and_saves_nothing(client: TestClient) -> None:
    url = "/api/universe/profiles/x"
    bad = client.put(url, json={"platforms": ["moxfield"]}, headers=MARK)
    assert bad.status_code == 422 and "moxfield" in bad.json()["detail"]
    assert client.put(url, json={"cohorts": ["bracket:9"]}, headers=MARK).status_code == 422
    assert client.put(url, json={"commanders": ["Nobody"]}, headers=MARK).status_code == 422
    assert client.get("/api/universe/profiles").json() == []


def test_put_with_a_commander_mismatch_is_refused_before_saving(folder: Path) -> None:
    with TestClient(create_app(folder)) as plain:
        answer = plain.put(
            "/api/universe/profiles/fremd",
            json={"commanders": ["Second Commander"]},
            headers=MARK,
            params=COMMANDER,
        )
        assert answer.status_code == 422
        assert plain.get("/api/universe/profiles").json() == []
        saved = plain.put(
            "/api/universe/profiles/eigen",
            json={"commanders": ["Test Commander"]},
            headers=MARK,
            params=COMMANDER,
        )
        assert saved.status_code == 200 and saved.json()["denominator"] == 43


def test_min_universe_is_a_strict_body_field_and_grades_the_spread(client: TestClient) -> None:
    url = "/api/universe/profiles/x"
    assert client.put(url, json={"min_universe": 0}, headers=MARK).status_code == 422
    assert client.put(url, json={"min_universe": True}, headers=MARK).status_code == 422
    saved = _put(client, "klein-aber-ok", {"platforms": ["archidekt"], "min_universe": 5})
    assert saved["spec"]["min_universe"] == 5
    assert saved["min_universe"] == 5 and saved["below_min_universe"] is False
    spread = client.get("/api/universe/spread", params={"profile": "klein-aber-ok"}).json()
    assert spread["params"]["min_universe"] == 5
    assert spread["params"]["cuts"] == tiers.TierParams().to_dict()["cuts"]
    assert spread["model_version"] == tiers.MODEL_VERSION
    assert spread["universe"]["below_min_universe"] is False
    card = next(item for item in spread["cards"] if item["name"] == "Forest")
    assert card["level"] == "S"  # 20 of 20 decks, and 20 >= the profile minimum of 5
    small = _put(client, "klein", {"platforms": ["archidekt"]})
    assert small["min_universe"] == 30 and small["below_min_universe"] is True


def test_pool_with_a_profile_shows_the_same_spread_as_the_tier_list(
    client: TestClient,
) -> None:
    _put(client, "alle", {})
    spread = client.get("/api/universe/spread", params={"profile": "alle"}).json()
    by_name = {item["name"]: item for item in spread["cards"]}
    pool = client.get("/api/pool", params={"commander": "Test Commander", "profile": "alle"}).json()
    forest = next(item for item in pool["cards"] if item["name"] == "Forest")
    assert forest["universe"]["hits"] == by_name["Forest"]["hits"] == 42
    assert forest["universe"]["denominator"] == 43
    assert forest["universe"]["level"] == by_name["Forest"]["level"] == "S"
    # Every pool card the spread knows carries exactly the spread's figures.
    for item in pool["cards"]:
        if "universe" in item:
            ref = by_name[item["name"]]
            assert item["universe"]["hits"] == ref["hits"]
            assert item["universe"]["level"] == ref["level"]
            assert item["universe"]["matched"] == ref["matched"]
    unmatched = [
        item for item in pool["cards"] if item.get("universe") and not item["universe"]["matched"]
    ]
    assert unmatched and all(item["universe"]["hits"] is None for item in unmatched)
    assert pool["universe"]["snapshot_id"] == spread["universe"]["snapshot_id"]
    assert pool["universe"]["model_version"] == tiers.MODEL_VERSION
    assert pool["universe"]["excluded_no_date"] == 0
    # Without a profile the pool payload is the legacy one: no universe anywhere.
    legacy = client.get("/api/pool", params={"commander": "Test Commander"}).json()
    assert "universe" not in legacy
    assert all("universe" not in item for item in legacy["cards"])
    assert (
        client.get(
            "/api/pool", params={"commander": "Test Commander", "profile": "nope"}
        ).status_code
        == 404
    )


def test_pool_universe_figures_do_not_move_with_marks(client: TestClient) -> None:
    _put(client, "alle", {})
    params = {"commander": "Test Commander", "profile": "alle"}
    before = client.get("/api/pool", params=params).json()
    assert (
        client.put(
            "/api/cards/card:project:0002/mark",
            json={"favorite": True, "excluded": True, "note": "private"},
            headers=MARK,
        ).status_code
        == 200
    )
    after = client.get("/api/pool", params=params).json()
    assert after["universe"] == before["universe"]
    assert [item.get("universe") for item in after["cards"]] == [
        item.get("universe") for item in before["cards"]
    ]


def test_pool_with_a_profile_of_another_commander_is_422(folder: Path) -> None:
    store = StudioStore.open(folder)
    try:
        _deck(store, "fremd1", "edhrec", 3, ["Forest"])
        store.connection.execute(
            "UPDATE commander_binding SET commander_name = 'Second Commander' "
            "WHERE kind = 'corpus_deck' AND key = 'fremd1'"
        )
        store.connection.commit()
        universe.save_profile(store, "fremd", {"commanders": ["Second Commander"]})
    finally:
        store.close()
    with TestClient(create_app(folder)) as plain:
        answer = plain.get("/api/pool", params={"commander": "Test Commander", "profile": "fremd"})
        assert answer.status_code == 422


CHULANE_NAME = "Chulane, Teller of Tales"


def _chulane_store(store: StudioStore, tmp_path: Path) -> None:
    """A minimal Chulane store: three collection cards and 30 bound source decks.

    Sol Ring is in all 30 decks, Forest in 15; every deck carries its own filler card
    so no two decks share a fingerprint."""
    db = store.connection
    db.execute(
        "INSERT OR IGNORE INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES ('raw', 'DERIVED_DESCRIPTIVE', 'raw', 'x', '2026-01-01')"
    )
    cards = [
        ("card:t:chulane", CHULANE_NAME, "GWU", "Legendary Creature — Human Druid", 0),
        ("card:t:sol", "Sol Ring", "C", "Artifact", 0),
        ("card:t:forest", "Forest", "G", "Basic Land — Forest", 1),
    ]
    for card_id, name, identity, type_line, basic in cards:
        db.execute(
            "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, type_line, "
            "is_basic_land, commander_legal, source_id) VALUES (?, NULL, ?, ?, ?, ?, 1, 'raw')",
            (card_id, name, identity, type_line, basic),
        )
        db.execute(
            "INSERT INTO inventory(card_id, observed, owned_lower_bound, reserved, "
            "available_lower_bound, quantity_exact, source_id) "
            "VALUES (?, 1, 1, 0, 1, 1, 'raw')",
            (card_id,),
        )
    decks = tmp_path / "chulane-decks"
    decks.mkdir()
    for index in range(30):
        names = [CHULANE_NAME, "Sol Ring", f"Filler {index}"]
        if index < 15:
            names.append("Forest")
        payload = {
            "urlhash": f"h{index:02d}",
            "variante": "upgraded",
            "bracket": 3,
            "savedate": "2026-10-01",
            "source_url": f"https://archidekt.com/decks/h{index:02d}",
            "commanders": [CHULANE_NAME],
            "cards": [{"name": name, "quantity": 1} for name in names],
            "karten_summe": len(names),
            "parse_status": "ok",
        }
        (decks / f"h{index:02d}.json").write_text(json.dumps(payload), encoding="utf-8")
    decklist_import.import_decklists(store, decks, format="edhrec")
    store.bind_unbound(CHULANE_NAME)
    db.commit()


def test_chulane_end_to_end_over_builder_and_tier_list_routes(tmp_path: Path) -> None:
    folder = tmp_path / "studio"
    store = StudioStore.open(folder)
    try:
        _chulane_store(store, tmp_path)
    finally:
        store.close()
    with TestClient(create_app(folder)) as client:
        params = {"commander": CHULANE_NAME}
        saved = client.put(
            "/api/universe/profiles/chulane-alle", json={}, headers=MARK, params=params
        )
        assert saved.status_code == 200 and saved.json()["denominator"] == 30
        spread = client.get(
            "/api/universe/spread", params={"profile": "chulane-alle", **params}
        ).json()
        pool = client.get("/api/pool", params={"profile": "chulane-alle", **params}).json()
        # One universe, one snapshot, in the tier list and in the builder alike.
        assert (
            pool["universe"]["snapshot_id"]
            == spread["universe"]["snapshot_id"]
            == saved.json()["snapshot_id"]
        )
        sol = next(item for item in pool["cards"] if item["name"] == "Sol Ring")
        assert sol["universe"] == {
            "matched": True,
            "hits": 30,
            "denominator": 30,
            "share": 1.0,
            "level": "S",
            "reason": "SHARE_CUT",
            "filter_card": False,  # added with the filter-card marking (Refs #1205)
        }
        forest = next(item for item in pool["cards"] if item["name"] == "Forest")
        assert forest["universe"]["hits"] == 15 and forest["universe"]["level"] == "S"
        together = client.get(
            "/api/cards/card:t:sol/cooccurrence",
            params={"profile": "chulane-alle", **params},
        ).json()
        assert together["decks_with_card"] == 30 and together["denominator"] == 30
        pair = next(p for p in together["pairs"] if p["card_name"] == "Forest")
        assert pair["decks_together"] == 15
        assert pair["lift"] == pytest.approx(1.0)  # (15/30) / (15/30)
        assert pair["combo_partner"] is False


def test_the_pages_carry_the_universe_controls() -> None:
    builder_page = (STATIC / "index.html").read_text(encoding="utf-8")
    builder_script = (STATIC / "app.js").read_text(encoding="utf-8")
    tier_script = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    assert 'id="universe"' in builder_page and 'id="universe-info"' in builder_page
    assert "studio.universe.profile" in builder_script and "studio.universe.profile" in tier_script
    assert "/api/universe/options" in tier_script
    assert "model_version" in tier_script and "excluded_no_date" in tier_script
    assert "combo_partner" in tier_script and "combo_partner" in builder_script


# ---------- steps 4-7: profile lifecycle, card filter, spread controls, data state ----------


def test_delete_universe_profile_route_and_its_errors(client: TestClient) -> None:
    client.put("/api/universe/profiles/weg", json={}, headers=MARK, params=COMMANDER)
    deleted = client.delete("/api/universe/profiles/weg", headers=MARK)
    assert deleted.status_code == 200 and deleted.json() == {"deleted": "weg"}
    assert client.get("/api/universe/profiles").json() == []
    assert client.get("/api/universe/profiles/weg/summary", params=COMMANDER).status_code == 404
    missing = client.delete("/api/universe/profiles/weg", headers=MARK)
    assert missing.status_code == 404
    client.put("/api/universe/profiles/bleibt", json={}, headers=MARK, params=COMMANDER)
    assert client.delete("/api/universe/profiles/bleibt").status_code == 403
    assert len(client.get("/api/universe/profiles").json()) == 1


def test_a_resaved_profile_rises_in_version_everywhere(client: TestClient) -> None:
    url = "/api/universe/profiles/versionen"
    first = client.put(url, json={}, headers=MARK, params=COMMANDER).json()
    assert first["version"] == 1
    second = client.put(url, json={"min_universe": 5}, headers=MARK, params=COMMANDER).json()
    assert second["version"] == 2
    listed = client.get("/api/universe/profiles").json()
    assert listed[0]["version"] == 2 and listed[0]["updated_at"] is not None
    spread = client.get("/api/universe/spread", params={"profile": "versionen", **COMMANDER}).json()
    assert spread["universe"]["version"] == 2


def test_card_filter_counts_chulane_decks_by_hand(tmp_path: Path) -> None:
    folder = tmp_path / "studio"
    store = StudioStore.open(folder)
    try:
        _chulane_store(store, tmp_path)
    finally:
        store.close()
    params = {"commander": CHULANE_NAME}
    with TestClient(create_app(folder)) as client:

        def saved(body: dict[str, object]) -> dict[str, object]:
            return client.put(
                "/api/universe/profiles/filter", json=body, headers=MARK, params=params
            ).json()

        ring = saved({"must_contain": ["Sol Ring"]})
        assert ring["denominator"] == 30 and ring["excluded_by_card_filter"] == 0
        forest = saved({"must_contain": ["Forest"]})
        assert forest["denominator"] == 15 and forest["excluded_by_card_filter"] == 15
        both = saved({"must_contain": ["Sol Ring", "Forest"]})
        assert both["denominator"] == 15  # the intersection, not the union
        # The commander himself: no deck lists him in its main deck, but every deck
        # is bound to him, so the commander exception carries all 30.
        own = saved({"must_contain": [CHULANE_NAME]})
        assert own["denominator"] == 30
        combined = saved({"must_contain": ["Forest"], "cohorts": ["bracket:3"]})
        assert combined["denominator"] == 15
        assert combined["denominator_by_bracket"] == {"bracket:3": 15}
        refused = client.put(
            "/api/universe/profiles/filter",
            json={"must_contain": ["Black Lotus"]},
            headers=MARK,
            params=params,
        )
        assert refused.status_code == 422 and "Black Lotus" in refused.json()["detail"]
        summary = client.get("/api/universe/profiles/filter/summary", params=params).json()
        assert summary["version"] == 5  # the refused save changed nothing
        assert summary["spec"]["must_contain"] == ["Forest"]


def test_options_offer_cards_with_their_filtered_denominator(tmp_path: Path) -> None:
    folder = tmp_path / "studio"
    store = StudioStore.open(folder)
    try:
        _chulane_store(store, tmp_path)
    finally:
        store.close()
    with TestClient(create_app(folder)) as client:
        data = client.get("/api/universe/options", params={"commander": CHULANE_NAME}).json()
    cards = {item["value"]: item["decks"] for item in data["cards"]}
    assert cards["Sol Ring"] == 30 and cards["Forest"] == 15
    assert cards[CHULANE_NAME] == 30


def test_marks_do_not_change_a_filtered_count(client: TestClient) -> None:
    client.put(
        "/api/universe/profiles/marken",
        json={"must_contain": ["Forest"]},
        headers=MARK,
        params=COMMANDER,
    )
    before = client.get("/api/universe/spread", params={"profile": "marken", **COMMANDER}).text
    summary_before = client.get("/api/universe/profiles/marken/summary", params=COMMANDER).text
    marked = client.put(
        "/api/cards/card:project:0002/mark",
        json={"favorite": True, "excluded": True, "note": "nur eine Notiz"},
        headers=MARK,
    )
    assert marked.status_code == 200
    assert (
        client.get("/api/universe/spread", params={"profile": "marken", **COMMANDER}).text == before
    )
    assert (
        client.get("/api/universe/profiles/marken/summary", params=COMMANDER).text == summary_before
    )


def test_status_and_data_report_routes_show_the_data_state(client: TestClient) -> None:
    status = client.get("/api/status").json()
    assert status["universe_profiles"] == 0
    inventory = status["source_inventory"]
    assert inventory["total_sources"] > 0
    assert set(inventory["status_counts"]) == {"VERIFIED", "REVIEW", "UNAVAILABLE"}
    report = client.get("/api/data-report").json()
    assert report["schema"] == "studio-data-report-1"
    assert report["universes"]["profiles"] == 0
    assert report["universes"]["model_version"] == "counted-spread-1"
    client.put("/api/universe/profiles/stand", json={}, headers=MARK, params=COMMANDER)
    assert client.get("/api/status").json()["universe_profiles"] == 1
    assert client.get("/api/data-report").json()["universes"]["profiles"] == 1


def test_the_tier_page_carries_the_steps_4_to_7_controls() -> None:
    page = (STATIC / "tierliste.html").read_text(encoding="utf-8")
    script = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    builder_script = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'id="spread-filter"' in page
    assert '"spread"' in script and '"spread_level"' in script
    assert "LEVEL_RANK" in script and "spread-filter" in script
    assert "must_contain" in script and "u-card-list" in script
    assert "Universum löschen" in script and '"DELETE"' in script
    assert "excluded_by_card_filter" in script and "excluded_by_card_filter" in builder_script
    assert "Version" in script and "version" in builder_script
