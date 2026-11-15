"""Similar source decks, the spec of #1404 (PR C): exact order, counting rules, routes, page file.

Everything runs on synthetic store data. The expected order is derived here from the design
table with exact fractions, not by calling the code under test.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import RevisionCard, StudioStore, builder, create_revision, labels
from commander_lab.studio.similar_decks import find_similar_decks
from commander_lab.studio.web import create_app

COMMANDER = "Test Commander"
STATIC_DIR = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"
USER = frozenset(f"Pool Card {i:02d}" for i in range(1, 11))
NOTE = "Ähnlich heißt: gleiche Karten, nicht: erfolgreich."
NOTE_TAIL = "Zu Erfolg je Deck gibt es für"


def _pool(*numbers: int) -> set[str]:
    return {f"Pool Card {i:02d}" for i in numbers}


@dataclass
class Deck:
    cards: set[str]
    cohort: str = "bracket:4"
    platform: str = "moxfield"
    duplicate_of: str | None = None
    basics: dict[str, int] = field(default_factory=lambda: {"Forest": 30})


def _designed() -> dict[str, Deck]:
    """30+ source decks. USER is Pool Card 01..10 (ten cards besides commander and basics)."""
    decks: dict[str, Deck] = {
        # shared 9 (no Pool Card 10), size 12 -> 9/13
        "sd_01": Deck(_pool(*range(1, 10), 11, 12) | {"Outside Card A"}),
        # same card set as sd_01, other basics: an exact duplicate, only sd_01 stays
        "sd_06": Deck(
            _pool(*range(1, 10), 11, 12) | {"Outside Card A"},
            "bracket:3", "archidekt", basics={"Plains": 20},
        ),  # fmt: skip
        # exactly the user's ten cards: the deck itself, left out
        "sd_07": Deck(_pool(*range(1, 11)), "bracket:3", basics={"Island": 36}),
        # shared 8, size 11 -> 8/13
        "sd_02": Deck(_pool(*range(1, 9), 11, 15) | {"Outside Card A"}, "bracket:3"),
        # shared 4, size 6 -> 4/12 = 1/3
        "sd_03": Deck(_pool(1, 2, 3, 4, 11, 12), "bracket:4"),
        # shared 7, size 10 -> 7/13
        "sd_04": Deck(_pool(*range(1, 8), 11, 15) | {"Outside Card A"}, "bracket:3"),
        # shared 5, size 10 -> 5/15 = 1/3: ties sd_03 with MORE shared cards, higher deck id
        "sd_05": Deck(_pool(1, 2, 3, 4, 5, 11, 12, 13, 14, 15)),
        # nothing shared
        "sd_08": Deck(_pool(11, 12, 13), "bracket:3"),
        # only basic lands and the commander: no card to compare
        "sd_09": Deck(set(), basics={"Forest": 36}),
        # shared 6, size 8 -> 6/12 = 1/2 (two cards outside the collection)
        "sd_10": Deck(_pool(*range(1, 7)) | {"Outside Card A", "Outside Card B"}),
        # shared 7, size 8 -> 7/11
        "sd_11": Deck(_pool(*range(1, 8)) | {"Outside Card A"}, "bracket:3"),
        # marked as an exact duplicate of sd_11 by the store itself: never counted
        "sd_dup": Deck(_pool(*range(1, 8)) | {"Outside Card A"}, "bracket:3", duplicate_of="sd_11"),
    }
    for number in range(12, 31):
        shift = (5 * number + number // 3) % 10
        cards = _pool(*(((shift + step * 7) % 10) + 1 for step in range(2)))  # two of the user's
        cards |= _pool(*(i for i in range(11, 16) if i != 11 + number % 5))  # four of the others
        if number % 4 == 0:
            cards.add("Outside Card A")
        decks[f"sd_{number:02d}"] = Deck(cards, "bracket:4" if number % 2 else "bracket:3")
    return decks


def _expected_order(decks: dict[str, Deck], user: frozenset[str], cohort: str | None = None) -> list[str]:
    """Brute force with exact fractions: by similarity, then deck id; a card set only once
    (lowest deck id), the user's own card set and empty decks left out."""
    seen: set[frozenset[str]] = set()
    rows: list[tuple[Fraction, str]] = []
    for deck_id in sorted(decks):
        deck = decks[deck_id]
        cards = frozenset(deck.cards)
        if deck.duplicate_of or not cards or cards == user:
            continue
        if cohort is not None and deck.cohort != cohort:
            continue
        if cards in seen:
            continue
        seen.add(cards)
        rows.append((Fraction(len(cards & user), len(cards | user)), deck_id))
    rows.sort(key=lambda item: (-item[0], item[1]))
    return [deck_id for _score, deck_id in rows]


