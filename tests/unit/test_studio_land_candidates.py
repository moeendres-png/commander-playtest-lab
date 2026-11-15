"""Land candidates of the land advisor (#1404): free lands the comparison group plays and the
deck lacks. Counts with their denominators, unknown last and never 0, no mark moves a row.
All data here is synthetic."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import RevisionCard, StudioStore, builder, land_advisor
from commander_lab.studio.web import create_app

COMMANDER = ["Test Commander"]


def _land(
    store: StudioStore,
    name: str,
    *,
    produced: str | None = "G",
    available: int = 1,
    identity: str = "G",
    basic: bool = False,
    legal: int = 1,
    decks: tuple[str, ...] = (),
) -> str:
    """One land of the collection (card, inventory, card data) and the source decks listing it."""
    slug = name.casefold().replace(" ", "-")
    card_id, oracle_id = f"land-{slug}", f"oid-{slug}"
    source_id = str(store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
    type_line = "Basic Land — Forest" if basic else "Land"
    with store.connection as db:
        db.execute(
            "INSERT INTO card (card_id, oracle_id, oracle_name, color_identity, mana_cost, "
            "mana_value, type_line, oracle_text, is_basic_land, commander_legal, "
            "legality_verified_at, identity_evidence, source_id) "
            "VALUES (?, ?, ?, ?, '', 0, ?, '', ?, ?, '2026-11-15', 'scryfall', ?)",
            (card_id, oracle_id, name, identity, type_line, int(basic), legal, source_id),
        )
        db.execute(
            "INSERT INTO inventory VALUES (?, ?, ?, 0, ?, 1, 1, '2026-11-15', ?)",
            (card_id, available, available, available, source_id),
        )
        if produced is not None:
            db.execute(
                "INSERT INTO scryfall_card VALUES (?, ?, ?, ?, 'normal', '', 0, ?, '', "
                "?, ?, 10, '', ?, NULL, NULL, 0, '2020-01-01', '', '', ?, 'SET', '1', 'exact')",
                (
                    oracle_id,
                    f"sf-{card_id}",
                    name,
                    name,
                    type_line,
                    identity,
                    "legal" if legal else "banned",
                    produced,
                    source_id,
                ),
            )
        for deck in decks:
            db.execute(
                "INSERT INTO corpus_deck_card VALUES (?, ?, ?, 1, 'main', 'exact')",
                (deck, name, oracle_id),
            )
    return card_id


@pytest.fixture
def store(tmp_path: Path) -> StudioStore:
    from tests.unit.test_studio_builder import _fill

    opened = StudioStore.open(tmp_path / "studio")
    _fill(opened, tmp_path)  # the group "all" holds d1, d2, d3 (d4 is a duplicate)
    return opened


def _names(store: StudioStore, deck: list[object] | None = None, **options: object) -> list[str]:
    found = land_advisor.land_candidates(store, COMMANDER, deck or [], **options)  # type: ignore[arg-type]
    return [str(item["name"]) for item in found]


def test_order_is_share_then_name_with_unknown_last_and_never_zero(store: StudioStore) -> None:
    _land(store, "Zeta Land", decks=("d1", "d2"))
    _land(store, "Alpha Land", decks=("d1", "d2"))  # same share as Zeta: name decides
    _land(store, "Mid Land", decks=("d1",))
    _land(store, "Rare Land", decks=("d1", "d2", "d3"))  # 3/3 first
    _land(store, "Unknown B", produced=None)  # no source deck names it
    _land(store, "Unknown A")
    found = land_advisor.land_candidates(store, COMMANDER, [], min_share=0.2)
    assert [item["name"] for item in found] == [
        "Rare Land",
        "Alpha Land",
        "Zeta Land",
        "Mid Land",
        "Unknown A",
        "Unknown B",
    ]
    rare, unknown = found[0], found[-1]
    assert (rare["decks"], rare["of"], rare["share"]) == (3, 3, 1.0)
    # an unknown frequency is null, never 0, and is not judged against the line
    assert (unknown["decks"], unknown["share"], unknown["of"]) == (None, None, 3)
    assert all(item["small_group"] is True for item in found)  # 3 decks: under 30
    assert _names(store, min_share=0.2) == [item["name"] for item in found]  # deterministic


def test_a_land_below_the_line_is_left_out_and_the_line_itself_is_in(store: StudioStore) -> None:
    _land(store, "Third Land", decks=("d1",))  # 1/3
    assert _names(store, min_share=1 / 3) == ["Third Land"]
    assert _names(store, min_share=0.34) == []
    assert _names(store, min_share=0.0) == ["Third Land"]


def test_a_share_just_under_the_line_is_not_rounded_into_the_list(
    store: StudioStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _land(store, "Near Land")
    monkeypatch.setattr(builder, "cohort_sizes", lambda _store, _names: {"all": 10001})
    monkeypatch.setattr(
        builder, "_corpus_hits", lambda _store, _names: {"Near Land": {"all": 2000}}
    )
    # 2000 / 10001 is 19.998 %: it rounds to 20 % at four digits, but it is under the line
    assert _names(store, min_share=0.2) == []
    monkeypatch.setattr(
        builder, "_corpus_hits", lambda _store, _names: {"Near Land": {"all": 2001}}
    )
    assert _names(store, min_share=0.2) == ["Near Land"]


def test_a_group_without_decks_has_no_candidates_not_a_list_of_unknowns(
    store: StudioStore,
) -> None:
    _land(store, "Some Land", decks=("d1",))
    assert _names(store, cohort="no-such-group") == []
    assert land_advisor.land_candidates(store, [], []) == []


def test_each_exclusion_holds_on_its_own(store: StudioStore) -> None:
    _land(store, "Plain Basic", basic=True, decks=("d1", "d2"))  # basic land
    _land(store, "Red Land", identity="R", decks=("d1", "d2"))  # outside the identity
    _land(store, "Banned Land", legal=0, decks=("d1", "d2"))  # not legal
    _land(store, "Taken Land", available=0, decks=("d1", "d2"))  # no free copy
    _land(store, "Played Land", decks=("d1", "d2"))  # in the deck
    _land(store, "Free Land", decks=("d1", "d2"))
    assert _names(store, [RevisionCard("land-played-land")]) == ["Free Land"]
    # the deck may come as card objects or as plain card ids; the commander is never listed
    assert _names(store, ["land-played-land"]) == ["Free Land"]
    assert _names(store, [RevisionCard("card:project:0001", 1, "commander")]) == [
        "Free Land",
        "Played Land",
    ]


def test_marks_and_labels_never_change_the_list(store: StudioStore) -> None:
    for name, hits in (("First Land", ("d1", "d2")), ("Second Land", ("d1",))):
        _land(store, name, decks=hits)
    before = land_advisor.land_candidates(store, COMMANDER, [], min_share=0.2)
    builder.set_mark(store, "land-second-land", favorite=True, excluded=False, note="top")
    builder.set_mark(store, "land-first-land", favorite=False, excluded=True, note="")
    assert land_advisor.land_candidates(store, COMMANDER, [], min_share=0.2) == before


def test_the_route_takes_the_line_and_the_group(tmp_path: Path) -> None:
    from tests.unit.test_studio_builder import _deck, _fill

    opened = StudioStore.open(tmp_path / "studio")
    _fill(opened, tmp_path)
    _land(opened, "Tower Land", decks=("d1", "d2"))
    _land(opened, "Pool Land", decks=("d1",))
    opened.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    cards = [card.__dict__ for card in _deck()]

    def candidates(**body: object) -> list[dict[str, object]]:
        answer = client.post("/api/land-advisor", json={"cards": cards, **body})
        assert answer.status_code == 200
        return list(answer.json()["land_candidates"])

    default = candidates()  # the line is 20 % unless the request says otherwise
    assert [(c["name"], c["decks"], c["of"]) for c in default] == [
        ("Tower Land", 2, 3),
        ("Pool Land", 1, 3),
    ]
    assert [c["name"] for c in candidates(min_share=0.5)] == ["Tower Land"]
    community = candidates(cohort="community")  # d1 and d2 only
    assert [(c["name"], c["decks"], c["of"]) for c in community] == [
        ("Tower Land", 2, 2),
        ("Pool Land", 1, 2),
    ]
    assert set(default[0]) == {
        "card_id", "name", "colours", "decks", "of", "share", "available", "small_group",
    }  # fmt: skip
    for bad in (-0.1, 1.5):
        refused = client.post("/api/land-advisor", json={"cards": cards, "min_share": bad})
        assert refused.status_code == 422
