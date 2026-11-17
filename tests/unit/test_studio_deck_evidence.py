"""Evidence per deck card: counted cells with n/N, unknown never 0, no sum (#1404)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, builder, card_duel, deck_evidence
from commander_lab.studio.decks import RevisionCard, list_rows
from commander_lab.studio.web import create_app

CMD = "card:project:0001"
FORBIDDEN_KEYS = {
    "sum",
    "total",
    "score",
    "rating",
    "rank",
    "combined",
    "overall",
    "mix",
    "price",
    "better",
    "best",
}


def _store(tmp_path: Path) -> tuple[StudioStore, dict[str, str], str]:
    # Source decks of the fixture: d1 {Swarm Rat, Filler 01}, d2 {Filler 01}, d3 {Swarm Rat,
    # Filler 02, Unknown Card} (d4 is a duplicate); every deck also plays Forest or none.
    from tests.unit.test_studio_card_duel import _store as duel_store

    store, ids, commander = duel_store(tmp_path)
    with store.connection as db:
        db.execute("INSERT INTO corpus_cohort(cohort, deck_id) VALUES ('bracket:4', 'd3')")
    return store, ids, commander


def _rows(store: StudioStore, ids: dict[str, str], *names: str) -> list:  # type: ignore[type-arg]
    cards = [RevisionCard(CMD, 1, "commander")]
    cards += [RevisionCard(ids[name], 1, "main") for name in names]
    return list_rows(store, cards)


def _by_name(result: dict[str, object]) -> dict[str, dict[str, object]]:
    return {str(card["name"]): card for card in result["cards"]}  # type: ignore[attr-defined]


def _keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, inner in value.items():
            found.add(str(key))
            found |= _keys(inner)
    elif isinstance(value, list):
        for inner in value:
            found |= _keys(inner)
    return found


def test_counts_match_a_hand_computed_store(tmp_path: Path) -> None:
    store, ids, commander = _store(tmp_path)
    rows = _rows(store, ids, "Swarm Rat", "Forest", "Filler 01", "Filler 09")
    result = deck_evidence.deck_evidence(store, rows)
    cards = _by_name(result)
    rat, filler = cards["Swarm Rat"]["cells"], cards["Filler 01"]["cells"]
    # Swarm Rat in d1 and d3, Filler 01 in d1 and d2, of 3 distinct source decks.
    assert (rat["decks_all"]["n"], rat["decks_all"]["of"]) == (2, 3)
    assert (filler["decks_all"]["n"], filler["decks_all"]["of"]) == (2, 3)
    # Derived group "tuned" (bracket 4 and 5) holds d3 only: a real 0 of 1 for Filler 01.
    assert (rat["decks_tuned"]["n"], rat["decks_tuned"]["of"]) == (1, 1)
    assert (filler["decks_tuned"]["n"], filler["decks_tuned"]["of"]) == (0, 1)
    assert result["groups"]["all"]["decks"] == 3 == builder.cohort_sizes(store, [commander])["all"]
    assert result["groups"]["tuned"]["decks"] == builder.cohort_sizes(store, [commander])["tuned"]
    # Small groups are flagged (3 and 1 decks are below 30).
    assert result["groups"]["all"]["small_group"] is True
    assert rat["decks_all"]["small_group"] is True
    # Fit by hand over the deck's other cards: Swarm Rat, Filler 01, Filler 09 (3 names).
    # Decks play 2 (d1), 1 (d2), 1 (d3) of them. Swarm Rat (d1, d3): (3 - 2) / (2 * 2) = 0.25;
    # baseline (4 - 2) / (3 * 2); footer baseline 4 / (3 * 3).
    assert rat["fit"]["value"] == 0.25
    assert rat["fit"]["baseline"] == round(2 / 6, 4)
    assert (rat["fit"]["decks"], rat["fit"]["of"]) == (2, 3)
    assert result["footer"]["fit"]["baseline"] == round(4 / 9, 4)
    assert result["footer"]["fit"]["deck_cards"] == 3
    assert result["footer"]["decks_all"] == {"of": 3}


def test_the_count_equals_the_builders_count_and_the_card_duel_fit(tmp_path: Path) -> None:
    store, ids, commander = _store(tmp_path)
    deck = ["Swarm Rat", "Filler 01"]
    result = deck_evidence.deck_evidence(store, _rows(store, ids, *deck), cohort="community")
    pool = {str(c["name"]): c for c in builder.pool_cards(store, [commander])["cards"]}  # type: ignore[attr-defined]
    cards = _by_name(result)
    assert result["cohort"]["key"] == "community"
    for name in deck:
        assert cards[name]["cells"]["decks_all"]["n"] == pool[name]["decks"]["all"]
        assert cards[name]["cells"]["decks_tuned"]["n"] == pool[name]["decks"]["tuned"]
        # card_duel with this card against a card that is not in the deck: the same others.
        duel = card_duel.card_duel(
            store,
            [commander],
            deck_card_ids=[CMD, *(ids[n] for n in deck)],
            card_a=ids[name],
            card_b=ids["Filler 09"],
            cohort="community",
        )
        fit = cards[name]["cells"]["fit"]
        assert (fit["value"], fit["baseline"]) == (duel["a"]["fit"], duel["baseline"])
        assert fit["decks"] == duel["a"]["fit_decks"]


def test_unknown_is_none_never_zero_and_commander_and_basics_are_not_applicable(
    tmp_path: Path,
) -> None:
    store, ids, _commander = _store(tmp_path)
    result = deck_evidence.deck_evidence(
        store, _rows(store, ids, "Swarm Rat", "Forest", "Filler 09")
    )
    cards = _by_name(result)
    unknown = cards["Filler 09"]["cells"]
    # No source deck names Filler 09: every count is unknown, not 0.
    assert unknown["decks_all"] is None and unknown["decks_tuned"] is None
    assert unknown["fit"] is None
    assert unknown["edhrec"] is None and unknown["playgroup"] is None
    assert unknown["roles"] is None and unknown["role_count"] is None
    assert unknown["combos"] is None and unknown["shells"] is None
    commander_row = next(c for c in result["cards"] if c["zone"] == "commander")  # type: ignore[attr-defined]
    for card in (commander_row, cards["Forest"]):
        assert card["applicable"] is False
        assert card["cells"] == {}
    assert commander_row["reason"] == "Commander" and cards["Forest"]["reason"] == "Standardland"
    # The footer baseline counts only applicable cards (Swarm Rat, Filler 09).
    assert result["footer"]["fit"]["deck_cards"] == 2
    assert result["thinnest"]["unknown"] == 1 and result["thinnest"]["applicable"] == 2


def _add_stored_figures(store: StudioStore, commander: str) -> None:
    with store.connection as db:
        db.execute(
            "INSERT INTO source(source_id, data_class, title, sha256, imported_at) "
            "VALUES ('src-ev', 'OBSERVED_COHORT', 'Evidence', ?, 'now')",
            ("0" * 64,),
        )
        for signal, value, num, den in (
            ("edhrec_commander_inclusion", 0.5, 50, 100),
            ("spellbook_shells", 3.0, None, None),
            ("tournament_lists", 0.5, 1, 2),
            ("edhtop16_commander_play_rate", 0.25, None, 48),
        ):
            db.execute(
                "INSERT INTO card_signal(commander_name, signal, card_name, value, numerator, "
                "denominator, source_id) VALUES (?, ?, 'Swarm Rat', ?, ?, ?, 'src-ev')",
                (commander, signal, value, num, den),
            )
        db.execute(
            "INSERT INTO commander_combo(commander_name, ordinal, cards, num_decks, source_id) "
            "VALUES (?, 1, ?, 9, 'src-ev'), (?, 2, ?, 4, 'src-ev')",
            (
                commander,
                json.dumps(["Swarm Rat", "Filler 01"]),
                commander,
                json.dumps(["Filler 01", "Filler 02"]),
            ),
        )
        db.execute(
            "INSERT INTO card_role(oracle_id, role, source_id) VALUES "
            "('oracle-swarm-rat', 'ramp', 'src-ev'), ('oracle-swarm-rat', 'draw', 'src-ev')"
        )
        row = db.execute(
            "SELECT card_id, oracle_id FROM card_fact WHERE oracle_name = 'Swarm Rat'"
        ).fetchone()
        db.execute(
            "INSERT INTO playgroup_card_atlas(oracle_id, card_id, card_name, slug, times_brought, "
            "winrate_when_cast_n, observed_winrate_gap_pp, ci_95_lower_pp, ci_95_upper_pp, "
            "insufficient_sample, source_id, created_at, updated_at) "
            "VALUES (?, ?, 'Swarm Rat', 'slug', 40, 23, 2.5, -1.5, 6.5, 1, 'src-ev', 'n', 'n')",
            (row["oracle_id"], row["card_id"]),
        )


def test_every_kind_of_evidence_is_a_counted_cell_with_its_denominator(tmp_path: Path) -> None:
    store, ids, commander = _store(tmp_path)
    _add_stored_figures(store, commander)
    result = deck_evidence.deck_evidence(store, _rows(store, ids, "Swarm Rat", "Filler 01"))
    rat = _by_name(result)["Swarm Rat"]["cells"]
    assert (rat["edhrec"]["n"], rat["edhrec"]["of"], rat["edhrec"]["pct"]) == (50, 100, 50.0)
    assert rat["edhrec"]["small_group"] is False
    assert rat["shells"] == {"count": 3, "sort": 3}
    # Swarm Rat stands in one of the two listed combos.
    assert (rat["combos"]["n"], rat["combos"]["of"]) == (1, 2)
    assert (rat["topdeck"]["n"], rat["topdeck"]["of"]) == (1, 2)
    assert rat["topdeck"]["small_group"] is True
    # The EDHTop16 count is derived (rate times the published entries), and says so.
    assert (rat["edhtop16"]["n"], rat["edhtop16"]["of"]) == (12, 48)
    assert rat["edhtop16"]["derived_numerator"] is True
    assert rat["edhtop16"]["small_group"] is False
    assert rat["playgroup"]["gap_pp"] == 2.5
    assert (rat["playgroup"]["ci_low_pp"], rat["playgroup"]["ci_high_pp"]) == (-1.5, 6.5)
    assert rat["playgroup"]["n"] == 23 and rat["playgroup"]["small_group"] is True
    assert rat["roles"]["roles"] == ["draw", "ramp"] and rat["role_count"]["n"] == 2
    keys = [column["key"] for column in result["columns"]]  # type: ignore[attr-defined]
    assert "topdeck" in keys and "edhtop16" in keys
    # The same card in the other card (Filler 01) has none of these rows: unknown, not 0.
    filler = _by_name(result)["Filler 01"]["cells"]
    assert filler["edhrec"] is None and filler["shells"] is None and filler["topdeck"] is None
    assert filler["combos"]["n"] == 2 and filler["playgroup"] is None
    # The headers name the group and the population.
    columns = {column["key"]: column for column in result["columns"]}  # type: ignore[attr-defined]
    assert "alle Commander, Mehrspieler (nicht nur Test Commander)" in columns["playgroup"]["basis"]
    assert "Bracket 4 und 5" in columns["decks_tuned"]["basis"]
    assert "Test Commander" in columns["shells"]["basis"]


def test_tournament_columns_exist_only_when_values_exist(tmp_path: Path) -> None:
    store, ids, _commander = _store(tmp_path)
    result = deck_evidence.deck_evidence(store, _rows(store, ids, "Swarm Rat"))
    keys = [column["key"] for column in result["columns"]]  # type: ignore[attr-defined]
    assert keys[:2] == ["decks_all", "decks_tuned"]
    assert "topdeck" not in keys and "edhtop16" not in keys
    assert keys[-1] == "fit"


def test_the_payload_carries_no_sum_no_score_no_combined_figure(tmp_path: Path) -> None:
    store, ids, commander = _store(tmp_path)
    _add_stored_figures(store, commander)
    result = deck_evidence.deck_evidence(
        store, _rows(store, ids, "Swarm Rat", "Forest", "Filler 01", "Filler 09")
    )
    found = _keys(result)
    assert found, "the payload has keys"
    assert {"cells", "columns", "footer", "thinnest"} <= found
    assert not {key.casefold() for key in found} & FORBIDDEN_KEYS
    # The footer holds the group sizes and the baseline, no figure over several columns.
    assert set(result["footer"]) == {"decks_all", "decks_tuned", "fit"}  # type: ignore[arg-type]
    text = json.dumps(result, ensure_ascii=False).casefold()
    assert "besser" not in text and "preis" not in text and "price" not in text
    assert "keine gesamtnote" in str(result["note"]).casefold()


def _fake(name: str, *, sort: object, zone: str = "main", applicable: bool = True) -> dict:  # type: ignore[type-arg]
    cells = {"decks_all": None if sort is None else {"sort": sort}} if applicable else {}
    return {"name": name, "zone": zone, "applicable": applicable, "cells": cells}


def test_sorting_contract_unknown_last_ties_by_name_not_applicable_after() -> None:
    cards = [
        _fake("Delta", sort=5),
        _fake("alpha", sort=5),
        _fake("Unknown B", sort=None),
        _fake("Forest", sort=None, applicable=False),
        _fake("Commander X", sort=None, zone="commander", applicable=False),
        _fake("Charlie", sort=2),
        _fake("Unknown A", sort=None),
        _fake("Bravo", sort=9),
    ]
    ascending = [str(c["name"]) for c in deck_evidence.order_cards(cards)]
    assert ascending == [
        "Charlie",
        "alpha",
        "Delta",
        "Bravo",
        "Unknown A",
        "Unknown B",
        "Commander X",
        "Forest",
    ]
    descending = [str(c["name"]) for c in deck_evidence.order_cards(cards, descending=True)]
    # Unknown still last, ties still by name ascending.
    assert descending == [
        "Bravo",
        "alpha",
        "Delta",
        "Charlie",
        "Unknown A",
        "Unknown B",
        "Commander X",
        "Forest",
    ]


def test_the_default_order_is_the_thinnest_evidence_first(tmp_path: Path) -> None:
    store, ids, _commander = _store(tmp_path)
    result = deck_evidence.deck_evidence(
        store, _rows(store, ids, "Swarm Rat", "Filler 02", "Filler 01", "Filler 09", "Forest")
    )
    order = [str(card["name"]) for card in result["cards"]]  # type: ignore[attr-defined]
    # Filler 02 in 1 deck, Filler 01 and Swarm Rat in 2 (by name), Filler 09 unknown, then the
    # cards that are not applicable (commander first).
    assert order == ["Filler 02", "Filler 01", "Swarm Rat", "Filler 09", "Test Commander", "Forest"]
    thin = result["thinnest"]
    assert [(c["name"], c["n"], c["of"]) for c in thin["cards"]] == [  # type: ignore[attr-defined]
        ("Filler 02", 1, 3),
        ("Filler 01", 2, 3),
        ("Swarm Rat", 2, 3),
    ]
    assert thin["unknown"] == 1


def test_owner_marks_change_nothing(tmp_path: Path) -> None:
    store, ids, commander = _store(tmp_path)
    _add_stored_figures(store, commander)
    names = ("Swarm Rat", "Filler 01", "Filler 02", "Filler 09")
    before = json.dumps(deck_evidence.deck_evidence(store, _rows(store, ids, *names)))
    builder.set_mark(store, ids["Filler 02"], favorite=True, excluded=False, note="mein Liebling")
    builder.set_mark(store, ids["Swarm Rat"], favorite=False, excluded=True, note="raus")
    marked = json.dumps(deck_evidence.deck_evidence(store, _rows(store, ids, *names)))
    assert marked == before


def test_a_group_without_decks_and_a_missing_commander_are_refused(tmp_path: Path) -> None:
    store, ids, _commander = _store(tmp_path)
    rows = _rows(store, ids, "Swarm Rat")
    for call in (
        lambda: deck_evidence.deck_evidence(store, rows, cohort="no-such-group"),
        lambda: deck_evidence.deck_evidence(
            store, list_rows(store, [RevisionCard(ids["Swarm Rat"], 1, "main")])
        ),
    ):
        try:
            call()
        except ValueError:
            continue
        raise AssertionError("expected ValueError")


def test_route(tmp_path: Path) -> None:
    store, ids, commander = _store(tmp_path)
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    cards = [
        {"card_id": CMD, "quantity": 1, "zone": "commander"},
        {"card_id": ids["Swarm Rat"], "quantity": 1, "zone": "main"},
        {"card_id": ids["Forest"], "quantity": 8, "zone": "main"},
    ]
    response = client.post("/api/deck-evidence", json={"cards": cards, "cohort": "all"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["schema"] == "studio-deck-evidence-1"
    assert data["commander"] == [commander]
    assert [c["name"] for c in data["cards"]] == ["Swarm Rat", commander, "Forest"]
    assert data["cards"][0]["cells"]["decks_all"]["n"] == 2
    # 404: an unknown card; 422: no commander, an unknown group, a malformed body.
    unknown = client.post(
        "/api/deck-evidence",
        json={"cards": [*cards, {"card_id": "card:project:nope", "quantity": 1}]},
    )
    assert unknown.status_code == 404
    no_commander = client.post("/api/deck-evidence", json={"cards": cards[1:]})
    assert no_commander.status_code == 422
    bad_group = client.post("/api/deck-evidence", json={"cards": cards, "cohort": "nope"})
    assert bad_group.status_code == 422
    assert client.post("/api/deck-evidence", json={"cards": "x"}).status_code == 422
    # Local use only, like every write-like route.
    assert (
        TestClient(create_app(tmp_path / "studio")).post(
            "/api/deck-evidence", json={"cards": cards}
        )
    ).status_code == 403


def test_an_edhrec_figure_from_the_observation_table_names_its_page(tmp_path: Path) -> None:
    store, ids, _commander = _store(tmp_path)
    with store.connection as db:
        db.execute(
            "INSERT INTO source(source_id, data_class, title, sha256, imported_at) "
            "VALUES ('src-ob', 'ORIGINAL_SOURCE', 'Observations', ?, 'now')",
            ("1" * 64,),
        )
        for name, page, value, num, den in (
            ("Swarm Rat", "edhrec:test-commander", 40.0, 4, 10),
            ("Filler 01", "edhrec:test-commander/artifacts", 50.0, 1, 2),
        ):
            db.execute(
                "INSERT INTO observation(card_id, card_name, metric, cohort, value, numerator, "
                "denominator, data_class, source_id) "
                "VALUES (?, ?, 'inclusion_pct', ?, ?, ?, ?, 'ORIGINAL_SOURCE', 'src-ob')",
                (ids[name], name, page, value, num, den),
            )
    store.bind_unbound("Test Commander")
    result = deck_evidence.deck_evidence(store, _rows(store, ids, "Swarm Rat", "Filler 01"))
    cards = _by_name(result)
    main = cards["Swarm Rat"]["cells"]["edhrec"]
    theme = cards["Filler 01"]["cells"]["edhrec"]
    assert (main["page"], main["main_page"], main["n"], main["of"]) == (
        "test-commander",
        True,
        4,
        10,
    )
    assert theme["page"] == "test-commander/artifacts" and theme["main_page"] is False
    assert (theme["n"], theme["of"]) == (1, 2) and theme["small_group"] is True
    edhrec_column = next(c for c in result["columns"] if c["key"] == "edhrec")  # type: ignore[attr-defined]
    assert "Unterseite" in edhrec_column["basis"] and "in der Zelle" in edhrec_column["basis"]