def _build(folder: Path, decks: dict[str, Deck]) -> StudioStore:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(folder / "studio")
    _fill(store, folder)
    source_id = str(store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
    with store.connection as db:
        for table in (
            "corpus_deck_role", "corpus_deck_stat", "corpus_deck_part", "corpus_cohort",
            "corpus_deck_card",
        ):  # fmt: skip
            db.execute(f"DELETE FROM {table}")
        db.execute("DELETE FROM commander_binding WHERE kind = 'corpus_deck'")
        db.execute("DELETE FROM corpus_deck")
        for number in range(1, 16):
            card_id = f"p_{number:02d}"
            db.execute(
                "INSERT INTO card (card_id, oracle_id, oracle_name, color_identity, mana_cost, "
                "mana_value, type_line, oracle_text, is_basic_land, commander_legal, "
                "legality_verified_at, identity_evidence, source_id) "
                "VALUES (?, ?, ?, 'G', '{1}{G}', 2.0, 'Creature — Elf', '', 0, 1, "
                "'2026-11-15', 'scryfall', ?)",
                (card_id, f"oid_{number:02d}", f"Pool Card {number:02d}", source_id),
            )
            db.execute(
                "INSERT INTO inventory VALUES (?, 1, 2, 0, ?, 1, 1, '2026-11-15', ?)",
                (card_id, 0 if number == 15 else 2, source_id),
            )
    _insert_decks(store, decks, source_id)
    return store


def _insert_decks(store: StudioStore, decks: dict[str, Deck], source_id: str) -> None:
    deck_rows = []
    card_rows = []
    binding_rows = []
    for deck_id, deck in decks.items():
        deck_rows.append(
            (
                deck_id, deck.cohort, f"https://example.org/decks/{deck_id}", deck.platform,
                "community", "2026-11-01", "", f"fp_{deck_id}", deck.duplicate_of, "ok", source_id,
            )  # fmt: skip
        )
        binding_rows.append(("corpus_deck", deck_id, COMMANDER, "test"))
        card_rows.append((deck_id, COMMANDER, "oracle-test-commander", 1, "commander", "exact"))
        for basic, quantity in deck.basics.items():
            card_rows.append((deck_id, basic, f"oracle-{basic.lower()}", quantity, "main", "exact"))
        for name in sorted(deck.cards):
            oracle = f"oid_{name[-2:]}" if name.startswith("Pool Card") else f"oid_{name}"
            card_rows.append((deck_id, name, oracle, 1, "main", "exact"))
    with store.connection as db:
        db.executemany(
            "INSERT INTO corpus_deck VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", deck_rows
        )
        db.executemany("INSERT INTO commander_binding VALUES (?, ?, ?, ?)", binding_rows)
        db.executemany("INSERT INTO corpus_deck_card VALUES (?, ?, ?, ?, ?, ?)", card_rows)


def _user_ids(store: StudioStore, *, extra_basic: bool = False) -> list[str]:
    pool = builder.pool_cards(store, [COMMANDER])
    commander = str(pool["commander_ids"][0])  # type: ignore[index]
    forest = next(str(c["card_id"]) for c in pool["cards"] if c["name"] == "Forest")  # type: ignore[union-attr]
    ids = [commander, forest, *(f"p_{i:02d}" for i in range(1, 11))]
    if extra_basic:
        ids.append(forest)
    return ids


@pytest.fixture(scope="module")
def designed(tmp_path_factory: pytest.TempPathFactory) -> tuple[StudioStore, dict[str, Deck]]:
    decks = _designed()
    store = _build(tmp_path_factory.mktemp("similar"), decks)
    return store, decks


def _run(store: StudioStore, **kwargs: object) -> dict[str, object]:
    options: dict[str, object] = {"cohort": "all", "n": 20, "include_unowned": False}
    options.update(kwargs)
    return find_similar_decks(store, [COMMANDER], deck_card_ids=_user_ids(store), **options)  # type: ignore[arg-type]


def test_exact_neighbour_order_with_ties_and_duplicates(designed) -> None:
    store, decks = designed
    wanted = _expected_order(decks, USER)
    result = _run(store, n=100)
    assert result["method"] == "jaccard_without_basic_lands"
    assert [row["deck_id"] for row in result["nearest"]] == wanted  # type: ignore[index, union-attr]
    assert result["decks_considered"] == len(wanted)
    # the designed decks keep their known places
    assert wanted[:3] == ["sd_01", "sd_11", "sd_02"]  # 9/13, 7/11, 8/13
    assert wanted.index("sd_03") < wanted.index("sd_05")  # tie 1/3: the lower id first
    first = result["nearest"][0]  # type: ignore[index]
    assert (first["shared"], first["size"], first["similarity"]) == (9, 12, round(9 / 13, 4))
    assert first["platform"] == "moxfield"
    assert first["bracket"] == "bracket:4"
    assert first["url"] == "https://example.org/decks/sd_01"
    assert first["deck_date"] == "2026-11-01"


def test_a_tie_breaks_by_deck_id_and_not_by_shared_cards(designed) -> None:
    store, _decks = designed
    ids = [row["deck_id"] for row in _run(store, n=100)["nearest"]]  # type: ignore[index, union-attr]
    # sd_03 (4 shared, size 6) and sd_05 (5 shared, size 10) are both 1/3
    assert ids.index("sd_03") + 1 == ids.index("sd_05") or ids.index("sd_03") < ids.index("sd_05")
    rows = {row["deck_id"]: row for row in _run(store, n=100)["nearest"]}  # type: ignore[index, union-attr]
    assert Fraction(rows["sd_03"]["shared"], 10 + rows["sd_03"]["size"] - rows["sd_03"]["shared"]) == Fraction(
        rows["sd_05"]["shared"], 10 + rows["sd_05"]["size"] - rows["sd_05"]["shared"]
    )
    assert rows["sd_05"]["shared"] > rows["sd_03"]["shared"]


def test_duplicates_and_the_deck_itself_are_left_out(designed) -> None:
    store, _decks = designed
    result = _run(store, n=100)
    ids = {row["deck_id"] for row in result["nearest"]}  # type: ignore[union-attr]
    assert "sd_06" not in ids  # same card set as sd_01
    assert "sd_07" not in ids  # the user's own card set
    assert "sd_dup" not in ids  # marked duplicate_of in the store
    assert "sd_09" not in ids  # no card besides basics
    assert result["identical_to_deck"] == 1
    assert int(result["duplicates_removed"]) >= 1  # type: ignore[call-overload]


def test_basic_lands_and_the_commander_never_count(designed) -> None:
    store, _decks = designed
    plain = _run(store, n=100)
    with_more_basics = find_similar_decks(
        store, [COMMANDER], deck_card_ids=_user_ids(store, extra_basic=True), n=100
    )
    assert with_more_basics == plain
    sizes = {row["deck_id"]: row["size"] for row in plain["nearest"]}  # type: ignore[union-attr]
    assert sizes["sd_01"] == 12  # 12 cards, the 30 Forest and the commander do not add
    assert plain["user_nonbasic_cards"] == 10


def test_hits_of_n_with_the_scaled_threshold_and_a_fixed_order(designed) -> None:
    store, decks = designed
    result = _run(store, n=5)
    nearest = [row["deck_id"] for row in result["nearest"]]  # type: ignore[union-attr]
    assert len(nearest) == 5
    assert result["n"] == 5
    assert result["min_hits"] == 2  # ceil(0.4 * 5)
    counts: dict[str, int] = {}
    for deck_id in nearest:
        for name in decks[deck_id].cards:
            counts[name] = counts.get(name, 0) + 1
    wanted = sorted(
        ((name, hits) for name, hits in counts.items() if name not in USER and hits >= 2 and not name.startswith("Outside")),
        key=lambda item: (-item[1], item[0]),
    )
    rows = [(row["name"], row["hits"]) for row in result["they_play_you_dont"]]  # type: ignore[union-attr]
    assert rows == wanted
    assert all(row["of"] == 5 for row in result["they_play_you_dont"])  # type: ignore[union-attr]
    assert all(row["hits"] >= 2 for row in result["they_play_you_dont"])  # type: ignore[union-attr]
    # twenty neighbours: eight of twenty
    big = _run(store, n=20)
    assert big["n"] == 20
    assert big["min_hits"] == 8
    assert all(row["hits"] >= 8 and row["of"] == 20 for row in big["they_play_you_dont"])  # type: ignore[union-attr]


def test_cards_you_play_and_they_do_not_with_zero_and_one_hit_flagged(designed) -> None:
    store, decks = designed
    result = _run(store, n=5)
    nearest = [row["deck_id"] for row in result["nearest"]]  # type: ignore[union-attr]
    counts = {name: sum(name in decks[d].cards for d in nearest) for name in USER}
    rows = {row["name"]: row for row in result["you_play_they_dont"]}  # type: ignore[union-attr]
    assert set(rows) == {name for name, hits in counts.items() if hits <= 1}
    assert all(row["of"] == 5 for row in rows.values())
    for name, row in rows.items():
        assert row["hits"] == counts[name]
        assert row["none_play"] is (counts[name] == 0)
    assert "Forest" not in rows
    assert COMMANDER not in rows


def test_an_empty_group_says_why_and_is_not_an_error(designed, tmp_path: Path) -> None:
    store, _decks = designed
    result = _run(store, cohort="bracket:2")
    assert result["decks_considered"] == 0
    assert result["empty_reason"] == "zu wenige Decks in dieser Gruppe"
    assert (result["nearest"], result["they_play_you_dont"], result["you_play_they_dont"]) == ([], [], [])
    client = TestClient(create_app(Path(store.path).parent))  # type: ignore[arg-type]
    answer = client.get(
        "/api/similar-decks",
        params={"commander": COMMANDER, "card_id": _user_ids(store), "cohort": "bracket:2"},
    )
    assert answer.status_code == 200
    assert answer.json()["empty_reason"] == "zu wenige Decks in dieser Gruppe"


def test_cards_outside_the_collection_only_with_the_switch(designed) -> None:
    store, _decks = designed
    hidden = _run(store, n=100)
    shown = _run(store, n=100, include_unowned=True)
    top = _run(store, n=5, include_unowned=True)
    assert not any(row["name"].startswith("Outside") for row in hidden["they_play_you_dont"])  # type: ignore[union-attr]
    outside = [row for row in top["they_play_you_dont"] if row["name"].startswith("Outside")]  # type: ignore[union-attr]
    assert [(row["name"], row["hits"], row["of"]) for row in outside] == [("Outside Card A", 5, 5)]
    assert all(row["owned"] == 0 and row["available"] == 0 and row["in_pool"] is False for row in outside)
    assert all(row["card_id"] is None for row in outside)
    assert hidden["nearest"] == shown["nearest"]  # the switch changes no neighbour
    top_hidden = _run(store, n=5)
    assert not any(row["name"].startswith("Outside") for row in top_hidden["they_play_you_dont"])  # type: ignore[union-attr]
    rows = {row["name"]: row for row in top_hidden["they_play_you_dont"]}  # type: ignore[union-attr]
    assert (rows["Pool Card 11"]["hits"], rows["Pool Card 11"]["owned"], rows["Pool Card 11"]["available"]) == (3, 2, 2)
    assert rows["Pool Card 11"]["in_pool"] is True
    # owned, but no free copy (all reserved): it is shown and says so
    assert (rows["Pool Card 15"]["hits"], rows["Pool Card 15"]["owned"], rows["Pool Card 15"]["available"]) == (2, 2, 0)


def test_groups_under_thirty_are_flagged_and_denominators_are_shown(designed) -> None:
    store, decks = designed
    everything = _run(store, n=100)
    one_bracket = _run(store, cohort="bracket:4", n=100)
    wanted_all = len(_expected_order(decks, USER))
    wanted_bracket = len(_expected_order(decks, USER, "bracket:4"))
    assert everything["decks_considered"] == wanted_all
    assert one_bracket["decks_considered"] == wanted_bracket
    assert wanted_all < 30 and wanted_bracket < wanted_all  # a small group is a small group
    assert everything["small_group"] is True
    assert one_bracket["small_group"] is True
    assert everything["small_group_limit"] == 30
    assert [row["deck_id"] for row in one_bracket["nearest"]] == _expected_order(decks, USER, "bracket:4")  # type: ignore[union-attr]
    # fewer decks than asked for: the denominator is what is there
    short = _run(store, cohort="bracket:4", n=100)
    assert short["n"] == len(short["nearest"])  # type: ignore[arg-type]
    assert short["n_requested"] == 100
    assert all(row["of"] == short["n"] for row in short["they_play_you_dont"])  # type: ignore[union-attr]


def test_the_output_is_deterministic(designed) -> None:
    store, _decks = designed
    first = _run(store, n=12, include_unowned=True)
    second = _run(store, n=12, include_unowned=True)
    assert first == second
    from commander_lab.studio import cache

    cache.invalidate()
    assert _run(store, n=12, include_unowned=True) == first


def test_marks_labels_and_favourites_change_nothing(tmp_path: Path) -> None:
    decks = _designed()
    store = _build(tmp_path, decks)
    before = _run(store, n=5, include_unowned=True)
    builder.set_favorite(store, "p_11", True)
    builder.set_mark(store, "p_15", favorite=False, excluded=True, note="nicht dieses")
    builder.set_mark(store, "p_03", favorite=True, excluded=False, note="")
    labels.set_card_labels(store, "p_13", ["Landfall"])
    after = _run(store, n=5, include_unowned=True)
    assert after == before
    names = {row["name"] for row in after["they_play_you_dont"]}  # type: ignore[union-attr]
    assert {"Pool Card 11", "Pool Card 15"} <= names  # an excluded card is still counted


def test_an_import_invalidates_the_remembered_decks(tmp_path: Path) -> None:
    decks = _designed()
    store = _build(tmp_path, decks)
    before = _run(store, n=100)
    assert before["decks_considered"] == len(_expected_order(decks, USER))
    other = StudioStore.open(tmp_path / "studio")  # another connection, as a later request or an import
    source_id = str(other.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
    _insert_decks(other, {"sd_99": Deck(_pool(1, 2, 3, 14))}, source_id)
    other.close()
    after = _run(store, n=100)
    assert after["decks_considered"] == before["decks_considered"] + 1  # type: ignore[operator]
    assert "sd_99" in {row["deck_id"] for row in after["nearest"]}  # type: ignore[union-attr]


def test_routes_resolve_a_revision_and_a_branch_draft_and_refuse_bad_input(tmp_path: Path) -> None:
    decks = _designed()
    store = _build(tmp_path, decks)
    ids = _user_ids(store)
    cards = [RevisionCard(ids[0], 1, "commander"), RevisionCard(ids[1], 12, "main")] + [
        RevisionCard(card_id, 1, "main") for card_id in ids[2:]
    ]
    revision_id = create_revision(store, deck_id="d_user", name="Mein Deck", cards=cards, branch="main")
    client = TestClient(create_app(tmp_path / "studio"))
    base = {"commander": COMMANDER, "n": 5}

    by_revision = client.get("/api/similar-decks", params={**base, "revision": revision_id})
    by_branch = client.get("/api/similar-decks", params={**base, "deck_id": "d_user", "branch": "main"})
    assert by_revision.status_code == by_branch.status_code == 200
    assert by_revision.json() == by_branch.json()
    assert [row["deck_id"] for row in by_revision.json()["nearest"]] == _expected_order(decks, USER)[:5]

    # a draft of the branch is the current list, and wins over the saved revision
    draft = [RevisionCard(ids[0], 1, "commander")] + [RevisionCard(f"p_{i:02d}", 1, "main") for i in (11, 12, 13)]
    builder.write_draft(store, "d_user", "main", draft, revision_id)
    drafted = client.get("/api/similar-decks", params={**base, "deck_id": "d_user", "branch": "main"})
    assert drafted.status_code == 200
    wanted = _expected_order(decks, frozenset(_pool(11, 12, 13)))[:5]
    assert [row["deck_id"] for row in drafted.json()["nearest"]] == wanted
    posted = client.post(
        "/api/similar-decks",
        json={"commander": COMMANDER, "deck_card_ids": ["p_11", "p_12", "p_13"], "n": 5},
        headers={"X-Studio": "1"},
    )
    assert posted.json()["nearest"] == drafted.json()["nearest"]

    assert client.get("/api/similar-decks", params={"revision": revision_id}).status_code == 422
    assert client.get("/api/similar-decks", params={**base, "n": 0, "revision": revision_id}).status_code == 422
    assert client.get("/api/similar-decks", params={**base, "n": 101, "revision": revision_id}).status_code == 422
    assert client.get("/api/similar-decks", params=base).status_code == 422  # no deck named
    both = client.get("/api/similar-decks", params={**base, "revision": revision_id, "deck_id": "d_user"})
    assert both.status_code == 422
    assert client.get("/api/similar-decks", params={**base, "branch": "main"}).status_code == 422
    assert client.get("/api/similar-decks", params={**base, "revision": "no-such-revision"}).status_code == 404
    assert client.get("/api/similar-decks", params={**base, "deck_id": "no-such-deck"}).status_code == 404
    assert (
        client.get("/api/similar-decks", params={**base, "deck_id": "d_user", "branch": "no-branch"}).status_code
        == 404
    )
    unknown = client.get("/api/similar-decks", params={"commander": "Nobody Here", "revision": revision_id})
    assert unknown.status_code == 404
    # an empty list of cards is a deck with nothing to compare, not an error
    empty = client.post(
        "/api/similar-decks", json={"commander": COMMANDER, "deck_card_ids": []}, headers={"X-Studio": "1"}
    )
    assert empty.status_code == 200
    assert empty.json()["nearest"] == []
    assert empty.json()["empty_reason"]


def test_three_thousand_source_decks_in_a_few_seconds(tmp_path: Path) -> None:
    decks: dict[str, Deck] = {}
    for number in range(3000):
        cards = {f"Perf Card {(number * 7 + step * 11) % 300:03d}" for step in range(40)}
        cards |= {f"Perf Unique {number:04d}"}
        cards |= _pool((number % 10) + 1, ((number * 3) % 10) + 1)
        decks[f"sd_{number:05d}"] = Deck(cards, "bracket:3" if number % 3 else "bracket:4")
    store = _build(tmp_path, decks)
    started = time.perf_counter()
    cold = _run(store, n=20)
    cold_seconds = time.perf_counter() - started
    started = time.perf_counter()
    warm = _run(store, n=20)
    warm_seconds = time.perf_counter() - started
    assert cold["decks_considered"] == 3000
    assert len(cold["nearest"]) == 20  # type: ignore[arg-type]
    assert warm == cold
    assert cold_seconds < 5.0, f"cold run took {cold_seconds:.2f} s"
    assert warm_seconds < 5.0, f"warm run took {warm_seconds:.2f} s"


def test_the_page_file_for_similar_decks() -> None:
    page = (STATIC_DIR / "similar.js").read_text(encoding="utf-8")
    index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert NOTE in page
    assert NOTE_TAIL in page
    assert "innerHTML" not in page
    assert "style=" not in page
    assert index.index('src="similar.js"') < index.index('src="app.js"')
    for word in ("Preis", "kaufen", "Zukauf", "besser", "stärker"):
        assert word not in page
    for marker in ("similar-decks-table", "similar-they-play", "similar-you-play", "similar-include-unowned"):
        assert marker in page
    assert "function renderSimilarDecks" not in app  # the section lives in similar.js
    assert "renderSimilarDecks" in app  # and app.js only hooks it in
