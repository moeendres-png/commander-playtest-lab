"""Card duel: frequency n/N and observed fit against the baseline (#1404 option 3)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, card_duel
from commander_lab.studio.web import create_app

CMD = "card:project:0001"


def _store(tmp_path: Path) -> tuple[StudioStore, dict[str, str], str]:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    ids = {
        str(row["oracle_name"]): str(row["card_id"])
        for row in store.connection.execute("SELECT card_id, oracle_name FROM card_fact")
    }
    oracle = {
        str(row["oracle_name"]): str(row["oracle_id"])
        for row in store.connection.execute("SELECT oracle_name, oracle_id FROM card_fact")
    }
    with store.connection as db:
        # Swarm Rat is already in d1 and d3 (fixture). Filler 01 in d1 and d2, Filler 02 in d3.
        for deck, name in (("d1", "Filler 01"), ("d2", "Filler 01"), ("d3", "Filler 02")):
            db.execute(
                "INSERT INTO corpus_deck_card VALUES (?, ?, ?, 1, 'main', 'exact')",
                (deck, name, oracle[name]),
            )
    commander = str(
        store.connection.execute(
            "SELECT oracle_name FROM card_fact WHERE card_id = ?", (CMD,)
        ).fetchone()[0]
    )
    return store, ids, commander


def test_duel_counts_frequency_and_fit_against_the_baseline(tmp_path: Path) -> None:
    store, ids, commander = _store(tmp_path)
    deck = [CMD, ids["Swarm Rat"], ids["Forest"], ids["Filler 01"]]
    result = card_duel.card_duel(
        store, [commander], deck_card_ids=deck, card_a=ids["Filler 01"], card_b=ids["Filler 02"]
    )
    a, b = result["a"], result["b"]
    assert (a["decks"], a["of"], b["decks"], b["of"]) == (2, 3, 1, 3)
    # Other cards: Swarm Rat only (duel cards, commander and basics left out).
    assert result["other_cards"] == 1
    # Decks with Filler 01 (d1, d2): Swarm Rat in d1 only -> 0.5; with Filler 02 (d3) -> 1.0.
    assert a["fit"] == 0.5
    assert b["fit"] == 1.0
    # Baseline over d1, d2, d3: Swarm Rat in d1 and d3.
    assert result["baseline"] == round(2 / 3, 4)
    assert a["in_deck"] is True and b["in_deck"] is False
    assert result["cohort"]["small"] is True


def test_a_card_no_source_deck_names_is_unknown_never_zero(tmp_path: Path) -> None:
    store, ids, commander = _store(tmp_path)
    result = card_duel.card_duel(
        store,
        [commander],
        deck_card_ids=[CMD, ids["Swarm Rat"]],
        card_a=ids["Filler 01"],
        card_b=ids["Filler 09"],
    )
    assert result["b"]["decks"] is None
    assert result["b"]["fit"] is None
    assert result["b"]["share"] is None
    assert result["a"]["decks"] == 2


def test_duel_route(tmp_path: Path) -> None:
    store, ids, commander = _store(tmp_path)
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    body = {
        "commander": commander,
        "deck_card_ids": [CMD, ids["Swarm Rat"]],
        "card_a": ids["Filler 01"],
        "card_b": ids["Filler 02"],
        "cohort": "picked",
    }
    response = client.post("/api/card-duel", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["cohort"] == {"key": "picked", "decks": 1, "small": True}
    assert (data["a"]["decks"], data["a"]["of"]) == (1, 1)
    unknown = client.post("/api/card-duel", json={**body, "card_b": "card:project:nope"})
    assert unknown.status_code == 404


def test_a_front_face_spelling_names_the_two_faced_card() -> None:
    from commander_lab.studio.similar_decks import _canonical_name

    # spelling_owners is keyed by the casefolded spelling (universe._build_spelling_owners).
    owners = {"brazen borrower": ["Brazen Borrower // Petty Theft"]}
    assert _canonical_name(owners, "Brazen Borrower") == "Brazen Borrower // Petty Theft"
    assert _canonical_name(owners, "BRAZEN BORROWER") == "Brazen Borrower // Petty Theft"
    assert _canonical_name(owners, "Unknown Card") == "Unknown Card"


def test_deck_tags_come_from_the_json_list_not_from_comma_splitting() -> None:
    from commander_lab.studio.similar_decks import split_tags

    assert split_tags('["bracket:5", "variant:cedh", "sum:100"]') == [
        "bracket:5",
        "variant:cedh",
        "sum:100",
    ]
    assert split_tags("alpha, beta") == ["alpha", "beta"]
    assert split_tags("") == []
    # Damaged JSON never leaks brackets or quotes into the labels.
    assert split_tags('["bracket:5", "variant') == ["bracket:5", "variant"]
